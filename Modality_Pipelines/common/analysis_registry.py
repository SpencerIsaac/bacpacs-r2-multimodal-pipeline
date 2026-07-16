"""Runtime registry and dispatcher for downstream analysis stages.

The registry lets the CLI and GUI discover analysis stages from metadata rather
than hardcoding every new metric. A new analysis needs three pieces: a Python
function, a study-specific output table class, and one JSON registry entry.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from Modality_Pipelines.common.study_config import load_study_config

DEFAULT_REGISTRY_PATH = Path(__file__).with_name("analysis_registry.json")


@dataclass(frozen=True)
class AnalysisSpec:
    """Resolved analysis metadata for one study namespace."""

    name: str
    modality: str
    module: str
    function: str
    input_table: type
    output_tables: list[type]
    input_name: str = "processed_record"
    batch_enabled: bool = True
    description: str = ""
    config: dict[str, Any] | None = None


def _read_registry_file(registry_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(registry_path) if registry_path is not None else DEFAULT_REGISTRY_PATH
    if not path.exists():
        return {"analyses": {}}
    with path.open("r", encoding="utf-8") as stream:
        data = json.load(stream)
    if "analyses" not in data:
        data = {"analyses": data}
    if not isinstance(data.get("analyses"), dict):
        raise ValueError("analysis registry must contain an 'analyses' object")
    return data


def load_analysis_registry(registry_path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """Load raw analysis registry entries keyed by analysis name."""
    return dict(_read_registry_file(registry_path)["analyses"])


def _normalize_study_mapping(value: Any, study: str, field_name: str) -> Any:
    if isinstance(value, Mapping):
        try:
            return value[study]
        except KeyError as exc:
            raise KeyError(f"{field_name} has no entry for study {study}") from exc
    return value


def _resolve_input_table(study: str, entry: Mapping[str, Any]):
    from Modality_Pipelines.common.table_registry import get_primary_processed_table, get_table_class

    if "input_table" in entry:
        table_name = _normalize_study_mapping(entry["input_table"], study, "input_table")
        return get_table_class(study, table_name)

    input_stage = entry.get("input_stage", "processed")
    if input_stage in {"processed", "primary_processed"}:
        return get_primary_processed_table(study, entry["modality"])

    raise ValueError(
        "Analysis entries must define input_table or use input_stage='processed'. "
        f"Got input_stage={input_stage!r}."
    )


def _resolve_output_tables(study: str, entry: Mapping[str, Any]) -> list[type]:
    from Modality_Pipelines.common.table_registry import get_table_class

    if "output_tables" in entry:
        output_value = entry["output_tables"]
    elif "output_table" in entry:
        output_value = entry["output_table"]
    else:
        raise ValueError("Analysis entry is missing output_table/output_tables")

    output_value = _normalize_study_mapping(output_value, study, "output_table")
    if isinstance(output_value, str):
        output_names = [output_value]
    else:
        output_names = list(output_value)
    return [get_table_class(study, table_name) for table_name in output_names]




def _resolve_input_table_name(study: str, entry: Mapping[str, Any]) -> str:
    if "input_table" in entry:
        return str(_normalize_study_mapping(entry["input_table"], study, "input_table"))

    input_stage = entry.get("input_stage", "processed")
    if input_stage in {"processed", "primary_processed"}:
        from Modality_Pipelines.common.lightweight_registry import PROCESSED_TABLE_NAMES

        modality = str(entry["modality"]).lower()
        return PROCESSED_TABLE_NAMES[study][modality][0]

    raise ValueError(
        "Analysis entries must define input_table or use input_stage='processed'. "
        f"Got input_stage={input_stage!r}."
    )


def _resolve_output_table_names(study: str, entry: Mapping[str, Any]) -> list[str]:
    if "output_tables" in entry:
        output_value = entry["output_tables"]
    elif "output_table" in entry:
        output_value = entry["output_table"]
    else:
        raise ValueError("Analysis entry is missing output_table/output_tables")

    output_value = _normalize_study_mapping(output_value, study, "output_table")
    if isinstance(output_value, str):
        return [output_value]
    return [str(value) for value in output_value]


def resolve_analysis_spec(
    study: str,
    analysis: str,
    registry_path: str | Path | None = None,
) -> AnalysisSpec:
    """Resolve one analysis registry entry into callable/table metadata."""
    study_config = load_study_config(study)
    registry = load_analysis_registry(registry_path)
    try:
        entry = registry[analysis]
    except KeyError as exc:
        raise KeyError(f"Unknown analysis {analysis!r}") from exc

    required = ["modality", "module", "function"]
    missing = [field for field in required if not entry.get(field)]
    if missing:
        raise ValueError(f"Analysis {analysis!r} is missing required field(s): {', '.join(missing)}")

    return AnalysisSpec(
        name=analysis,
        modality=str(entry["modality"]).lower(),
        module=str(entry["module"]),
        function=str(entry["function"]),
        input_table=_resolve_input_table(study_config.study, entry),
        output_tables=_resolve_output_tables(study_config.study, entry),
        input_name=str(entry.get("input_name", "processed_record")),
        batch_enabled=bool(entry.get("batch_enabled", True)),
        description=str(entry.get("description", "")),
        config=dict(entry.get("config", {})),
    )


def get_analysis_callable(spec: AnalysisSpec):
    """Import and return the Python callable declared by an analysis spec."""
    module = importlib.import_module(spec.module)
    try:
        return getattr(module, spec.function)
    except AttributeError as exc:
        raise AttributeError(f"{spec.module!r} does not define {spec.function!r}") from exc


def list_available_analyses(
    study: str | None = None,
    modality: str | None = None,
    registry_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return analysis metadata suitable for CLI help/status output."""
    modality_key = modality.lower() if modality else None
    rows: list[dict[str, Any]] = []
    for name, entry in load_analysis_registry(registry_path).items():
        if modality_key and str(entry.get("modality", "")).lower() != modality_key:
            continue
        row = {
            "name": name,
            "modality": str(entry.get("modality", "")).lower(),
            "description": entry.get("description", ""),
            "module": entry.get("module", ""),
            "function": entry.get("function", ""),
            "batch_enabled": bool(entry.get("batch_enabled", True)),
        }
        if study is not None:
            study_key = load_study_config(study).study
            row["input_table"] = _resolve_input_table_name(study_key, entry)
            row["output_tables"] = _resolve_output_table_names(study_key, entry)
        rows.append(row)
    return sorted(rows, key=lambda item: (item["modality"], item["name"]))


