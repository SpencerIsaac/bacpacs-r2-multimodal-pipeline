"""Full-pipeline integration smoke test using mock subject-data files."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from Modality_Pipelines.common.analysis_registry import list_available_analyses, resolve_analysis_spec

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass
from Modality_Pipelines.common.manifest import register_raw_files, validate_study_files
from Modality_Pipelines.common.processing import run_modality_processing
from Modality_Pipelines.common.study_config import load_study_config
from Modality_Pipelines.common.table_registry import get_stage_registry, get_supported_studies


def make_mock_subject_data(root: Path, study: str) -> Path:
    config = load_study_config(study)
    participant = f"{config.participant_prefix}_001"
    baseline = config.visits["baseline"]["folder"]
    files = {
        "delsys": "R{study_num}_001_BL_delsys_SSV1_noAFO.mat",
        "xsens": "R{study_num}_001_BL_xsens_SSV1_noAFO.mvnx",
        "gaitrite": "R{study_num}_001_BL_GR_SSV1_noAFO.xlsx",
        "cosmed": "R{study_num}_001_BL_cosmed_SSV1_noAFO.xlsx",
    }
    study_num = study.removeprefix("R")
    for modality, file_template in files.items():
        folder = root / participant / baseline / config.modalities[modality]["folder"]
        folder.mkdir(parents=True, exist_ok=True)
        (folder / file_template.format(study_num=study_num)).write_text("mock", encoding="utf-8")
    return root


def run_cli(repo: Path, *args: str) -> subprocess.CompletedProcess:
    import os

    command = [sys.executable, "-m", "Modality_Pipelines.cli", *args]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": str(repo)}
    return subprocess.run(command, cwd=repo, text=True, capture_output=True, env=env)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run full-pipeline smoke checks.")
    parser.add_argument("--study", default="R2", choices=get_supported_studies())
    parser.add_argument("--keep-root", action="store_true")
    args = parser.parse_args(argv)

    repo = Path(__file__).resolve().parents[1]
    print(f"repo: {repo}")
    print(f"study: {args.study}")

    with tempfile.TemporaryDirectory() as tmpdir:
        root = make_mock_subject_data(Path(tmpdir) / "Subject Data", args.study)
        database_path = Path(tmpdir) / "mock_pipeline.duckdb"
        print(f"mock_root: {root}")
        cli_database_path = Path(tmpdir) / "cli_mock_pipeline.duckdb"
        cli_dryrun_database_path = Path(tmpdir) / "cli_dryrun_pipeline.duckdb"
        print(f"mock_database: {database_path}")
        print(f"cli_mock_database: {cli_database_path}")

        config = load_study_config(args.study)
        assert config.study == args.study
        assert "delsys" in get_stage_registry(args.study)

        manifest = validate_study_files(study=args.study, root=root)
        assert len(manifest) == 4, manifest
        assert set(manifest["status"]) == {"valid"}, manifest[["file_name", "status", "issues"]]
        print("validation: passed")

        dry_counts = register_raw_files(study=args.study, root=root, dry_run=True, database_path=database_path)
        assert dry_counts["registered"] == 0, dry_counts
        assert dry_counts["would_register"] == 4, dry_counts
        assert dry_counts["skipped"] == 0, dry_counts
        print("registration dry-run: passed")

        write_counts = register_raw_files(study=args.study, root=root, dry_run=False, database_path=database_path)
        assert write_counts["registered"] == 4, write_counts
        assert write_counts["skipped"] == 0, write_counts
        print("registration write to temp DB: passed")

        # Processing dry-run checks dispatch/wiring without requiring valid acquisition exports.
        process_result = run_modality_processing(
            study=args.study,
            modality="delsys",
            dry_run=True,
            database_path=database_path,
        )
        assert "delsys" in process_result
        print("processing dry-run dispatch: passed")

        analyses = list_available_analyses(study=args.study)
        assert isinstance(analyses, list)
        print(f"analysis registry: {len(analyses)} registered")

        cli_checks = [
            ("studies",),
            ("status", "--study", args.study),
            ("analyses", "--study", args.study),
            ("validate", "--study", args.study, "--root", str(root), "--limit", "2"),
            (
                "register",
                "--study",
                args.study,
                "--root",
                str(root),
                "--dry-run",
                "--database-path",
                str(cli_dryrun_database_path),
            ),
            (
                "register",
                "--study",
                args.study,
                "--root",
                str(root),
                "--database-path",
                str(cli_database_path),
            ),
            (
                "process",
                "--study",
                args.study,
                "--modality",
                "delsys",
                "--dry-run",
                "--database-path",
                str(cli_database_path),
            ),
        ]
        for check in cli_checks:
            completed = run_cli(repo, *check)
            if completed.returncode not in (0, 2):
                print(completed.stdout)
                print(completed.stderr, file=sys.stderr)
                raise AssertionError(f"CLI check failed: {' '.join(check)}")
        print("cli smoke: passed")

        # Validate registry resolution when a temporary analysis entry exists.
        registry_path = Path(tmpdir) / "analysis_registry.json"
        registry_path.write_text(json.dumps({
            "analyses": {
                "mock_coactivation": {
                    "modality": "delsys",
                    "input_stage": "processed",
                    "output_table": {
                        "R1": "R1DelsysProcessed",
                        "R2": "DelsysProcessed"
                    },
                    "module": "math",
                    "function": "sqrt"
                }
            }
        }), encoding="utf-8")
        spec = resolve_analysis_spec(args.study, "mock_coactivation", registry_path=registry_path)
        assert spec.modality == "delsys"
        print("dynamic analysis resolution: passed")

    print("full pipeline smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
