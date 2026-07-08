"""Database-backed services for the BACPACS pipeline control panel.

The control panel treats SciDB/DuckDB as ground truth after registration. It
uses the SciDB metadata tables to answer what raw and processed records exist
for each participant without crawling the filesystem or re-running processing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from Modality_Pipelines.common.common_config import PIPELINE_ROOT
from Modality_Pipelines.common.study_config import StudyConfig, load_study_config
from Modality_Pipelines.common.table_registry import get_processed_tables, get_raw_file_table

CONTROL_PANEL_CONFIG_PATH = Path(__file__).with_name("control_panel_config.json")

CONFIG_FILES = {
    "Shared Study Config": PIPELINE_ROOT / "config.json",
    "Delsys Config": PIPELINE_ROOT / "Delsys_Pipeline" / "delsys_config.json",
    "Xsens Config": PIPELINE_ROOT / "Xsens_Pipeline" / "xsens_config.json",
    "GAITRite Config": PIPELINE_ROOT / "GAITRite_Pipeline" / "gaitrite_config.json",
    "Cosmed Config": PIPELINE_ROOT / "Cosmed_Pipeline" / "cosmed_config.json",
    "Control Panel Config": CONTROL_PANEL_CONFIG_PATH,
}


@dataclass(frozen=True)
class LedgerStatus:
    """Status summary for a participant row in the processing ledger."""

    label: str
    severity: int
    reason: str


def load_control_panel_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load UI-facing control panel configuration."""
    path = Path(config_path or CONTROL_PANEL_CONFIG_PATH)
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def get_ledger_stage_map(config_path: str | Path | None = None, study: str = "R2") -> list[dict[str, Any]]:
    """Return the configured modality/stage map for the processing ledger."""
    config = load_control_panel_config(config_path)
    modalities = config.get("ledger", {}).get("modalities", [])
    study_config = load_study_config(study)
    return [_normalize_modality_config(modality, study_config) for modality in modalities]


def get_record_counts(
    database_path: str | Path | None = None,
    stage_map: list[dict[str, Any]] | None = None,
    study: str = "R2",
) -> pd.DataFrame:
    """Return counts by participant and SciDB variable type.

    The queried record types come from ``control_panel_config.json`` so new
    analysis stages can appear in the ledger after a config update.
    """
    study_config = load_study_config(study)
    path = Path(database_path or study_config.database_path)
    if not path.exists():
        return _empty_counts()

    wanted_types = tuple(_stage_tables(stage_map or get_ledger_stage_map(study=study)))
    if not wanted_types:
        return _empty_counts()

    placeholders = ", ".join(["?"] * len(wanted_types))
    query = f"""
        SELECT
            COALESCE(s.participant_number, '') AS participant_number,
            r.type AS record_type,
            COUNT(*)::INTEGER AS record_count
        FROM _record r
        LEFT JOIN _schema s ON r.schema_id = s.schema_id
        WHERE COALESCE(r.excluded, false) = false
          AND r.type IN ({placeholders})
        GROUP BY 1, 2
        ORDER BY 1, 2
    """

    try:
        with duckdb.connect(str(path), read_only=True) as con:
            return con.execute(query, wanted_types).fetchdf()
    except duckdb.CatalogException:
        return _empty_counts()


def build_processing_ledger(
    database_path: str | Path | None = None,
    stage_map: list[dict[str, Any]] | None = None,
    study: str = "R2",
) -> pd.DataFrame:
    """Build the participant x stage ledger used by the home screen."""
    study_config = load_study_config(study)
    stages = stage_map or get_ledger_stage_map(study=study_config.study)
    output_columns = [
        "participant",
        *_stage_columns(stages),
        "ledger_status",
        "ledger_reason",
    ]
    counts = get_record_counts(database_path, stages, study=study_config.study)

    if counts.empty:
        return pd.DataFrame(columns=output_columns)

    participants = sorted(
        participant for participant in counts["participant_number"].dropna().unique() if participant
    )
    rows: list[dict[str, Any]] = []
    for participant in participants:
        participant_counts = counts[counts["participant_number"] == participant]
        count_by_type = dict(
            zip(participant_counts["record_type"], participant_counts["record_count"])
        )
        row: dict[str, Any] = {"participant": f"{study_config.participant_prefix}_{participant}"}
        for stage in _iter_stages(stages):
            row[stage["column"]] = int(count_by_type.get(stage["table"], 0))

        status = classify_ledger_row(row, stages)
        row["ledger_status"] = status.label
        row["ledger_reason"] = status.reason
        row["_severity"] = status.severity
        rows.append(row)

    ledger = pd.DataFrame(rows)
    if ledger.empty:
        return pd.DataFrame(columns=output_columns)
    ledger = ledger.sort_values(["_severity", "participant"], ascending=[False, True])
    return ledger.drop(columns=["_severity"]).reset_index(drop=True)


