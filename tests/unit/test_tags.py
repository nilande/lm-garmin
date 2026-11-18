from lm_garmin.tags import feature_tags, read_columns, tag_key


def test_tag_key_folds_to_ascii():
    assert tag_key("alternativt_manér") == "lm:alternativt_maner"


def test_unknown_and_zero_values_are_dropped():
    cols = ["objekttypnr", "skoterkorning_tillaten", "ruskmarkering", "rotation"]
    tags = feature_tags("ovrig_vag", cols, (1848, "Påbjuden", "Ingen information", 0.0))
    assert tags == {"lm:l": "ovrig_vag", "lm:t": "1848", "lm:skoterkorning_tillaten": "Påbjuden"}


def test_aliases():
    tags = feature_tags("hojdlinje", ["objekttypnr", "hojdvarde", "stodkurva"], (2401, 625.0, "Ja"))
    assert tags["ele"] == tags["lm:hojdvarde"] == "625"
    assert tags["lm:stodkurva"] == "Ja"
    t = feature_tags("textpunkt", ["textstrang"], ("Våjhtja",))
    assert t["name"] == "Våjhtja"


def test_floats_are_compact():
    t = feature_tags("textpunkt", ["textriktning"], (42.3900001,))
    assert t["lm:textriktning"] == "42.39"


def test_read_columns_skips_bookkeeping():
    cols = ["objektidentitet", "skapad", "objekttypnr", "objekttyp", "hojdvarde"]
    assert read_columns(cols) == ["objekttypnr", "hojdvarde"]
