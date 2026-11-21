"""The styles are generated from mapping.csv and cover every Lantmäteriet object type."""

import re
from pathlib import Path

import pytest

from lm_garmin import style_docs, stylegen
from lm_garmin.convert import LAYER_THEME
from lm_garmin.products import PRODUCTS

ROOT = Path(__file__).parents[2]
LAYERS_WITHOUT_TYPES = {"textpunkt", "textlinje", "hojdkurvstext"}


def inventory_types() -> set[tuple[str, str]]:
    """(layer, objekttypnr) from the tables in docs/data-inventory.md."""
    text = (ROOT / "docs" / "data-inventory.md").read_text(encoding="utf-8")
    out, layer = set(), None
    for line in text.splitlines():
        m = re.match(r"#### `(\w+)`", line)
        if m:
            layer = m.group(1)
            continue
        m = re.match(r"\| (\d{4}) \| [^|]+ \| [\d ]+ \|$", line)
        if m and layer:
            out.add((layer, m.group(1)))
    return out


def covered(rules, layer: str, t: str) -> bool:
    return any(r.layer == layer and r.t in (t, "") for r in rules)


def test_inventory_parsed():
    types = inventory_types()
    assert len(types) > 150
    assert ("ovrig_vag", "1848") in types


def test_every_object_type_has_a_rule_or_is_dropped_explicitly():
    rules = stylegen.load(ROOT / "styles" / "topo50" / "mapping.csv")
    inventory = inventory_types()
    missing = sorted(lt for lt in inventory if not covered(rules, *lt))
    assert missing == []
    layers = set(LAYER_THEME)
    assert layers == {layer for layer, _ in inventory} | LAYERS_WITHOUT_TYPES
    assert layers <= {rule.layer for rule in rules}


def test_overlay_covers_all_winter_trails():
    rules = stylegen.load(ROOT / "styles" / "skoter" / "mapping.csv")
    for t in ("1847", "1848"):
        conds = {r.condition for r in rules if r.layer == "ovrig_vag" and r.t == t}
        assert any("Påbjuden" in c for c in conds) and any("=Ja" in c for c in conds)
        assert any("Nej" in c for c in conds) and "" in conds  # "" = Ingen information
    assert covered(rules, "ledintressepunkt_fjall", "1836")


@pytest.mark.parametrize("key", list(PRODUCTS))
def test_generated_files_are_up_to_date(key):
    p = PRODUCTS[key]
    for rel, text in stylegen.generated_files(p.style_dir, p.family_id, p.levels).items():
        on_disk = (p.style_dir / rel).read_text(encoding="utf-8")
        assert on_disk == text, f"{p.style_dir / rel} is stale – run `lm-garmin style generate`"


def test_translation_table_is_up_to_date():
    table = style_docs.TRANSLATION_TABLE.read_text(encoding="utf-8")
    assert table == style_docs.render_translation_table(), (
        "docs/translation-table.md is stale – run `lm-garmin style generate`"
    )


@pytest.mark.parametrize("bad", ["0x11520", "0x10e30", "0x200000"])
def test_invalid_types_rejected(bad):
    with pytest.raises(ValueError):
        stylegen.check_type(bad)


def test_valid_types_accepted():
    for ok in ("0x2800", "0x10e1f", "0x11500", "0x52"):
        stylegen.check_type(ok)


def test_typ_defines_each_used_type():
    rules = stylegen.load(ROOT / "styles" / "topo50" / "mapping.csv")
    typ = stylegen.render_typ(rules, 5750)
    for r in rules:
        if r.kind in ("polygon", "line") or (r.kind == "point" and r.pattern != "none"):
            assert f"Type={r.type}\n" in typ, r
    assert "CodePage=65001" in typ and "FID=5750" in typ


def test_only_index_contours_are_labelled_in_feet():
    rules = stylegen.load(ROOT / "styles" / "topo50" / "mapping.csv")
    contours = [r for r in rules if r.layer == "hojdlinje"]
    labelled = [r for r in contours if r.name]
    assert [r.condition for r in labelled] == ["lm:stodkurva=Ja"]
    assert labelled[0].name == "${ele|conv:m=>ft}"  # Garmin reads contour labels as feet
    assert labelled[0].resolution == "23"  # labels only when zoomed in
    # the same index contour is drawn unlabelled further out (continue → emitted twice)
    unlabelled = [r for r in contours if r.condition == "lm:stodkurva=Ja" and not r.name]
    assert unlabelled and "continue" in unlabelled[0].options


def test_roads_use_standard_garmin_road_types():
    rules = stylegen.load(ROOT / "styles" / "topo50" / "mapping.csv")
    for r in rules:
        if r.layer == "vaglinje":
            assert int(r.type, 16) <= 0x13, f"{r.t} {r.description}: {r.type}"


def test_relabel_overrides_the_generic_name():
    from lm_garmin.stylegen import Rule

    base = dict(
        kind="point",
        layer="textpunkt",
        t="",
        condition="",
        type="0x2800",
        resolution="23",
        description="",
        colour="",
        colour2="",
        width="",
        pattern="none",
        order="",
    )
    rule = Rule(**base, name="${name|subst:naturreservat=>nr}", options="relabel")
    assert "{ set mkgmap:label:1='${name|subst:naturreservat=>nr}' }" in rule.mkgmap_rule()
    assert "{ name '${name}' }" in Rule(**base, name="${name}").mkgmap_rule()