def run_registered_analysis(
    study: str = "R2",
    analysis: str | None = None,
    participant_number=None,
    visit=None,
    test=None,
    condition=None,
    speed=None,
    trial=None,
    unprocessed_only: bool = True,
    overwrite: bool = False,
    dry_run: bool = False,
    registry_path: str | Path | None = None,
    **extra_options: Any,
):
    """Run one registry-defined analysis through SciStack-owned batching.

    This is the backend function the CLI should call for dynamic analysis
    processing. It does not touch raw files; analyses consume processed tables.
    """
    if not analysis:
        raise ValueError("analysis is required")

    from Modality_Pipelines.common.scistack_runner import run_scistack_stage, split_stage_kwargs

    spec = resolve_analysis_spec(study, analysis, registry_path=registry_path)
    if not spec.batch_enabled:
        raise ValueError(f"Analysis {analysis!r} is not marked batch_enabled")

    fn = get_analysis_callable(spec)
    if spec.config:
        base_fn = fn

        def fn(**kwargs):
            return base_fn(**kwargs, config=spec.config)

    schema_filters = {
        "participant_number": participant_number,
        "visit": visit,
        "test": test,
        "condition": condition,
        "speed": speed,
        "trial": trial,
        "dry_run": dry_run,
        "skip_computed": unprocessed_only and not overwrite,
        **extra_options,
    }
    schema_filters, stage_options = split_stage_kwargs(schema_filters)

    return run_scistack_stage(
        fn,
        inputs={spec.input_name: spec.input_table},
        outputs=spec.output_tables,
        schema_filters=schema_filters,
        study=study,
        **stage_options,
    )
