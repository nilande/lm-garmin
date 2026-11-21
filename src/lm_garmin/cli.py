"""lm-garmin: build Garmin .img maps from Lantmäteriet's Topografi 50."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, region, tools

NOT_YET: dict[str, str] = {}


def _add_region_args(p: argparse.ArgumentParser, multi: bool = False) -> None:
    g = p.add_mutually_exclusive_group(required=True)
    act = "append" if multi else "store"
    more = " (repeatable)" if multi else ""
    g.add_argument("--bbox", action=act, help=f"xmin,ymin,xmax,ymax in SWEREF 99 TM{more}")
    g.add_argument("--bbox-wgs84", action=act, help=f"lon_min,lat_min,lon_max,lat_max{more}")
    g.add_argument("--region", choices=["sweden"], help="named region")
    g.add_argument("--county", action=act, help=f"county name or SCB code{more}")
    g.add_argument("--municipality", action=act, help=f"municipality name or SCB code{more}")
    p.add_argument("--admin-index", type=Path, help="SCB digital boundaries ZIP for named regions")
    if multi:
        g.add_argument(
            "--area",
            action="append",
            choices=sorted(region.AREAS),
            help="named development area (repeatable)",
        )


def _regions_from_args(a: argparse.Namespace, gpkg_dir: Path, cache: Path) -> list[region.Region]:
    def as_list(v):
        return v if isinstance(v, list) else [v]

    if a.bbox:
        return [region.from_bbox(b) for b in as_list(a.bbox)]
    if a.bbox_wgs84:
        return [region.from_wgs84(b) for b in as_list(a.bbox_wgs84)]
    if getattr(a, "area", None):
        return [region.from_area(n) for n in a.area]
    if a.county or a.municipality:
        from .administrative import named_regions

        kind, names = ("county", a.county) if a.county else ("municipality", a.municipality)
        regions = named_regions(
            kind, as_list(names), gpkg_dir, a.admin_index or cache / "admin-index.zip"
        )
        for selected in regions:
            print(f"{selected.id}: {selected.boundary_source}", file=sys.stderr)
        return regions
    return [region.sweden(gpkg_dir)]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lm-garmin", description=__doc__)
    p.add_argument("--version", action="version", version=f"lm-garmin {__version__}")
    p.add_argument(
        "--cache", type=Path, help="cache folder (default $LM_GARMIN_CACHE or ~/.cache/lm-garmin)"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("tools", help="manage pinned external tools (mkgmap, splitter)")
    tsub = t.add_subparsers(dest="tools_cmd", required=True)
    tsub.add_parser("fetch", help="download and verify mkgmap and splitter")
    tsub.add_parser("path", help="print paths of java and the tool jars")

    u = sub.add_parser("unpack", help="S0: unpack a Topografi 50 delivery into the cache")
    u.add_argument("delivery", type=Path, help="folder with the theme zips (quote the path!)")

    cache_cmd = sub.add_parser("cache", help="inspect or clean cached build stages")
    cache_actions = cache_cmd.add_subparsers(dest="cache_action", required=True)
    cache_actions.add_parser("info", help="report stage entries and disk usage")
    cache_actions.add_parser(
        "clean", help="remove build outputs while keeping source data and tools"
    )

    c = sub.add_parser("convert", help="S1: convert GeoPackages to OSM PBF for a region")
    _add_region_args(c)
    c.add_argument("--gpkg-dir", type=Path, help="GeoPackages (default: <cache>/gpkg)")
    c.add_argument("--out", type=Path, help="output folder (default: <cache>/pbf/<region>)")
    c.add_argument("--jobs", type=int, help="parallel themes (default: CPU count)")
    c.add_argument("--nvdb-dir", type=Path, help="NVDB GeoPackages for street names (Lastkajen)")

    b = sub.add_parser("build", help="S1–S3: build the Garmin maps for a region")
    _add_region_args(b, multi=True)
    b.add_argument(
        "--dev", action="store_true", help="development map: own family ids, files lm-dev-*.img"
    )
    b.add_argument("--gpkg-dir", type=Path, help="GeoPackages (default: <cache>/gpkg)")
    b.add_argument("--topo100-dir", type=Path, help="unpacked Topografi 100 nationwide GeoPackages")
    b.add_argument("--topo250-dir", type=Path, help="unpacked Topografi 250 nationwide GeoPackages")
    b.add_argument(
        "--nvdb-dir",
        type=Path,
        help="unpacked Trafikverket NVDB GeoPackages (Lastkajen) for street names",
    )
    b.add_argument("--out", type=Path, default=Path("dist"), help="output folder (default: dist)")
    b.add_argument(
        "--products",
        help="comma-separated: topo50, skoter, skoter-osm (adds skoter-osm with --osm by default)",
    )
    b.add_argument("--osm", type=Path, help="local .osm or .osm.pbf extract for the OSM supplement")
    b.add_argument("--jobs", type=int, help="parallel jobs (default: CPU count)")
    b.add_argument("--java-mem", default="4g", help="Java heap for mkgmap (default 4g)")
    b.add_argument("--max-nodes", type=int, default=1_600_000, help="splitter --max-nodes")

    s = sub.add_parser("style", help="generate mkgmap styles, TYP and the translation table")
    s.add_argument("action", choices=["generate"])

    i = sub.add_parser("install", help="copy built .img files to a Garmin device (verified)")
    i.add_argument("img", type=Path, nargs="+", help=".img files to install")
    i.add_argument(
        "--device",
        type=Path,
        default=Path("/Volumes/GARMIN"),
        help="mount point of the device (default /Volumes/GARMIN)",
    )

    v = sub.add_parser("verify", help="S4: decode built .img files and check them")
    v.add_argument("img", type=Path, nargs="+", help="tile .img or gmapsupp-style .img files")

    rend = sub.add_parser("render", help="render a Garmin map and compare it to a reference raster")
    rend.add_argument("img", type=Path, help="Garmin .img to decode")
    rend.add_argument("--bbox", help="xmin,ymin,xmax,ymax in SWEREF 99 TM (defaults to reference)")
    rend.add_argument("--reference", type=Path, help="georeferenced RGB raster")
    rend.add_argument("--out", type=Path, default=Path("dist/render"), help="PNG and report folder")
    rend.add_argument("--level", type=int, choices=range(7), default=0, help="Garmin level")
    rend.add_argument("--meters-per-pixel", type=float, default=5, help="SWEREF grid spacing")
    rend.add_argument("--style-mapping", type=Path, help="custom mapping.csv used by the build")
    v.add_argument("--expect", type=Path, help="expectations JSON (see tests/data/expect)")
    v.add_argument("--dump", type=Path, help="also write decoded features as GeoJSON lines")
    v.add_argument("--level-counts", action="store_true", help="print feature counts by level")

    coverage = sub.add_parser("coverage", help="measure GPX coverage of a built snowmobile overlay")
    coverage.add_argument("--img", type=Path, required=True, help="snowmobile overlay .img")
    coverage.add_argument("--gpx", type=Path, required=True, help="GPX file or directory of files")

    nv = sub.add_parser("nvdb", help="prepare Trafikverket NVDB data for street names")
    nv_sub = nv.add_subparsers(dest="nvdb_cmd", required=True)
    nx = nv_sub.add_parser(
        "extract", help="keep only the name layers of NVDB county files (zip or GeoPackage)"
    )
    nx.add_argument("inputs", type=Path, nargs="+", help="county .zip/.gpkg files or folders")
    nx.add_argument(
        "--out", type=Path, required=True, help="output .gpkg (put it in its own folder)"
    )

    for name, text in NOT_YET.items():
        sub.add_parser(name, help=f"{text} – not implemented yet")

    a = p.parse_args(argv)
    cache = a.cache or tools.cache_dir()

    if a.cmd == "tools":
        if a.tools_cmd == "fetch":
            for tool in tools.TOOLS.values():
                print(f"{tool.name} {tool.version}: {tools.fetch(tool)}")
        else:
            print(f"java: {tools.find_java() or 'NOT FOUND'}")
            for tool in tools.TOOLS.values():
                jar = tools.tools_dir() / tool.jar
                print(f"{tool.name}: {jar if jar.exists() else 'not fetched'}")
        return 0

    if a.cmd == "unpack":
        from .unpack import unpack

        res = unpack(a.delivery, cache / "gpkg")
        done = [r for r in res if not r.skipped]
        print(f"{len(done)} unpacked, {len(res) - len(done)} unchanged → {cache / 'gpkg'}")
        return 0

    if a.cmd == "cache":
        from .stage_cache import StageCache

        stages = StageCache(cache)
        if a.cache_action == "clean":
            stages.clean()
            print(f"Cleaned build stages → {stages.root}")
        else:
            with stages.lease():
                info = stages.info()
            for name, usage in info.items():
                print(f"{name}: {usage['entries']} entries, {usage['bytes'] / 1e6:.1f} MB")
            if not info:
                print(f"No cached build stages → {stages.root}")
        return 0

    if a.cmd == "convert":
        from .convert import convert

        gpkg_dir = a.gpkg_dir or cache / "gpkg"
        try:
            reg = _regions_from_args(a, gpkg_dir, cache)[0]
        except (ValueError, RuntimeError) as e:
            p.error(str(e))
        out = a.out or cache / "pbf" / reg.id
        nvdb = None
        if a.nvdb_dir:
            from . import street_names

            try:
                nvdb = street_names.sources(a.nvdb_dir)
            except (OSError, ValueError) as e:
                p.error(str(e))
        stats = convert(gpkg_dir, reg, out, a.jobs, nvdb=nvdb)
        total = sum(s.features for s in stats)
        print(f"{total} features in {len(stats)} themes → {out}")
        return 0

    if a.cmd == "build":
        from .build import BuildError, build

        gpkg_dir = a.gpkg_dir or cache / "gpkg"
        try:
            reg = _regions_from_args(a, gpkg_dir, cache)
        except (ValueError, RuntimeError) as e:
            p.error(str(e))
        try:
            rep = build(
                gpkg_dir,
                reg,
                a.out,
                cache,
                a.products.split(",") if a.products else None,
                a.jobs,
                a.java_mem,
                a.max_nodes,
                dev=a.dev,
                osm=a.osm,
                topo100_dir=a.topo100_dir,
                topo250_dir=a.topo250_dir,
                nvdb_dir=a.nvdb_dir,
            )
        except BuildError as e:
            print(f"build failed: {e}", file=sys.stderr)
            return 1
        print(f"done in {rep['seconds']}s → {a.out}")
        return 0

    if a.cmd == "style":
        from . import style_docs, stylegen
        from .products import PRODUCTS

        for prod in PRODUCTS.values():
            for f in stylegen.generate(prod.style_dir, prod.family_id, prod.levels):
                print(f)
        table = style_docs.TRANSLATION_TABLE
        table.write_text(style_docs.render_translation_table(), encoding="utf-8")
        print(table)
        return 0

    if a.cmd == "install":
        from .install import install

        install(a.img, a.device)
        return 0

    if a.cmd == "verify":
        from .verify import main as verify_main

        return verify_main(a.img, a.expect, a.dump, level_counts=a.level_counts)

    if a.cmd == "render":
        from .render import run
        from .verify import VerifyError

        try:
            report = run(
                a.img,
                a.out,
                bbox=region.parse_bbox(a.bbox) if a.bbox else None,
                reference=a.reference,
                level=a.level,
                metres=a.meters_per_pixel,
                mapping=a.style_mapping,
            )
        except (OSError, ValueError, VerifyError) as e:
            print(f"render failed: {e}", file=sys.stderr)
            return 1
        if report is not None:
            for name, score in report["classes"].items():
                if score["iou"] is not None:
                    print(f"{name}: IoU {score['iou']:.1%}")
        print(f"rendered → {a.out}")
        return 0

    if a.cmd == "coverage":
        from .coverage import CoverageError, measure
        from .verify import VerifyError

        try:
            print(measure(a.img, a.gpx))
        except (CoverageError, VerifyError, OSError) as e:
            print(f"coverage failed: {e}", file=sys.stderr)
            return 1
        return 0

    if a.cmd == "nvdb":
        from .nvdb_extract import extract

        try:
            sources = extract(a.inputs, a.out)
        except (OSError, ValueError) as e:
            print(f"nvdb extract failed: {e}", file=sys.stderr)
            return 1
        total = sum(sum(s.lines.values()) for s in sources)
        print(f"{a.out}: {total} name lines from {len(sources)} files")
        return 0

    print(f"lm-garmin {a.cmd}: not implemented yet – {NOT_YET[a.cmd]}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
