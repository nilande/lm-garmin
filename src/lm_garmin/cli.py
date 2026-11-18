"""lm-garmin: build Garmin .img maps from Lantmäteriet's Topografi 50."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, region, tools

NOT_YET = {
    "build": "S1–S3: build gmapsupp.img for a region (issue #7)",
    "verify": "S4: decode a built .img and run the checks (issue #9)",
}


def _add_region_args(p: argparse.ArgumentParser) -> None:
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--bbox", help="xmin,ymin,xmax,ymax in SWEREF 99 TM (EPSG:3006)")
    g.add_argument("--bbox-wgs84", help="lon_min,lat_min,lon_max,lat_max")
    g.add_argument("--region", choices=["sweden"], help="named region")


def _region_from_args(a: argparse.Namespace, gpkg_dir: Path) -> region.Region:
    if a.bbox:
        return region.from_bbox(a.bbox)
    if a.bbox_wgs84:
        return region.from_wgs84(a.bbox_wgs84)
    return region.sweden(gpkg_dir)


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

    c = sub.add_parser("convert", help="S1: convert GeoPackages to OSM PBF for a region")
    _add_region_args(c)
    c.add_argument("--gpkg-dir", type=Path, help="GeoPackages (default: <cache>/gpkg)")
    c.add_argument("--out", type=Path, help="output folder (default: <cache>/pbf/<region>)")
    c.add_argument("--jobs", type=int, help="parallel themes (default: CPU count)")

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

    if a.cmd == "convert":
        from .convert import convert

        gpkg_dir = a.gpkg_dir or cache / "gpkg"
        reg = _region_from_args(a, gpkg_dir)
        out = a.out or cache / "pbf" / reg.id
        stats = convert(gpkg_dir, reg, out, a.jobs)
        total = sum(s.features for s in stats)
        print(f"{total} features in {len(stats)} themes → {out}")
        return 0

    print(f"lm-garmin {a.cmd}: not implemented yet – {NOT_YET[a.cmd]}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
