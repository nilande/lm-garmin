import pytest

from lm_garmin import cli


def test_build_requires_a_region():
    with pytest.raises(SystemExit) as e:
        cli.main(["build"])
    assert e.value.code == 2


def test_version(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--version"])
    assert "lm-garmin" in capsys.readouterr().out
