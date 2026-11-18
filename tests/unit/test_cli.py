from lm_garmin import cli


def test_unimplemented_commands_exit_2(capsys):
    assert cli.main(["build"]) == 2
    assert "not implemented" in capsys.readouterr().err
