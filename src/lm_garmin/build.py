"""S1–S3: build Garmin .img files for a region.

S1 convert (GeoPackage → PBF per theme) → S2 split (splitter) → S3 compile (mkgmap + style +
TYP), once per product (base map, snowmobile overlay). Each external step is timed and its
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

from . import __version__, stylegen, tools
from .convert import convert
from .products import PRODUCTS, Product
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
    java: str, inputs: list[Path], out_dir: Path, product: Product, jobs: int, max_nodes: int
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
        f"--mapid={product.mapid_base}",
        f"--max-nodes={max_nodes}",
        f"--max-threads={jobs}",
        "--output=pbf",
        *map(str, inputs),
    ]
    secs, rss = run_tool(cmd, out_dir / "splitter.log")
    tiles = sorted(out_dir.glob("*.osm.pbf"))
    return Step(f"split:{product.key}", round(secs, 2), rss, {"tiles": len(tiles)})


def compile_img(
    java: str, tiles_dir: Path, work: Path, product: Product, jobs: int, java_mem: str
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
        f"--style-file={product.style_dir}",
        f"--family-id={product.family_id}",
        "--product-id=1",
        f"--family-name={product.name}",
        f"--series-name={product.name}",
        f"--description={product.name}",
        "--copyright-message=© Lantmäteriet",
        "--unicode",
        "--lower-case",
        "--gmapsupp",
        f"--max-jobs={jobs}",
    ]
    if product.transparent:
        cmd += ["--transparent", f"--draw-priority={product.draw_priority}"]
    else:
        cmd += ["--index"]
    cmd += ["-c", str(tiles_dir / "template.args"), str(product.typ)]
    secs, rss = run_tool(cmd, work / "mkgmap.log")
    img = work / "gmapsupp.img"
    return Step(f"compile:{product.key}", round(secs, 2), rss, {"bytes": img.stat().st_size})


def build(
    gpkg_dir: Path,
    region: Region,
    out_dir: Path,
    cache: Path,
    products: list[str] | None = None,
    jobs: int | None = None,
    java_mem: str = "4g",
    max_nodes: int = 1_600_000,
    log=print,
) -> dict:
    jobs = jobs or os.cpu_count() or 4
    keys = products or list(PRODUCTS)
    java = tools.find_java()
    if not java:
        raise BuildError("java not found – install Java 17+ or set LM_GARMIN_JAVA")
    work = cache / "work" / region.id
    out_dir.mkdir(parents=True, exist_ok=True)
    steps: list[Step] = []
    t_all = time.monotonic()

    # The styles are generated from mapping.csv; make sure they are current.
    for k in keys:
        p = PRODUCTS[k]
        stylegen.generate(p.style_dir, p.family_id, p.levels)

    t0 = time.monotonic()
    pbf_dir = cache / "pbf" / region.id
    theme_stats = convert(gpkg_dir, region, pbf_dir, jobs, log=log)
    steps.append(
        Step(
            "convert",
            round(time.monotonic() - t0, 2),
            max(s.max_rss_mb for s in theme_stats),
            {"features": sum(s.features for s in theme_stats)},
        )
    )
    all_inputs = [pbf_dir / s.pbf for s in theme_stats if s.nodes]

    outputs = {}
    for k in keys:
        p = PRODUCTS[k]
        if k == "skoter":
            t0 = time.monotonic()
            src = pbf_dir / "kommunikation.osm.pbf"
            if not src.exists():
                log("skoter: no kommunikation data in region, skipped")
                continue
            sk = work / "skoter.osm.pbf"
            sk.parent.mkdir(parents=True, exist_ok=True)
            n = skoter_extract(src, sk)
            steps.append(
                Step("extract:skoter", round(time.monotonic() - t0, 2), detail={"objects": n})
            )
            if n == 0:
                log("skoter: no winter trails in region, skipped")
                continue
            inputs = [sk]
        else:
            inputs = all_inputs
        if not inputs:
            raise BuildError(f"{k}: no data in region {region.id}")
        tiles = work / "tiles" / k
        steps.append(split(java, inputs, tiles, p, jobs, max_nodes))
        log(f"{k}: split into {steps[-1].detail['tiles']} tiles in {steps[-1].seconds}s")
        steps.append(compile_img(java, tiles, work / "img" / k, p, jobs, java_mem))
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
            "tiles": steps[-2].detail["tiles"],
        }
        log(f"{k}: {dest} ({dest.stat().st_size / 1e6:.1f} MB) in {steps[-1].seconds}s")

    report = {
        "lm_garmin": __version__,
        "region": {"id": region.id, "bbox_3006": region.bbox},
        "tools": {t.name: t.version for t in tools.TOOLS.values()},
        "java": java,
        "jobs": jobs,
        "seconds": round(time.monotonic() - t_all, 2),
        "steps": [s.__dict__ for s in steps],
        "outputs": outputs,
    }
    (out_dir / "build-report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report
