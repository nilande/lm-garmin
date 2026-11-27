"""The styles are generated from mapping.csv and cover every Lantmäteriet object type."""

import re
from pathlib import Path

import pytest

from lm_garmin import style_docs, stylegen
from lm_garmin.convert import LAYER_THEME, LAYERS_2027
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
    assert layers == {layer for layer, _ in inventory} | LAYERS_WITHOUT_TYPES | LAYERS_2027
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


def test_road_rules_make_only_named_lines_roads():
    """mkgmap does not merge road segments: unnamed lines stay plain lines (#72)."""
    from dataclasses import replace

    from lm_garmin.stylegen import Rule

    rule = Rule(
        kind="line",
        layer="vaglinje",
        t="1806",
        condition="",
        type="0x05",
        resolution="23",
        name="${lm:gatunamn_nvdb}",
        description="",
        colour="",
        colour2="",
        width="",
        pattern="solid",
        order="",
        options="font=small road",
    )
    named, unnamed = rule.mkgmap_rule().splitlines()
    assert named.startswith("lm:l=vaglinje & lm:t=1806 & lm:gatunamn_nvdb=* {")
    assert "set mkgmap:city='${lm:kommun}'" in named
    assert named.endswith("[0x05 road_class=1 road_speed=3 resolution 23]")
    assert unnamed == "lm:l=vaglinje & lm:t=1806 [0x05 resolution 23]"
    with pytest.raises(ValueError, match="needs a name"):
        replace(rule, name="").mkgmap_rule()


def test_street_name_types_use_the_small_font():
    """Street labels competed with town names on the Montana (#71). The device honours TYP
    FontStyle only on lines (label kit, docs/device-testing.md)."""
    rules = stylegen.load(ROOT / "styles" / "topo50" / "mapping.csv")
    typ = stylegen.render_typ(rules, 5750)
    lines = {s.split("\n")[0]: s for s in typ.split("[_line]\n")[1:]}
    named = {r.type for r in rules if r.name == "${lm:gatunamn_nvdb}"}
    assert named
    for t in named:
        assert "FontStyle=SmallFont\n" in lines[f"Type={t}"], t
    assert "FontStyle" not in lines["Type=0x01"]  # motorway shields keep the default font
    assert "FontStyle" not in typ.split("[_line]")[0]  # no point sections are touched


def _rule(**kw):
    base = dict.fromkeys(
        [
            "layer",
            "t",
            "condition",
            "resolution",
            "name",
            "description",
            "colour",
            "colour2",
            "width",
            "pattern",
            "order",
        ],
        "",
    )
    return stylegen.Rule(**{**base, **kw})


@pytest.mark.parametrize("kind,opt", [("line", "font=tiny"), ("point", "font=large")])
def test_invalid_font_options_rejected(kind, opt):
    with pytest.raises(ValueError):
        stylegen.label_style([_rule(kind=kind, type="0x06", options=opt)])


def test_lake_and_terrain_names_are_searchable_and_labelled():
    """The 0x6500/0x6600 search points must `continue`, or the 0x2800 label rules never
    see lake and terrain names (lost since v0.2.0 by a value in the wrong column)."""
    rules = stylegen.load(ROOT / "styles" / "topo50" / "mapping.csv")
    for kategori, t in (("Hydrografi", "0x6500"), ("Terrängnamn", "0x6600")):
        (search,) = [r for r in rules if r.type == t and kategori in r.condition]
        assert "continue" in search.options.split()
        assert search.mkgmap_rule().endswith("continue]")
    labels = [r for r in rules if r.layer == "textpunkt" and r.type == "0x2800"]
    assert any("textkategori" not in r.condition for r in labels)  # generic name rules


def test_order_must_be_numeric(tmp_path):
    csv_file = tmp_path / "mapping.csv"
    header = (
        "kind,layer,t,condition,type,resolution,name,description,"
        "colour,colour2,width,pattern,order,options\n"
    )
    csv_file.write_text(header + "point,textpunkt,,,0x2800,24,${name},X,,,,label,continue\n")
    with pytest.raises(ValueError, match="order must be a number"):
        stylegen.load(csv_file)


