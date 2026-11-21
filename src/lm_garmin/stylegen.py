"""Generate a mkgmap style and TYP source from a style's mapping.csv.

`styles/<name>/mapping.csv` is the single source of truth for one style: one row per rule
(Lantmäteriet layer/object type → Garmin type, level, label and TYP look). The generator
writes the mkgmap rule files (`points`, `lines`, `polygons`, …) and `typ/<name>.txt`.
Generated files carry a header and are checked by a test to be up to date.

Columns: kind (point|line|polygon|drop), layer, t (objekttypnr, empty = any), condition
(extra mkgmap expression), type, resolution, name (label expression, e.g. ${ele}; alternatives
separated by `|` take the first whose tags are set, e.g. `${ref}|${lm:gatunamn_nvdb}`),
description, colour, colour2, width,
pattern (solid|solid-bitmap|dash|dot|label|stripe|hatch|dots|mottled|icon|none),
order (polygon draw order 1–8), options (`continue`: keep matching later rules, so one feature
can be emitted twice, e.g. unlabelled at one resolution range and labelled at another;
`outline`: pass the layer and object type to inner rings of a multipolygon for a line rule).
A resolution may be a range, e.g. `20-21`.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, replace
from pathlib import Path

HEADER = "# GENERATED from mapping.csv by `lm-garmin style generate` – do not edit.\n"
KINDS = ("point", "line", "polygon")
DEFAULT_LEVELS = "0:24, 1:23, 2:22, 3:21, 4:20, 5:18, 6:16"


@dataclass(frozen=True)
class Rule:
    kind: str
    layer: str
    t: str
    condition: str
    type: str
    resolution: str
    name: str
    description: str
    colour: str
    colour2: str
    width: str
    pattern: str
    order: str
    options: str = ""

    def expression(self) -> str:
        parts = [f"lm:l={self.layer}"]
        if self.t:
            parts.append(f"lm:t={self.t}")
        if self.condition:
            parts.append(f"({self.condition})")
        return " & ".join(parts)

    def mkgmap_rule(self) -> str:
        # `${ref}|${name}`: the first alternative whose tags are all set (mkgmap syntax).
        # A `|` inside `${…}` is an mkgmap filter (`${ele|conv:m=>ft}`), not an alternative.
        alternatives = " | ".join(f"'{n.strip()}'" for n in re.split(r"\|(?![^{]*\})", self.name))
        action = f" {{ name {alternatives} }}" if self.name else ""
        cont = " continue" if "continue" in self.options.split() else ""
        return f"{self.expression()}{action} [{self.type} resolution {self.resolution}{cont}]"


def check_type(type_: str, where: str = "") -> None:
    """Garmin extended types are 0x1TTSS with subtype SS ≤ 0x1f (mkgmap rejects larger)."""
    v = int(type_, 16)
    if v >= 0x10000:
        if v > 0x1FFFF or (v & 0xFF) > 0x1F:
            raise ValueError(f"{where}: invalid extended type {type_} (subtype must be ≤ 0x1f)")
    elif v > 0xFFFF:
        raise ValueError(f"{where}: invalid type {type_}")


def load(mapping: Path) -> list[Rule]:
    lines = [
        ln
        for ln in mapping.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    rows = list(csv.DictReader(lines))
    rules = []
    for i, r in enumerate(rows, start=2):
        r = {k: (v or "").strip() for k, v in r.items() if k is not None}
        rule = Rule(**r)
        if rule.kind not in (*KINDS, "drop"):
            raise ValueError(f"{mapping}:{i}: unknown kind {rule.kind!r}")
        if rule.kind != "drop":
            if not (rule.type and rule.resolution):
                raise ValueError(f"{mapping}:{i}: type and resolution are required")
            check_type(rule.type, f"{mapping}:{i}")
        rules.append(rule)
    return rules


def render_rules(rules: list[Rule], kind: str) -> str:
    out = [HEADER]
    if kind in ("point", "line"):
        out.append("name=* { name '${name}' }\n")
    for r in rules:
        if r.kind == kind:
            out.append(r.mkgmap_rule() + "\n")
    return "".join(out)


def render_relations(rules: list[Rule]) -> str:
    # mkgmap already sends the outer rings of a multipolygon to the line rules.
    # Tag inner rings so the boundaries of enclaves can be drawn as well.
    return HEADER + "".join(
        f"type=multipolygon & {r.expression()} "
        "{ apply role=inner { set lm:l='${lm:l}'; set lm:t='${lm:t}'; } }\n"
        for r in rules
        if r.kind == "line" and "outline" in r.options.split()
    )


# ---------------------------------------------------------------- TYP


def _xpm(rows: list[str], colours: dict[str, str]) -> str:
    w, h = len(rows[0]), len(rows)
    head = f'Xpm="{w} {h} {len(colours)} 1"\n'
    cols = "".join(f'"{k} c {v}"\n' for k, v in colours.items())
    return head + cols + "".join(f'"{r}"\n' for r in rows)


def _pattern(kind: str) -> list[str]:
    if kind == "stripe":
        return [("a" * 32 if y % 4 == 0 else "b" * 32) for y in range(32)]
    if kind == "hatch":
        return ["".join("a" if (x + y) % 8 == 0 else "b" for x in range(32)) for y in range(32)]
    if kind == "dots":
        return [
            "".join("a" if x % 6 == 0 and y % 6 == 0 else "b" for x in range(32)) for y in range(32)
        ]
    if kind == "mottled":
        # Small, offset patches leave the underlying land-cover colour visible.
        rows = [["b"] * 32 for _ in range(32)]
        patches = (
            (2, 3, (2, 4, 3)),
            (12, 1, (3, 5, 4, 2)),
            (24, 4, (2, 3, 2)),
            (8, 10, (2, 4, 3)),
            (19, 11, (3, 5, 4, 2)),
            (27, 15, (2, 3)),
            (1, 18, (3, 4, 2)),
            (13, 21, (2, 4, 3, 2)),
            (23, 25, (3, 4, 3)),
            (4, 27, (2, 4, 2)),
        )
        for x, y, widths in patches:
            max_width = max(widths)
            for dy, width in enumerate(widths):
                start = x + (max_width - width + dy % 2) // 2
                rows[y + dy][start : start + width] = "a" * width
        return ["".join(row) for row in rows]
    raise ValueError(kind)


def _typ_polygon(r: Rule) -> str:
    s = f"[_polygon]\nType={r.type}\nString1=0x04,{r.description}\n"
    if r.pattern in ("solid", ""):
        s += f'Xpm="0 0 1 0"\n"a c {r.colour}"\n'
    else:
        bg = r.colour2 and r.colour or "none"
        fg = r.colour2 or r.colour
        s += _xpm(_pattern(r.pattern), {"a": fg, "b": bg})
    return s + "[end]\n"


def _typ_line(r: Rule) -> str:
    w = max(int(r.width or 1), 1)
    s = f"[_line]\nType={r.type}\nString1=0x04,{r.description}\n"
    if r.pattern == "label":
        # Label-only line: mkgmap rejects a fully transparent line, so one faint pixel in 32.
        s += "UseOrientation=Y\n" + _xpm(["a" + "b" * 31], {"a": r.colour, "b": "none"})
    elif r.pattern in ("dash", "dot", "solid-bitmap"):
        length = {"dash": 5, "dot": 2, "solid-bitmap": 7}[r.pattern]
        dash = "".join("a" if i % 8 < length else "b" for i in range(32))
        rows = [dash] * w
        if r.pattern == "solid-bitmap":
            # Keep a continuous centre while using the same bitmap format as dashed lines.
            rows[w // 2] = "a" * 32
        s += "UseOrientation=Y\n" + _xpm(rows, {"a": r.colour, "b": "none"})
    elif r.colour2:
        s += f'LineWidth={w}\nBorderWidth=1\nXpm="0 0 2 0"\n"a c {r.colour}"\n"b c {r.colour2}"\n'
    else:
        s += f'LineWidth={w}\nXpm="0 0 1 0"\n"a c {r.colour}"\n'
    return s + "[end]\n"


def _typ_point(r: Rule) -> str:
    n = max(int(r.width or 5), 1)
    rows = ["a" * n] * n
    return (
        f"[_point]\nType={r.type}\nString1=0x04,{r.description}\n"
        + _xpm(rows, {"a": r.colour})
        + "[end]\n"
    )


def typ_rules(rules: list[Rule]) -> dict[tuple[str, str], Rule]:
    """Return the first visual definition for each geometry and Garmin type."""
    seen = {}
    for r in rules:
        if r.kind in KINDS:
            seen.setdefault((r.kind, r.type), r)
    return seen


def render_typ(rules: list[Rule], family_id: int, product_id: int = 1) -> str:
    seen = typ_rules(rules)
    out = [
        HEADER.replace("#", ";"),
        f"[_id]\nFID={family_id}\nProductCode={product_id}\nCodePage=65001\n[end]\n",
    ]
    polys = [r for (k, _), r in seen.items() if k == "polygon"]
    if polys:
        order = "".join(f"Type={r.type},{r.order or 1}\n" for r in polys)
        out.append(f"[_drawOrder]\n{order}[end]\n")
    for (kind, _), r in seen.items():
        if kind == "polygon":
            out.append(_typ_polygon(r))
        elif kind == "line":
            out.append(_typ_line(r))
        elif r.pattern != "none":
            out.append(_typ_point(r))
    return "\n".join(out)


# ---------------------------------------------------------------- files


def _replace_polygon_levels(rules: list[Rule], resolutions: tuple[int, ...]) -> list[Rule]:
    result = []
    for rule in rules:
        if rule.kind != "polygon" or rule.layer not in {"mark", "sankmark"}:
            result.append(rule)
            continue
        start, _, end = rule.resolution.partition("-")
        low, high = int(start), int(end or "24")
        excluded = sorted(res for res in resolutions if low <= res <= high)
        if not excluded:
            result.append(rule)
            continue
        limits = [low - 1, *excluded, high + 1]
        bands = [(a + 1, b - 1) for a, b in zip(limits, limits[1:], strict=False) if a + 1 < b]
        for index, (start, end) in enumerate(bands):
            # Emit every surviving band before advancing to the next style rule.
            options = rule.options
            if index < len(bands) - 1 and "continue" not in options.split():
                options = f"{options} continue".strip()
            result.append(replace(rule, resolution=f"{start}-{end}", options=options))
    return result


def generated_files(
    style_dir: Path,
    family_id: int,
    levels: str = DEFAULT_LEVELS,
    *,
    overview_resolutions: tuple[int, ...] = (),
) -> dict[str, str]:
    rules = load(style_dir / "mapping.csv")
    name = style_dir.name
    return {
        "version": "0\n",
        "info": f"{HEADER}version 1\nsummary: lm-garmin style '{name}'\n",
        "options": f"{HEADER}levels = {levels}\n",
        "points": render_rules(rules, "point"),
        "lines": render_rules(rules, "line"),
        "polygons": render_rules(_replace_polygon_levels(rules, overview_resolutions), "polygon"),
        "relations": render_relations(rules),
        f"typ/{name}.txt": render_typ(rules, family_id),
    }


def generate(style_dir: Path, family_id: int, levels: str = DEFAULT_LEVELS) -> list[Path]:
    written = []
    for rel, text in generated_files(style_dir, family_id, levels).items():
        p = style_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        written.append(p)
    return written