def classify_ledger_row(
    row: dict[str, Any],
    stage_map: list[dict[str, Any]] | None = None,
) -> LedgerStatus:
    """Classify one ledger row from configured modality stages."""
    stages = stage_map or get_ledger_stage_map()
    reasons: list[str] = []

    for modality in stages:
        modality_key = modality["key"]
        modality_stages = modality["stages"]
        raw_stage = _raw_stage(modality)
        analysis_stage = _analysis_stage(modality)
        raw_count = _row_count(row, raw_stage["column"])
        analysis_count = _row_count(row, analysis_stage["column"])

        previous = raw_stage
        for stage in modality_stages[1:]:
            previous_count = _row_count(row, previous["column"])
            stage_count = _row_count(row, stage["column"])
            if previous_count > 0 and stage_count == 0:
                reasons.append(
                    f"{modality_key}: {previous['label'].lower()} records exist but {stage['label'].lower()} has not run"
                )
                break
            if previous_count > 0 and stage_count < previous_count and stage.get("role") != "analysis":
                reasons.append(
                    f"{modality_key}: fewer {stage['label'].lower()} records than {previous['label'].lower()} records"
                )
                break
            previous = stage

        if raw_count > 0 and 0 < analysis_count < raw_count and len(modality_stages) == 2:
            reasons.append(
                f"{modality_key}: fewer {analysis_stage['label'].lower()} records than raw records"
            )

    any_stage = any(_row_count(row, stage["column"]) > 0 for stage in _iter_stages(stages))

    if reasons:
        severity = 2 if any("has not run" in reason for reason in reasons) else 1
        return LedgerStatus("attention" if severity == 2 else "partial", severity, "; ".join(reasons))
    if any_stage:
        return LedgerStatus("complete", 0, "registered and processed records are present")
    return LedgerStatus("empty", -1, "no registered records")


def get_config_state(study: str = "R2") -> pd.DataFrame:
    """Return read-only config key/value rows for the Configuration page."""
    rows: list[dict[str, Any]] = []
    rows.extend(_study_config_rows(load_study_config(study)))
    for config_name, path in CONFIG_FILES.items():
        if not path.exists():
            rows.append(
                {
                    "config": config_name,
                    "key": "__file__",
                    "value": "missing",
                    "source_path": str(path),
                }
            )
            continue
        with path.open("r", encoding="utf-8-sig") as file:
            data = json.load(file)
        for key_path, value in _flatten_json(data):
            rows.append(
                {
                    "config": config_name,
                    "key": key_path,
                    "value": json.dumps(value) if isinstance(value, (dict, list)) else value,
                    "source_path": str(path),
                }
            )
    return pd.DataFrame(rows)


def get_lineage_records(database_path: str | Path | None = None, limit: int = 200, study: str = "R2") -> pd.DataFrame:
    """Return recent invocation input/output lineage rows for inspection."""
    study_config = load_study_config(study)
    path = Path(database_path or study_config.database_path)
    if not path.exists():
        return pd.DataFrame()

    query = """
        SELECT
            i.function_name,
            input_record.type AS input_type,
            ii.input_record_id,
            output_record.type AS output_type,
            io.output_record_id,
            s.participant_number,
            s.visit,
            s.test,
            s.condition,
            s.speed,
            s.trial,
            s.cycle
        FROM _invocation i
        LEFT JOIN _invocation_input ii ON i.invocation_id = ii.invocation_id
        LEFT JOIN _record input_record ON ii.input_record_id = input_record.record_id
        LEFT JOIN _invocation_output io ON i.invocation_id = io.invocation_id
        LEFT JOIN _record output_record ON io.output_record_id = output_record.record_id
        LEFT JOIN _schema s ON output_record.schema_id = s.schema_id
        ORDER BY i.invocation_id DESC
        LIMIT ?
    """
    try:
        with duckdb.connect(str(path), read_only=True) as con:
            return con.execute(query, [limit]).fetchdf()
    except duckdb.CatalogException:
        return pd.DataFrame()