def test_night_colours_darken_fills_and_brighten_inks():
    import colorsys

    def lightness(c):
        return colorsys.rgb_to_hls(*(int(c[i : i + 2], 16) / 255 for i in (1, 3, 5)))[1]

    for day in ("#FFFFF2", "#CBEAFF", "#D4EEB7", "#E88A2E", "#464646"):
        assert lightness(stylegen.night(day, "fill")) <= 0.32
    # lighter by day stays lighter by night
    assert lightness(stylegen.night("#FFFFF2", "fill")) > lightness(
        stylegen.night("#E88A2E", "fill")
    )
    for day in ("#000000", "#333333", "#0080E6", "#C44982", "#D4B0F0", "#A0A0A0"):
        assert lightness(stylegen.night(day, "ink")) >= 0.55
    assert stylegen.night("none", "fill") == "none"
    with pytest.raises(ValueError):
        stylegen.night("#000000", "glow")


def test_typ_has_night_colours_for_every_drawn_entry():
    for style in ("topo50", "skoter", "skoter-osm"):
        typ = stylegen.render_typ(stylegen.load(ROOT / "styles" / style / "mapping.csv"), 5750)
        for section in typ.split("[_")[1:]:
            kind, body = section.split("]\n", 1)
            if kind in ("polygon", "line"):
                xpm = re.search(r'Xpm="(\d+) (\d+) (\d+) ', body)
                assert xpm and int(xpm[3]) in (2, 4), body
            elif kind == "point" and '"a c none"' not in body:
                assert "DayXpm=" in body and "NightXpm=" in body, body


def test_night_pattern_marks_sit_between_fill_and_ink():
    import colorsys

    def lightness(c):
        return colorsys.rgb_to_hls(*(int(c[i : i + 2], 16) / 255 for i in (1, 3, 5)))[1]

    for day in ("#707070", "#B2E39C", "#40BAFF", "#C04040"):
        fill, mark, ink = (stylegen.night(day, role) for role in ("fill", "mark", "ink"))
        assert lightness(fill) < lightness(mark) < lightness(ink)


def _rule(**kw):
    from lm_garmin.stylegen import Rule

    base = dict(
        kind="line",
        layer="ovrig_vag",
        t="1846",
        condition="",
        type="0x0f",
        resolution="20",
        name="",
        description="",
        colour="",
        colour2="",
        width="",
        pattern="solid",
        order="",
        options="route access=foot",
    )
    return Rule(**{**base, **kw})


def test_route_rules_make_paths_routable_for_the_allowed_classes_only():
    """Hiking trails are roads for walkers only (#28)."""
    (line,) = _rule().mkgmap_rule().splitlines()
    assert line.startswith("lm:l=ovrig_vag & lm:t=1846 {")
    assert "set mkgmap:car=no" in line and "set mkgmap:bicycle=no" in line
    assert "mkgmap:foot" not in line
    assert line.endswith("[0x0f road_class=0 road_speed=0 resolution 20]")


def test_route_rules_with_road_keep_the_address_on_named_lines():
    """Every street is routable; named ones also carry city and region (#72, #28)."""
    named, unnamed = (
        _rule(
            layer="vaglinje",
            t="1811",
            type="0x06",
            resolution="23",
            name="${lm:gatunamn_nvdb}",
            options="font=small road route",
        )
        .mkgmap_rule()
        .splitlines()
    )
    assert named.startswith("lm:l=vaglinje & lm:t=1811 & lm:gatunamn_nvdb=* {")
    assert "set mkgmap:city='${lm:kommun}'" in named
    assert unnamed == "lm:l=vaglinje & lm:t=1811 [0x06 road_class=0 road_speed=2 resolution 23]"


def test_route_rules_reject_unroutable_types_and_unknown_access():
    with pytest.raises(ValueError, match="0x01–0x3f"):
        _rule(type="0x10e03").mkgmap_rule()
    with pytest.raises(ValueError, match="access"):
        _rule(options="route access=hiker").mkgmap_rule()


def test_walkers_and_cyclists_can_route_on_paths_but_not_on_motorways():
    rules = stylegen.load(ROOT / "styles" / "topo50" / "mapping.csv")
    route = {(r.layer, r.t): r for r in rules if "route" in r.options.split()}
    for t in ("1623", "1624", "1625", "1628", "1842", "1846", "1847"):
        assert ("ovrig_vag", t) in route, t
    assert ("ovrig_vag", "1848") not in route  # winter trails cross lakes and bogs
    motorway = route[("vaglinje", "1801")].mkgmap_rule()
    assert "set mkgmap:foot=no" in motorway and "set mkgmap:bicycle=no" in motorway
