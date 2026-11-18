"""S4: decode built .img files (java/ImgDump.java on mkgmap's reader) and check them.

Checks are run on the *built map*, not on the intermediate data (ADR-0006).
"""

from __future__ import annotations

import collections
import json
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from . import tools

IMGDUMP = Path(__file__).resolve().parents[2] / "java" / "ImgDump.java"


class VerifyError(RuntimeError):
    pass


def norm_type(t: str) -> str:
    """Canonical hex form, so "0x01" (style) and "0x1" (decoder) compare equal."""
    return hex(int(t, 16))


def decode(img: Path) -> Iterator[dict]:
    """Yield decoded features (GeoJSON dicts) from a tile or multi-tile .img."""
    java = tools.find_java()
    if not java:
        raise VerifyError("java not found")
    jar = tools.fetch(tools.TOOLS["mkgmap"])
    p = subprocess.Popen(
        [java, "-cp", str(jar), str(IMGDUMP), str(img)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    assert p.stdout is not None
    for line in p.stdout:
        yield json.loads(line)
    err = p.stderr.read() if p.stderr else ""
    if p.wait() != 0:
        raise VerifyError(f"ImgDump failed on {img}:\n{err[-2000:]}")


@dataclass
class Summary:
    img: str
    tiles: set[str] = field(default_factory=set)
    levels: set[int] = field(default_factory=set)
    counts: collections.Counter = field(
        default_factory=collections.Counter
    )  # (kind, type) @ level 0
    labels: set[str] = field(default_factory=set)

    def types(self, kind: str | None = None) -> set[str]:
        return {t for (k, t) in self.counts if kind is None or k == kind}


def summarize(img: Path, dump: Path | None = None) -> Summary:
    s = Summary(img.name)
    out = dump.open("w", encoding="utf-8") if dump else None
    try:
        for f in decode(img):
            p = f["properties"]
            s.tiles.add(p["tile"])
            s.levels.add(p["level"])
            if p["level"] == 0:
                s.counts[(p["kind"], norm_type(p["type"]))] += 1
            if p["label"]:
                s.labels.add(p["label"])
            if out:
                out.write(json.dumps(f, ensure_ascii=False) + "\n")
    finally:
        if out:
            out.close()
    return s


def check(s: Summary, expect: dict) -> list[str]:
    """Compare a summary with expectations; returns a list of problems (empty = OK).

    expect = {"min_tiles": 1, "types": {"line": ["0x20"], ...}, "labels": ["Lövlund"]}
    """
    problems = []
    if len(s.tiles) < expect.get("min_tiles", 1):
        problems.append(f"{s.img}: {len(s.tiles)} tiles, expected ≥ {expect.get('min_tiles', 1)}")
    for kind, types in expect.get("types", {}).items():
        missing = sorted({norm_type(t) for t in types} - s.types(kind))
        if missing:
            problems.append(f"{s.img}: missing {kind} types {missing}")
    missing_labels = sorted(set(expect.get("labels", [])) - s.labels)
    if missing_labels:
        problems.append(f"{s.img}: missing labels {missing_labels}")
    return problems


def main(imgs: list[Path], expect_path: Path | None, dump: Path | None) -> int:
    expect = json.loads(expect_path.read_text(encoding="utf-8")) if expect_path else {}
    problems = []
    for img in imgs:
        s = summarize(img, dump if len(imgs) == 1 else None)
        kinds = collections.Counter()
        for (k, _), n in s.counts.items():
            kinds[k] += n
        print(
            f"{img.name}: {len(s.tiles)} tiles, levels {sorted(s.levels)}, "
            f"level 0: {dict(kinds)}, {len(s.types())} types, {len(s.labels)} distinct labels"
        )
        problems += check(s, expect)
    for p in problems:
        print(f"FAIL {p}", file=sys.stderr)
    return 1 if problems else 0
