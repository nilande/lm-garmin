"""Generate a mkgmap style and TYP source from a style's mapping.csv.

`styles/<name>/mapping.csv` is the single source of truth for one style: one row per rule
(Lantmäteriet layer/object type → Garmin type, level, label and TYP look). The generator
writes the mkgmap rule files (`points`, `lines`, `polygons`, …) and `typ/<name>.txt`.
Generated files carry a header and are checked by a test to be up to date.

Columns: kind (point|line|polygon|drop), layer, t (objekttypnr, empty = any), condition
(extra mkgmap expression), type, resolution, name (label expression, e.g. ${ele}),
description, colour, colour2, width,
pattern (solid|solid-bitmap|dash|dash-long|dot|label|stripe|hatch|hatch-sparse|dots|mottled|
icon|none; for points `label` draws the label without a symbol; for bitmap lines colour2
fills the gaps),
order (polygon draw order 1–8), options (`continue`: keep matching later rules, so one feature
can be emitted twice, e.g. unlabelled at one resolution range and labelled at another;
`outline`: pass the layer and object type to inner rings of a multipolygon for a line rule;
`relabel`: replace the label already set from `name`, e.g. to abbreviate it;
`font=small|normal|large`: label size of a line type – a TYP setting, so it applies to every
rule of the type. The Montana 700 ignores TYP font size and label colour on points and label
colour on lines, so only line font sizes are supported; see docs/device-testing.md).
A resolution may be a range, e.g. `20-21`.

Night colours are not in mapping.csv: `night()` derives them from the day colours (#92).
"""

from __future__ import annotations

import colorsys
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
        if self.name and "relabel" in self.options.split():
            # `name` never replaces a label that is already set (the generic name=* rule sets
            # it first); write the label tag directly to transform the name.
            action = f" {{ set mkgmap:label:1='{self.name}' }}"
        else:
            action = f" {{ name '{self.name}' }}" if self.name else ""
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
        # A value one column off (e.g. `continue` in `order`) is silently ignored by mkgmap
        # rules: lake and terrain names lost their labels that way in v0.2.0.
        if rule.order and not rule.order.isdigit():
            raise ValueError(f"{mapping}:{i}: order must be a number, got {rule.order!r}")
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

# Night colours (#92) are derived from the day colours, so mapping.csv stays the only source.
# The device switches to them in night mode (Color Mode Night, or Auto after dark).
# - "fill": area backgrounds and the fill behind line and point symbols. Darkened, keeping
#   the order of lightness so light day areas stay the lighter night areas.
#   The colourfulness (chroma) is reduced and capped, so open land, fields and built-up areas
#   become muted greys and browns instead of olive and rust; blue keeps more, so water and
#   wet ground stay recognisably blue.
# - "mark": the marks of area patterns (hatch, dots, stripes). A little lighter than a dark
#   fill, so patterns stay visible without glaring on the dark map.
# - "ink": lines and point symbols. Brightened to stand out on the dark fills, keeping hue and
#   most of the saturation; very dark and very light inks end up lightest.
NIGHT_FILL_L = (0.10, 0.22)  # lightness = a + b * day lightness
NIGHT_FILL_C = (0.5, 0.10, 0.30)  # share of the day chroma (not for blue), cap, cap for blue
NIGHT_MARK_DL = 0.15  # mark lightness = fill lightness + this
NIGHT_INK_L = (0.55, 0.30)  # lightness = a + b * |2 * day lightness - 1|


def night(colour: str, role: str) -> str:
    """Night version of a `#RRGGBB` day colour; `none` stays transparent."""
    if colour.lower() == "none":
        return colour
    r, g, b = (int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5))
    h, lum, s = colorsys.rgb_to_hls(r, g, b)
    if role in ("fill", "mark"):
        share, cap, blue_cap = NIGHT_FILL_C
        chroma = s * (1 - abs(2 * lum - 1))
        blue = 0.5 <= h <= 0.7
        chroma = min(chroma if blue else chroma * share, blue_cap if blue else cap)
        lum = NIGHT_FILL_L[0] + NIGHT_FILL_L[1] * lum
        if role == "mark":
            lum, chroma = lum + NIGHT_MARK_DL, chroma * 1.5
        s = min(1.0, chroma / (1 - abs(2 * lum - 1)))
    elif role == "ink":
        lum, s = NIGHT_INK_L[0] + NIGHT_INK_L[1] * abs(2 * lum - 1), s * 0.85
    else:
        raise ValueError(role)
    return "#" + "".join(f"{round(c * 255):02X}" for c in colorsys.hls_to_rgb(h, lum, s))


NIGHT_TAGS = {"a": "3", "b": "4"}


def _xpm(rows: list[str], colours: dict[str, str], roles: dict[str, str] | None = None) -> str:
    """An XPM block; with `roles` (tag → fill|ink) the night colours follow the day ones.

    The device draws the rows with the day tags and swaps in the night colours itself.
    """
    colours = dict(colours)
    if roles:
        colours |= {NIGHT_TAGS[k]: night(colours[k], role) for k, role in roles.items()}
    w, h = len(rows[0]), len(rows)
    head = f'Xpm="{w} {h} {len(colours)} 1"\n'
    cols = "".join(f'"{k} c {v}"\n' for k, v in colours.items())
    return head + cols + "".join(f'"{r}"\n' for r in rows)


def _solid(day: str, role: str) -> str:
    return f'Xpm="0 0 2 0"\n"a c {day}"\n"b c {night(day, role)}"\n'


