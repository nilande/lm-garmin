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
from dataclasses import dataclass, field
from pathlib import Path

import osmium

from . import __version__, overview, stylegen, tools
from .convert import convert
from .products import DEFAULT_PRODUCTS, PRODUCTS, Product, dev_variant
from .region import Region

FAT32_LIMIT = 3_500_000_000  # stay clear of the 4 GiB per-file limit
SKOTER_TAGS = (("lm:t", "1847"), ("lm:t", "1848"), ("lm:t", "1836"))


@dataclass
class Step:
    name: str
    seconds: float
    max_rss_mb: float = 0.0
    detail: dict = field(default_factory=dict)


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
        "--gmapsupp",
        f"--max-jobs={jobs}",
    ]
    if product.transparent:
        cmd += ["--transparent", f"--draw-priority={product.draw_priority}"]
    else:
        cmd += ["--index"]
    # Tile files are named <mapid>.osm.pbf by splitter; mkgmap takes the map number from it.
    cmd += [*map(str, tiles), str(style_dir / "typ" / f"{product.style}.txt")]
    secs, rss = run_tool(cmd, work / "mkgmap.log")
    img = work / "gmapsupp.img"
    return Step(f"compile:{product.key}", round(secs, 2), rss, {"bytes": img.stat().st_size})


def generate_style(
    product: Product, work: Path, overview_resolutions: tuple[int, ...] = ()
) -> Path:
    """Write the product's generated style (with its own family id in the TYP) to work/."""
    out = work / "style" / product.key
    if out.exists():
        shutil.rmtree(out)
    for rel, text in stylegen.generated_files(
        product.style_dir,
        product.family_id,
        product.levels,
        overview_resolutions=overview_resolutions,
    ).items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    return out


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
    prods = {k: dev_variant(PRODUCTS[k]) if dev else PRODUCTS[k] for k in keys}
    java = tools.find_java()
    if not java:
        raise BuildError("java not found – install Java 17+ or set LM_GARMIN_JAVA")
    build_id = "+".join(r.id for r in regions) + ("-dev" if dev else "")
    build_id += "".join(f"-topo{scale}" for scale in sources)
    work = cache / "work" / build_id
    out_dir.mkdir(parents=True, exist_ok=True)
    steps: list[Step] = []
    t_all = time.monotonic()

    osm_trails = []
    if osm is not None:
        from .osm_skoter import read_trails

        t0 = time.monotonic()
        work.mkdir(parents=True, exist_ok=True)
        try:
            osm_trails = read_trails(osm, work / "osm-trails.osm.pbf")
        except (RuntimeError, ValueError) as e:
            raise BuildError(f"Could not read the OSM extract: {e}") from e
        steps.append(
            Step(
                "read:skoter-osm",
                round(time.monotonic() - t0, 2),
                detail={"ways": len(osm_trails)},
            )
        )

    pbf_dirs = []
    convert_lm = any(k in DEFAULT_PRODUCTS for k in keys)
    for reg in regions:
        if not convert_lm:
            pbf_dirs.append((reg, cache / "pbf" / reg.id, []))
            continue
        t0 = time.monotonic()
        pbf_dir = cache / "pbf" / reg.id
        stats = convert(gpkg_dir, reg, pbf_dir, jobs, log=log)
        steps.append(
            Step(
                f"convert:{reg.id}",
                round(time.monotonic() - t0, 2),
                max(s.max_rss_mb for s in stats),
                {"features": sum(s.features for s in stats)},
            )
        )
        pbf_dirs.append((reg, pbf_dir, [pbf_dir / s.pbf for s in stats if s.nodes]))

    outputs = {}
    for k, p in prods.items():
        tiles: list[Path] = []
        for i, (reg, pbf_dir, all_inputs) in enumerate(pbf_dirs):
            if k == "skoter-osm":
                from .osm_skoter import write_region

                t0 = time.monotonic()
                supplement = work / "extract" / reg.id / "skoter-osm.osm.pbf"
                supplement.parent.mkdir(parents=True, exist_ok=True)
                n = write_region(osm_trails, gpkg_dir, reg, supplement)
                steps.append(
                    Step(
                        f"extract:skoter-osm:{reg.id}",
                        round(time.monotonic() - t0, 2),
                        detail={"objects": n},
                    )
                )
                inputs = [supplement] if n else []
            elif k == "skoter":
                src = pbf_dir / "kommunikation.osm.pbf"
                if not src.exists():
                    continue
                t0 = time.monotonic()
                sk = work / "extract" / reg.id / "skoter.osm.pbf"
                sk.parent.mkdir(parents=True, exist_ok=True)
                n = skoter_extract(src, sk)
                steps.append(
                    Step(
                        f"extract:skoter:{reg.id}",
                        round(time.monotonic() - t0, 2),
                        detail={"objects": n},
                    )
                )
                inputs = [sk] if n else []
            else:
                inputs = all_inputs
                if sources and inputs:
                    t0 = time.monotonic()
                    polygons = work / "extract" / reg.id / "overview.osm.pbf"
                    try:
                        counts = overview.write_polygons(sources, reg, polygons, mapped)
                    except (OSError, RuntimeError, ValueError) as e:
                        raise BuildError(f"Could not prepare overview polygons: {e}") from e
                    steps.append(
                        Step(
                            f"extract:overview:{reg.id}",
                            round(time.monotonic() - t0, 2),
                            detail={"polygons": counts},
                        )
                    )
                    inputs = [*inputs, polygons]
            if not inputs:
                continue
            tdir = work / "tiles" / k / reg.id
            steps.append(split(java, inputs, tdir, p, jobs, max_nodes, p.mapid_base + i * 1000))
            steps[-1].name += f":{reg.id}"
            tiles += sorted(tdir.glob("*.osm.pbf"))
        if not tiles:
            if k == "topo50":
                raise BuildError(f"{k}: no data in {build_id}")
            if k == "skoter-osm":
                (out_dir / p.filename).unlink(missing_ok=True)
            log(f"{k}: nothing to build in {build_id}, skipped")
            continue
        log(f"{k}: {len(tiles)} tiles")
        resolutions = (
            tuple(overview.RESOLUTIONS[scale] for scale in sources) if k == "topo50" else ()
        )
        style_dir = generate_style(p, work, resolutions)
        steps.append(compile_img(java, tiles, style_dir, work / "img" / k, p, jobs, java_mem))
        img = work / "img" / k / "gmapsupp.img"
        if img.stat().st_size > FAT32_LIMIT:
            raise BuildError(
                f"{k}: {img.stat().st_size / 1e9:.2f} GB is too close to FAT32's "
                "4 GiB limit – build a smaller region"
            )
        dest = out_dir / p.filename
        shutil.copyfile(img, dest)
        outputs[k] = {
            "file": dest.name,
            "bytes": dest.stat().st_size,
            "family_id": p.family_id,
            "tiles": len(tiles),
        }
        log(f"{k}: {dest} ({dest.stat().st_size / 1e6:.1f} MB) in {steps[-1].seconds}s")

    report = {
        "lm_garmin": __version__,
        "regions": [{"id": r.id, "bbox_3006": r.bbox} for r in regions],
        "dev": dev,
        "tools": {t.name: t.version for t in tools.TOOLS.values()},
        "java": java,
        "jobs": jobs,
        "seconds": round(time.monotonic() - t_all, 2),
        "steps": [s.__dict__ for s in steps],
        "outputs": outputs,
    }
    if sources:
        report["overview_sources"] = {str(scale): str(path) for scale, path in sources.items()}
    (out_dir / "build-report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report
