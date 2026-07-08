import pytest

from Modality_Pipelines.cli import build_parser, dispatch


def parse_args(*args):
    parser = build_parser()
    return parser, parser.parse_args(args)


def test_gui_does_not_require_study(monkeypatch):
    parser, args = parse_args("gui")
    monkeypatch.setattr("Modality_Pipelines.cli.subprocess.call", lambda command: 0)
    assert dispatch(args, parser) == 0


def test_operational_commands_require_study():
    parser, args = parse_args("validate")
    with pytest.raises(SystemExit):
        dispatch(args, parser)


def test_studies_command_does_not_require_study(capsys):
    parser, args = parse_args("studies")
    assert dispatch(args, parser) == 0
    assert "Configured studies" in capsys.readouterr().out