def _pattern(kind: str) -> list[str]:
    if kind == "stripe":
        return [("a" * 32 if y % 4 == 0 else "b" * 32) for y in range(32)]
    if kind == "hatch-sparse":
        # Half the density of `hatch`, for large areas drawn over terrain (#14).
        return ["".join("a" if (x + y) % 16 == 0 else "b" for x in range(32)) for y in range(32)]
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
        s += _solid(r.colour, "fill")
    else:
        bg = r.colour2 and r.colour or "none"
        fg = r.colour2 or r.colour
        s += _xpm(_pattern(r.pattern), {"a": fg, "b": bg}, {"a": "mark", "b": "fill"})
    return s + "[end]\n"


FONTS = {"small": "SmallFont", "normal": "NormalFont", "large": "LargeFont"}


def label_style(rules: list[Rule]) -> dict[tuple[str, str], str]:
    """TYP `FontStyle` line per line type, from `font=` options."""
    out: dict[tuple[str, str], str] = {}
    for r in rules:
        for opt in r.options.split():
            key, _, value = opt.partition("=")
            if key != "font":
                continue
            if r.kind != "line":
                raise ValueError(f"{r.description}: font= works only on lines on the device")
            if value not in FONTS:
                raise ValueError(f"{r.description}: font must be one of {sorted(FONTS)}")
            out[(r.kind, r.type)] = f"FontStyle={FONTS[value]}\n"
    return out


def _typ_line(r: Rule, label: str = "") -> str:
    w = max(int(r.width or 1), 1)
    s = f"[_line]\nType={r.type}\nString1=0x04,{r.description}\n" + label
    if r.pattern == "label":
        # Label-only line: mkgmap rejects a fully transparent line, so one faint pixel in 32.
        s += "UseOrientation=Y\n" + _xpm(
            ["a" + "b" * 31], {"a": r.colour, "b": "none"}, {"a": "ink", "b": "fill"}
        )
    elif r.pattern in ("dash", "dash-long", "dot", "solid-bitmap"):
        length, period = {"dash": (5, 8), "dash-long": (10, 16), "dot": (2, 8)}.get(
            r.pattern, (7, 8)
        )
        dash = "".join("a" if i % period < length else "b" for i in range(32))
        rows = [dash] * w
        if r.pattern == "solid-bitmap":
            # Keep a continuous centre while using the same bitmap format as dashed lines.
            rows[w // 2] = "a" * 32
        # Garmin line bitmaps have two colours: with colour2 the gaps are filled (a two-tone
        # line that stays visible on any background, #57); without, they are transparent.
        s += "UseOrientation=Y\n" + _xpm(
            rows, {"a": r.colour, "b": r.colour2 or "none"}, {"a": "ink", "b": "fill"}
        )
    elif r.colour2:
        s += f"LineWidth={w}\nBorderWidth=1\n" + _xpm_solid_border(r.colour, r.colour2)
    else:
        s += f"LineWidth={w}\n" + _solid(r.colour, "ink")
    return s + "[end]\n"


def _xpm_solid_border(line: str, border: str) -> str:
    """A solid line with a border: day line and border, then night line and border."""
    colours = (line, border, night(line, "ink"), night(border, "fill"))
    return 'Xpm="0 0 4 0"\n' + "".join(
        f'"{k} c {c}"\n' for k, c in zip("ab34", colours, strict=True)
    )


def _typ_point(r: Rule) -> str:
    if r.pattern == "label":
        # Label without a symbol: replaces the device's default dot with a transparent pixel.
        icon = _xpm(["a"], {"a": "none"})
    else:
        if r.colour2:
            # Square with a 2 px ring in colour2, to stand out on a line of the same colour (#57).
            n = max(int(r.width or 5), 5)
            rows = ["b" * n, "b" * n, *("bb" + "a" * (n - 4) + "bb" for _ in range(n - 4))]
            rows += ["b" * n, "b" * n]
            day, roles = {"a": r.colour, "b": r.colour2}, {"a": "ink", "b": "fill"}
        else:
            n = max(int(r.width or 5), 1)
            rows, day, roles = ["a" * n] * n, {"a": r.colour}, {"a": "ink"}
        # Points take a separate night icon instead of night colours in one XPM.
        night_cols = {k: night(c, roles[k]) for k, c in day.items()}
        icon = "Day" + _xpm(rows, day) + "Night" + _xpm(rows, night_cols)
    return f"[_point]\nType={r.type}\nString1=0x04,{r.description}\n" + icon + "[end]\n"


def source_tags(rules: list[Rule]) -> dict[str, set[str]]:
    """Tags each layer's rules read in conditions and labels (besides lm:l and lm:t)."""
    out: dict[str, set[str]] = {}
    for r in rules:
        text = f"{r.condition} {r.name}"
        tags = {f"lm:{t}" for t in re.findall(r"lm:(\w+)", text)} - {"lm:l", "lm:t"}
        tags |= {a for a in ("ref", "name", "ele") if re.search(rf"(?<![\w:]){a}\b", text)}
        if tags:
            out.setdefault(r.layer, set()).update(tags)
    return out


def typ_rules(rules: list[Rule]) -> dict[tuple[str, str], Rule]:
    """Return the first visual definition for each geometry and Garmin type."""
    seen = {}
    for r in rules:
        if r.kind in KINDS:
            seen.setdefault((r.kind, r.type), r)
    return seen


def render_typ(rules: list[Rule], family_id: int, product_id: int = 1) -> str:
    seen = typ_rules(rules)
    labels = label_style(rules)
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
            out.append(_typ_line(r, labels.get((kind, r.type), "")))
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
