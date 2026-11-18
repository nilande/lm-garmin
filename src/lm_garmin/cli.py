"""Command line interface. Most commands are placeholders until milestone M1."""

from __future__ import annotations

import argparse
import sys

from . import __version__, tools

NOT_YET = {
    "unpack": "S0: unpack the delivery zips to the local cache",
    "build": "S1–S3: build gmapsupp.img for a region",
    "verify": "S4: decode a built .img and run the checks",
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lm-garmin", description=__doc__)
    p.add_argument("--version", action="version", version=f"lm-garmin {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("tools", help="manage pinned external tools (mkgmap, splitter)")
    tsub = t.add_subparsers(dest="tools_cmd", required=True)
    tsub.add_parser("fetch", help="download and verify mkgmap and splitter")
    tsub.add_parser("path", help="print paths of java and the tool jars")

    for name, text in NOT_YET.items():
        sub.add_parser(name, help=f"{text} (not implemented yet)")

    args = p.parse_args(argv)

    if args.cmd == "tools":
        if args.tools_cmd == "fetch":
            for tool in tools.TOOLS.values():
                print(f"{tool.name} {tool.version}: {tools.fetch(tool)}")
        else:
            print(f"java: {tools.find_java() or 'NOT FOUND'}")
            for tool in tools.TOOLS.values():
                jar = tools.tools_dir() / tool.jar
                print(f"{tool.name}: {jar if jar.exists() else 'not fetched'}")
        return 0

    print(f"lm-garmin {args.cmd}: not implemented yet – {NOT_YET[args.cmd]}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
