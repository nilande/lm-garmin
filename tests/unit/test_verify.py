import json

from lm_garmin import cli, verify


def test_verify_fails_only_for_budgeted_class_and_reports_counts(tmp_path, monkeypatch, capsys):
    features = [
        {"tile": "test", "level": 0, "kind": "line", "type": "0x20", "label": ""},
        {"tile": "test", "level": 4, "kind": "polygon", "type": "0x50", "label": ""},
        {"tile": "test", "level": 4, "kind": "polygon", "type": "0x50", "label": ""},
    ]
    monkeypatch.setattr(verify, "decode", lambda _: iter({"properties": p} for p in features))
    expect = tmp_path / "expect.json"
    expect.write_text(
        json.dumps({"types": {"line": ["0x20"]}, "max_features_by_level": {"4": {"polygon": 1}}})
    )
    args = ["verify", "map.img", "--level-counts", "--expect", str(expect)]
    assert cli.main(args) == 1
    result = capsys.readouterr()
    assert "level 0: point=0, line=1, polygon=0" in result.out
    assert "level 4: point=0, line=0, polygon=2" in result.out
    assert "level 4 polygon count 2 exceeds budget 1" in result.err


def test_verify_rejects_missing_budgeted_levels():
    expect = {"max_features_by_level": {"4": {"line": 0}}}
    problems = verify.check(verify.Summary("map.img", tiles={"test"}), expect)
    assert problems == ["map.img: missing budgeted level 4"]
