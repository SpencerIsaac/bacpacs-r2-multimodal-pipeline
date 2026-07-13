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


def test_doctor_command_does_not_require_study(capsys):
    parser, args = parse_args("doctor")
    assert dispatch(args, parser) == 0
    assert "BACPACS environment check" in capsys.readouterr().out

def test_validate_output_uses_compact_manifest_summary(monkeypatch, capsys):
    import pandas as pd
    import Modality_Pipelines.common.manifest as manifest_module

    manifest = pd.DataFrame(
        [
            {
                "file_path": r"Y:\long\folder\R1_001\1. Baseline\Cosmed\bad file.xlsx",
                "file_name": "bad file.xlsx",
                "participant_number": None,
                "visit": None,
                "modality": None,
                "test": None,
                "condition": None,
                "speed": None,
                "trial": None,
                "status": "review",
                "issues": "filename: does not match pattern",
            }
        ]
    )

    monkeypatch.setattr(manifest_module, "validate_study_files", lambda **kwargs: manifest)
    parser, args = parse_args("validate", "--study", "R1")
    assert dispatch(args, parser) == 2
    output = capsys.readouterr().out
    assert "Manifest rows (showing 1 of 1)" in output
    assert "identity: participant=?" in output
    assert "filename: does not match pattern" in output
    assert "file_path" not in output

def test_help_shows_command_usage(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--help"])
    output = capsys.readouterr().out
    assert "usage: bacpacs <command> [options]" in output
    assert "bacpacs validate --study R2" in output


def test_validate_help_shows_full_command_usage(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["validate", "--help"])
    output = capsys.readouterr().out
    assert "usage: bacpacs validate --study {R1,R2} [filters] [options]" in output
