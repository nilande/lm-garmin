"""S1–S3: build Garmin .img files for a region.

S1 convert (GeoPackage → PBF per theme) → S2 split (splitter) → S3 compile (mkgmap + style +
TYP), once per product (base map and snowmobile overlays). Each external step is timed and its
peak memory recorded in build-report.json.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field, replace
from importlib.metadata import version
from pathlib import Path

import osmium

from . import __version__, overview, street_names, stylegen, tools
from .convert import convert
from .products import DEFAULT_PRODUCTS, PRODUCTS, Product, dev_variant
from .region import Region
from .stage_cache import StageCache, publish

FAT32_LIMIT = 3_500_000_000  # stay clear of the 4 GiB per-file limit
SKOTER_TAGS = (("lm:t", "1847"), ("lm:t", "1848"), ("lm:t", "1836"))


@dataclass
class Step:
    name: str
    seconds: float
    max_rss_mb: float | None = 0.0
    detail: dict = field(default_factory=dict)
    cached: bool = False


class BuildError(RuntimeError):
    pass


def _rss_mb(ru_maxrss: int) -> float:
    return round(ru_maxrss / (1e6 if platform.system() == "Darwin" else 1e3), 1)


def run_tool(cmd: list[str], log_path: Path) -> tuple[float, float]:
    """Run an external tool, write its output to log_path, return (seconds, peak RSS MB)."""
    t0 = time.monotonic()
    with log_path.open("w") as log:
        p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
        _, status, ru = os.wait4(p.pid, 0)
    p.returncode = os.waitstatus_to_exitcode(status)
    seconds = time.monotonic() - t0
    text = log_path.read_text(errors="replace")
    if p.returncode != 0 or "SEVERE" in text:
        tail = "\n".join(text.splitlines()[-20:])
        raise BuildError(
            f"{Path(cmd[3]).name} failed (exit {p.returncode}), see {log_path}:\n{tail}"
        )
    return seconds, _rss_mb(ru.ru_maxrss)


def skoter_extract(kommunikation_pbf: Path, out: Path) -> int:
    """Winter trails 1847/1848 and points 1836, with the nodes the ways need."""
    n = 0
    with osmium.BackReferenceWriter(str(out), ref_src=str(kommunikation_pbf), overwrite=True) as w:
        for obj in osmium.FileProcessor(str(kommunikation_pbf)).with_filter(
            osmium.filter.TagFilter(*SKOTER_TAGS)
        ):
            w.add(obj)
            n += 1
    return n


def split(
    java: str,
    inputs: list[Path],
    out_dir: Path,
    product: Product,
    jobs: int,
    max_nodes: int,
    mapid: int | None = None,
) -> Step:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    jar = tools.fetch(tools.TOOLS["splitter"])
    cmd = [
        java,
        "-Xmx4g",
        "-jar",
        str(jar),
        f"--output-dir={out_dir}",
        f"--mapid={mapid or product.mapid_base}",
        f"--max-nodes={max_nodes}",
        f"--max-threads={jobs}",
        "--output=pbf",
        *map(str, inputs),
    ]
    secs, rss = run_tool(cmd, out_dir / "splitter.log")
    tiles = sorted(out_dir.glob("*.osm.pbf"))
    return Step(f"split:{product.key}", round(secs, 2), rss, {"tiles": len(tiles)})


def compile_img(
    java: str,
    tiles: list[Path],
    style_dir: Path,
    work: Path,
    product: Product,
    jobs: int,
    java_mem: str,
) -> Step:
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    jar = tools.fetch(tools.TOOLS["mkgmap"])
    cmd = [
        java,
        f"-Xmx{java_mem}",
        "-jar",
        str(jar),
        f"--output-dir={work}",
        f"--style-file={style_dir}",
        f"--family-id={product.family_id}",
        "--product-id=1",
        f"--family-name={product.name}",
        f"--series-name={product.name}",
        f"--description={product.name}",
        f"--copyright-message={product.copyright}",
        "--unicode",
        "--lower-case",
        # Search results show "<name>, <country abbr>"; mkgmap's default is "ABC".
        "--country-name=Sverige",
        "--country-abbr=SE",
        # Line merging is on by default, but only joins lines that run end-to-start.
        # Topografi 50 segments have no common direction: allow reversing (#62).
        "--allow-reverse-merge",
        "--gmapsupp",
        f"--max-jobs={jobs}",
    ]
    if product.transparent:
        cmd += ["--transparent", f"--draw-priority={product.draw_priority}"]
    else:
        # --net: street data for Where to? › Addresses (named roads, #72).
        cmd += ["--index", "--net"]
    # Tile files are named <mapid>.osm.pbf by splitter; mkgmap takes the map number from it.
    cmd += [*map(str, tiles), str(style_dir / "typ" / f"{product.style}.txt")]
    secs, rss = run_tool(cmd, work / "mkgmap.log")
    img = work / "gmapsupp.img"
    return Step(f"compile:{product.key}", round(secs, 2), rss, {"bytes": img.stat().st_size})


def _write_style(style_dir: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        f = style_dir / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")


def build(
    gpkg_dir: Path,
    region: Region | list[Region],
    out_dir: Path,
    cache: Path,
    products: list[str] | None = None,
    jobs: int | None = None,
    java_mem: str = "4g",
    max_nodes: int = 1_600_000,
    log=print,
    dev: bool = False,
    osm: Path | None = None,
    *,
    topo100_dir: Path | None = None,
    topo250_dir: Path | None = None,
    nvdb_dir: Path | None = None,
) -> dict:
    """Build the products for one region, or several regions combined into one map.

    Each region is converted and split on its own (tile numbers offset by 1000 per region),
    then all tiles are compiled into one .img per product.
    """
    regions = region if isinstance(region, list) else [region]
    jobs = jobs or os.cpu_count() or 4
    keys = products or [*DEFAULT_PRODUCTS, *(["skoter-osm"] if osm is not None else [])]
    if unknown := sorted(set(keys) - PRODUCTS.keys()):
        raise BuildError(f"Unknown map products: {', '.join(unknown)}")
    if "skoter-osm" in keys and (osm is None or not osm.is_file()):
        raise BuildError("skoter-osm requires --osm with a local .osm or .osm.pbf file")
    if osm is not None and "skoter-osm" not in keys:
        raise BuildError("--osm requires skoter-osm in --products (or omit --products)")
    sources = {
        scale: folder / "mark_sverige.gpkg"
        for scale, folder in ((100, topo100_dir), (250, topo250_dir))
        if folder is not None
    }
    if sources and "topo50" not in keys:
        raise BuildError("--topo100-dir and --topo250-dir require topo50 in --products")
    for scale, source in sources.items():
        if not source.is_file():
            raise BuildError(f"Topografi {scale}: missing {source}")
    mapped = {}
    if sources:
        rules = stylegen.load(PRODUCTS["topo50"].style_dir / "mapping.csv")
        mapped = {
            f"{layer}{scale}": {r.t for r in rules if r.layer == f"{layer}{scale}"}
            for scale in sources
            for layer in overview.LAYERS
        }
    nvdb: list[Path] = []
    if nvdb_dir is not None:
        if "topo50" not in keys:
            raise BuildError("--nvdb-dir requires topo50 in --products")
        try:
            nvdb = street_names.sources(nvdb_dir)
        except (OSError, ValueError) as e:
            raise BuildError(f"NVDB: {e}") from e
    prods = {k: dev_variant(PRODUCTS[k]) if dev else PRODUCTS[k] for k in keys}
    if nvdb:
        prods["topo50"] = replace(
            prods["topo50"],
            copyright=f"{prods['topo50'].copyright}, {street_names.COPYRIGHT}",
        )
    java = tools.find_java()
    if not java:
        raise BuildError("java not found – install Java 17+ or set LM_GARMIN_JAVA")
    build_id = "+".join(r.id for r in regions) + ("-dev" if dev else "")
    build_id += "".join(f"-topo{scale}" for scale in sources)
    build_id += "-nvdb" if nvdb else ""
    stage_cache = StageCache(cache)
    out_dir.mkdir(parents=True, exist_ok=True)
    steps: list[Step] = []
    t_all = time.monotonic()

    def run(stage, inputs, produce, name):
        artifact = stage_cache.run(stage, inputs, lambda dest: asdict(produce(dest)))
        record = artifact.record
        steps.append(
            Step(
                name,
                0 if artifact.cached else record["seconds"],
                None if artifact.cached else record["max_rss_mb"],
                record["detail"],
                artifact.cached,
            )
        )
        if artifact.cached:
            log(f"{name}: reused")
        return artifact

    def implementation(*modules):
        return [stage_cache.fingerprint(Path(__file__).with_name(f"{m}.py")) for m in modules]

    with stage_cache.lease():
        convert_lm = any(k in DEFAULT_PRODUCTS for k in keys)
        data_inputs = [
            (p.name, stage_cache.fingerprint(p))
            for p in sorted(gpkg_dir.glob("*.gpkg"))
            if not p.name.startswith("._")
        ]
        # Fingerprint sidecars if a mutable GeoPackage has a write-ahead log.
        data_inputs.extend(
            (p.name, stage_cache.fingerprint(p)) for p in sorted(gpkg_dir.glob("*.gpkg-wal"))
        )
        conversion = [
            __version__,
            implementation(
                "convert", "tags", "region", "forest_overview", "water_overview", "street_names"
            ),
        ]
        # NVDB is part of the conversion key: names are cached per region and NVDB checksum.
        nvdb_inputs = [(p.name, stage_cache.fingerprint(p)) for p in nvdb]
        orchestrator = implementation("build")
        dependencies = {
            pkg: version(pkg)
            for pkg in ("pyogrio", "pyproj", "shapely", "osmium", "pyarrow", "numpy")
        }
        conversion.append(dependencies)
        java_paths = (Path(java), Path(java).resolve().parent.parent / "release")
        java_input = [stage_cache.fingerprint(path) for path in java_paths if path.is_file()]
        tool_inputs = {name: tool.sha256 for name, tool in tools.TOOLS.items()}
        overview_inputs = {
            scale: stage_cache.fingerprint(source) for scale, source in sources.items()
        }
        osm_input = stage_cache.fingerprint(osm) if osm is not None else None

        def region_input(reg):
            return [reg.id, reg.bbox, reg.geometry.wkb_hex if reg.geometry is not None else None]

        def convert_stage(dest, reg):
            t0 = time.monotonic()
            stats = convert(gpkg_dir, reg, dest, jobs, log=log, nvdb=nvdb or None)
            names = next((s.street_names for s in stats if s.street_names), None)
            return Step(
                "convert",
                round(time.monotonic() - t0, 2),
                max((s.max_rss_mb for s in stats), default=0),
                {
                    "features": sum(s.features for s in stats),
                    "pbf": [s.pbf for s in stats if s.nodes],
                    **({"street_names": names} if names else {}),
                },
            )

        converted = [
            run(
                "convert",
                [conversion, data_inputs, region_input(reg), *([nvdb_inputs] if nvdb else [])],
                lambda dest, reg=reg: convert_stage(dest, reg),
                f"convert:{reg.id}",
            )
            if convert_lm
            else None
            for reg in regions
        ]

        osm_trails = None

        def extract_stage(dest, product, reg, source):
            nonlocal osm_trails
            t0 = time.monotonic()
            pbf = dest / "extract.osm.pbf"
            if product == "skoter-osm":
                from .osm_skoter import read_trails, write_region

                try:
                    if osm_trails is None:
                        osm_trails = read_trails(osm, dest / "filtered.osm.pbf")
                        (dest / "filtered.osm.pbf").unlink()
                    count = write_region(osm_trails, gpkg_dir, reg, pbf)
                except (RuntimeError, ValueError) as e:
                    raise BuildError(f"Could not prepare OSM trails: {e}") from e
            elif product == "skoter":
                count = skoter_extract(source, pbf)
            else:
                try:
                    count = sum(overview.write_polygons(sources, reg, pbf, mapped).values())
                except (OSError, RuntimeError, ValueError) as e:
                    raise BuildError(f"Could not prepare overview polygons: {e}") from e
            return Step("extract", round(time.monotonic() - t0, 2), detail={"objects": count})

        outputs = {}
        for k, p in prods.items():
            tiles: list[Path] = []
            tile_inputs = []
            for i, (reg, lm) in enumerate(zip(regions, converted, strict=True)):
                inputs = (
                    [lm.path / filename for filename in lm.record["detail"]["pbf"]] if lm else []
                )
                input_keys = [lm.key] if lm else []
                extract_key = None
                source = None
                if k == "skoter-osm":
                    extract_key = [
                        osm_input,
                        data_inputs,
                        conversion,
                        implementation("osm_skoter"),
                        region_input(reg),
                    ]
                elif k == "skoter":
                    source = lm.path / "kommunikation.osm.pbf"
                    if not source.exists():
                        continue
                    extract_key = [lm.key, orchestrator]
                elif sources and inputs:
                    extract_key = [
                        overview_inputs,
                        region_input(reg),
                        conversion,
                        implementation("overview"),
                        {layer: sorted(codes) for layer, codes in mapped.items()},
                    ]

                if extract_key is not None:
                    extract = run(
                        "extract",
                        [k, extract_key],
                        lambda dest, k=k, reg=reg, source=source: extract_stage(
                            dest, k, reg, source
                        ),
                        f"extract:{k}:{reg.id}",
                    )
                    extra = (
                        [extract.path / "extract.osm.pbf"]
                        if extract.record["detail"]["objects"]
                        else []
                    )
                    if k == "topo50":
                        inputs += extra
                        input_keys.append(extract.key)
                    else:
                        inputs, input_keys = extra, [extract.key]

                if not inputs:
                    continue
                mapid = p.mapid_base + i * 1000
                split_result = run(
                    "split",
                    [
                        input_keys,
                        orchestrator,
                        java_input,
                        tool_inputs["splitter"],
                        mapid,
                        jobs,
                        max_nodes,
                    ],
                    lambda dest, inputs=inputs, p=p, mapid=mapid: split(
                        java, inputs, dest / "tiles", p, jobs, max_nodes, mapid
                    ),
                    f"split:{k}:{reg.id}",
                )
                tile_inputs.append(split_result.key)
                tiles += sorted((split_result.path / "tiles").glob("*.osm.pbf"))

            if not tiles:
                if k == "topo50":
                    raise BuildError(f"{k}: no data in {build_id}")
                if k == "skoter-osm":
                    (out_dir / p.filename).unlink(missing_ok=True)
                log(f"{k}: nothing to build in {build_id}, skipped")
                continue

            resolutions = (
                tuple(overview.RESOLUTIONS[scale] for scale in sources) if k == "topo50" else ()
            )
            style_files = stylegen.generated_files(
                p.style_dir, p.family_id, p.levels, overview_resolutions=resolutions
            )

            def compile_stage(dest, style_files=style_files, tiles=tiles, p=p):
                style_dir = dest / "style"
                _write_style(style_dir, style_files)
                return compile_img(java, tiles, style_dir, dest / "img", p, jobs, java_mem)

            compiled = run(
                "compile",
                [
                    tile_inputs,
                    orchestrator,
                    java_input,
                    tool_inputs["mkgmap"],
                    asdict(p),
                    style_files,
                    jobs,
                    java_mem,
                ],
                compile_stage,
                f"compile:{k}",
            )
            img = compiled.path / "img" / "gmapsupp.img"
            size = img.stat().st_size
            if size > FAT32_LIMIT:
                raise BuildError(
                    f"{k}: {size / 1e9:.2f} GB is too close to FAT32's 4 GiB limit – "
                    "build a smaller region"
                )
            dest = out_dir / p.filename
            publish(img, dest)
            outputs[k] = {
                "file": dest.name,
                "bytes": size,
                "family_id": p.family_id,
                "tiles": len(tiles),
            }
            log(f"{k}: {dest} ({size / 1e6:.1f} MB) in {steps[-1].seconds}s")

    report = {
        "lm_garmin": __version__,
        "regions": [
            {
                "id": r.id,
                "bbox_3006": r.bbox,
                **({"boundary_source": r.boundary_source} if r.boundary_source else {}),
            }
            for r in regions
        ],
        "dev": dev,
        "tools": {t.name: t.version for t in tools.TOOLS.values()},
        "java": java,
        "jobs": jobs,
        "seconds": round(time.monotonic() - t_all, 2),
        "steps": [s.__dict__ for s in steps],
        "outputs": outputs,
    }
    if nvdb:
        report["nvdb_sources"] = [str(p) for p in nvdb]
        report["nvdb"] = street_names.provenance(nvdb)
    if sources:
        report["overview_sources"] = {str(scale): str(path) for scale, path in sources.items()}
    (out_dir / "build-report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report
