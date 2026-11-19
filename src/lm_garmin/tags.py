"""Tag schema: Lantmäteriet attributes → OSM tags (style-independent, ADR-0003).

See docs/tag-schema.md. The converter only re-encodes Lantmäteriet semantics; Garmin types,
levels and colours are decided by the mkgmap style.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable

SCHEMA_VERSION = 3

# Columns never carried over: identity/bookkeeping, or redundant with lm:t.
SKIP_COLUMNS = frozenset({"fid", "geom", "objektidentitet", "skapad", "objekttyp", "objekttypnr"})

# Values that mean "no information". Absence of a tag means the same thing.
UNKNOWN_VALUES = frozenset({"", "Ingen information"})

# Convenience aliases understood by mkgmap without extra rules.
ALIASES = {"textstrang": "name", "hojdvarde": "ele", "vardvagnummer": "ref"}

# Attributes where 0 means "not set" and is dropped.
ZERO_IS_UNSET = frozenset({"rotation", "textriktning"})


def tag_key(column: str) -> str:
    """lm:<column>, ASCII-folded (alternativt_manér → lm:alternativt_maner)."""
    folded = unicodedata.normalize("NFKD", column).encode("ascii", "ignore").decode("ascii")
    return f"lm:{folded}"


def format_value(v: object) -> str:
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v))
        return f"{v:.2f}".rstrip("0").rstrip(".")
    return str(v)


def read_columns(all_columns: Iterable[str]) -> list[str]:
    """Columns the converter needs to read for one layer."""
    return [c for c in all_columns if c not in SKIP_COLUMNS or c == "objekttypnr"]


def feature_tags(layer: str, columns: list[str], row: tuple) -> dict[str, str]:
    """Tags for one feature. `row` holds the values of `columns` in the same order."""
    tags = {"lm:l": layer}
    for col, v in zip(columns, row, strict=True):
        if v is None:
            continue
        if col == "objekttypnr":
            tags["lm:t"] = str(int(v))
            continue
        if col in SKIP_COLUMNS:
            continue
        s = format_value(v)
        if s in UNKNOWN_VALUES or (col in ZERO_IS_UNSET and s == "0"):
            continue
        tags[tag_key(col)] = s
        alias = ALIASES.get(col)
        if alias:
            tags[alias] = s
    return tags