def _normalize_modality_config(modality: dict[str, Any], study_config: StudyConfig) -> dict[str, Any]:
    normalized = dict(modality)
    stages = []
    processed_index = 0
    for stage in modality.get("stages", []):
        stage_role = stage.get("role", "processed")
        resolved_stage = _normalize_stage_config(normalized["key"], stage)
        if stage_role == "raw":
            resolved_stage["table"] = get_raw_file_table(study_config.study, normalized["key"]).__name__
        else:
            processed_tables = get_processed_tables(study_config.study, normalized["key"])
            if processed_index < len(processed_tables):
                resolved_stage["table"] = processed_tables[processed_index].__name__
            processed_index += 1
        stages.append(resolved_stage)
    normalized["stages"] = stages
    if not normalized["stages"]:
        raise ValueError(f"Ledger modality {normalized.get('key')!r} has no stages.")
    return normalized


def _normalize_stage_config(modality_key: str, stage: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(stage)
    if "table" not in normalized:
        raise ValueError(f"Ledger stage {modality_key}.{normalized.get('key')} is missing a table.")
    normalized.setdefault("key", normalized["table"])
    normalized.setdefault("label", normalized["key"].replace("_", " ").title())
    normalized.setdefault("column", f"{modality_key}_{normalized['key']}")
    normalized.setdefault("role", "processed")
    return normalized


def _raw_stage(modality: dict[str, Any]) -> dict[str, Any]:
    for stage in modality["stages"]:
        if stage.get("role") == "raw":
            return stage
    return modality["stages"][0]


def _analysis_stage(modality: dict[str, Any]) -> dict[str, Any]:
    for stage in reversed(modality["stages"]):
        if stage.get("role") == "analysis":
            return stage
    return modality["stages"][-1]


def _iter_stages(stage_map: list[dict[str, Any]]):
    for modality in stage_map:
        yield from modality["stages"]


def _stage_columns(stage_map: list[dict[str, Any]]) -> list[str]:
    return [stage["column"] for stage in _iter_stages(stage_map)]


def _stage_tables(stage_map: list[dict[str, Any]]) -> list[str]:
    return list(dict.fromkeys(stage["table"] for stage in _iter_stages(stage_map)))


def _row_count(row: dict[str, Any], column: str) -> int:
    value = row.get(column, 0)
    if pd.isna(value):
        return 0
    return int(value or 0)


def _study_config_rows(study_config: StudyConfig) -> list[dict[str, Any]]:
    data = {
        "metadata": {"project_name": study_config.project_name},
        "project": {
            "project_root": str(study_config.project_root),
            "subject_data_root": str(study_config.subject_data_root),
            "pipeline_root": str(study_config.pipeline_root),
            "database_path": str(study_config.database_path),
        },
        "file_naming": {
            "pattern": study_config.file_name_pattern,
            "participant_folder_template": study_config.participant_folder_template,
            "schema_keys": list(study_config.schema_keys),
        },
        "visits": study_config.visits,
        "modalities": study_config.modalities,
    }
    return [
        {
            "config": "Selected Study Config",
            "key": key_path,
            "value": json.dumps(value) if isinstance(value, (dict, list)) else value,
            "source_path": f"study:{study_config.study}",
        }
        for key_path, value in _flatten_json(data)
    ]


def _flatten_json(value: Any, prefix: str = ""):
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            yield from _flatten_json(child, child_prefix)
    else:
        yield prefix, value


def _empty_counts() -> pd.DataFrame:
    return pd.DataFrame(columns=["participant_number", "record_type", "record_count"])
