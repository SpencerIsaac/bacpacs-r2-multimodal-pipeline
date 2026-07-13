"""Check that pipeline docs match executable configuration.

The SOP is the human source of truth. This script checks that the MkDocs pages
and source metadata still mention the runtime facts exposed by the code/config.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = REPO_ROOT / "docs"
SOURCE_OF_TRUTH = DOCS_ROOT / "source_of_truth.json"
REQUIRED_DOCS = [
    "index.md",
    "sop/bacpacs-pipeline-sop.md",
    "user-guide/first-time-setup.md",
    "user-guide/running-the-pipeline.md",
    "user-guide/cli-reference.md",
    "user-guide/gui-control-panel.md",
    "developer-guide/architecture.md",
    "developer-guide/adding-analysis-methods.md",
    "developer-guide/configuration-reference.md",
    "developer-guide/documentation-freshness.md",
    "reference/canonical-tables.md",
    "reference/discrepancies.md",
    "reference/glossary.md",
]


def _load_runtime_facts() -> dict:
    sys.path.insert(0, str(REPO_ROOT))
    from Modality_Pipelines.common.lightweight_registry import (
        PROCESSED_TABLE_NAMES,
        RAW_FILE_TABLE_NAMES,
        get_supported_studies,
    )
    from Modality_Pipelines.common.study_config import load_study_config

    studies = get_supported_studies()
    configs = {study: load_study_config(study) for study in studies}
    return {
        "studies": studies,
        "configs": configs,
        "raw_file_tables": RAW_FILE_TABLE_NAMES,
        "processed_tables": PROCESSED_TABLE_NAMES,
    }


def _read_docs() -> str:
    content = []
    for relative_path in REQUIRED_DOCS:
        path = DOCS_ROOT / relative_path
        if path.exists():
            content.append(path.read_text(encoding="utf-8"))
    return "\n".join(content)


def _require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    failures: list[str] = []

    _require(SOURCE_OF_TRUTH.exists(), "Missing docs/source_of_truth.json", failures)
    for relative_path in REQUIRED_DOCS:
        _require((DOCS_ROOT / relative_path).exists(), f"Missing docs/{relative_path}", failures)

    if failures:
        for failure in failures:
            print(f"docs freshness: {failure}")
        return 1

    metadata = json.loads(SOURCE_OF_TRUTH.read_text(encoding="utf-8-sig"))
    docs_text = _read_docs()
    facts = _load_runtime_facts()

    studies = facts["studies"]
    _require(metadata.get("studies") == studies, "docs/source_of_truth.json studies do not match runtime studies", failures)

    database_paths = {str(config.database_path) for config in facts["configs"].values()}
    _require(len(database_paths) == 1, "R1/R2 runtime configs no longer point to one shared database", failures)
    shared_database_path = next(iter(database_paths))
    _require(metadata.get("shared_database_path") == shared_database_path, "shared database path metadata is stale", failures)
    _require(shared_database_path in docs_text, "shared database path is missing from docs", failures)

    for study, config in facts["configs"].items():
        expected_tokens = [
            study,
            config.project_name,
            str(config.subject_data_root),
            config.file_name_pattern,
            config.participant_prefix,
        ]
        for token in expected_tokens:
            _require(token in docs_text, f"Missing study token in docs: {token}", failures)

        for visit in config.visits.values():
            _require(visit["folder"] in docs_text, f"Missing visit folder in docs: {study} {visit['folder']}", failures)
            _require(visit["file_code"] in docs_text, f"Missing visit code in docs: {study} {visit['file_code']}", failures)

        for modality in config.modalities.values():
            _require(modality["folder"] in docs_text, f"Missing modality folder in docs: {study} {modality['folder']}", failures)
            _require(modality["file_code"] in docs_text, f"Missing modality code in docs: {study} {modality['file_code']}", failures)
            for extension in modality.get("primary_extensions", []):
                _require(f".{extension}" in docs_text or extension in docs_text, f"Missing extension in docs: {extension}", failures)

    for table_map in facts["raw_file_tables"].values():
        for table_name in table_map.values():
            _require(table_name in docs_text, f"Missing RawFile table in docs: {table_name}", failures)

    for table_map in facts["processed_tables"].values():
        for table_names in table_map.values():
            for table_name in table_names:
                _require(table_name in docs_text, f"Missing processed table in docs: {table_name}", failures)

    for command in metadata.get("required_cli_commands", []):
        _require(command in docs_text, f"Missing CLI command in docs: {command}", failures)

    for source_file in metadata.get("source_files", []):
        _require((REPO_ROOT / source_file).exists(), f"Source-of-truth file does not exist: {source_file}", failures)
        _require(source_file in docs_text, f"Source-of-truth file not documented: {source_file}", failures)

    if failures:
        for failure in failures:
            print(f"docs freshness: {failure}")
        return 1

    print("docs freshness: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
