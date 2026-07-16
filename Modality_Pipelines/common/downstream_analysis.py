"""Derived downstream analysis tables for BACPACS multimodal data."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from Modality_Pipelines.common.common_config import configure_scistack_database
from Modality_Pipelines.common.study_config import StudyConfig, load_study_config
from Modality_Pipelines.common.table_registry import get_table_class

SCHEMA_KEYS = ("participant_number", "visit", "test", "condition", "speed", "trial", "cycle")
TRIAL_KEYS = ("participant_number", "visit", "test", "condition", "speed", "trial")
NUM_POINTS = 101
REQUIRED_MODALITIES = ("xsens", "delsys", "gaitrite")
ISSUE_SEVERITY = {
    "missing_modality": "error",
    "mismatched_trial": "error",
    "missing_gait_events": "error",
    "slice_failure": "error",
    "missing_visit_summary": "error",
    "missing_or_zero_visit_max": "error",
    "non_alternating_cycles": "warning",
    "export_failure": "error",
}
ANALYSIS_TABLES = {
    "R1": {
        "trial": "R1TrialAnalysis",
        "cycle_unmatched": "R1CycleUnmatched",
        "cycle_matched": "R1CycleMatched",
        "visit": "R1VisitSummary",
        "issue": "R1AnalysisIssue",
        "xsens": "R1XsensProcessed",
        "delsys": "R1DelsysProcessed",
        "gaitrite_loaded": "R1GAITRiteLoaded",
        "gaitrite_cycle": "R1GAITRiteCycle",
    },
    "R2": {
        "trial": "TrialAnalysis",
        "cycle_unmatched": "CycleUnmatched",
        "cycle_matched": "CycleMatched",
        "visit": "VisitSummary",
        "issue": "AnalysisIssue",
        "xsens": "XsensProcessed",
        "delsys": "DelsysProcessed",
        "gaitrite_loaded": "GAITRiteLoaded",
        "gaitrite_cycle": "GAITRiteCycle",
    },
}
EXPORT_FILES = {
    "trial": "bacpacs_trial.csv",
    "cycle_unmatched": "bacpacs_cycle_unmatched.csv",
    "cycle_matched": "bacpacs_cycle_matched.csv",
    "visit": "bacpacs_visit.csv",
    "issue": "bacpacs_analysis_issues.csv",
}
ISSUE_EXPORT_COLUMNS = [
    "participant_number",
    "visit",
    "test",
    "condition",
    "speed",
    "trial",
    "cycle_index",
    "stage",
    "issue_type",
    "severity",
    "modality",
    "source_table",
    "source_record_id",
    "related_record_ids",
    "message",
    "created_at",
]


class AnalysisPreconditionError(RuntimeError):
    """Raised when a downstream stage is run before its required input exists."""


def build_trial_analysis(study: str = "R2", **filters) -> dict[str, int]:
    ctx = _context(study, filters)
    xsens = _load_table(ctx, "xsens")
    delsys = _load_table(ctx, "delsys")
    gaitrite_loaded = _load_table(ctx, "gaitrite_loaded")
    gaitrite_cycle = _load_table(ctx, "gaitrite_cycle")

    indexed = {
        "xsens": _by_trial(xsens),
        "delsys": _by_trial(delsys),
        "gaitrite": _by_trial(gaitrite_loaded),
    }
    all_keys = set().union(*(set(value) for value in indexed.values()))
    saved = 0
    issues = 0
    skipped = 0
    for key in sorted(all_keys):
        missing = [name for name, rows in indexed.items() if key not in rows]
        metadata = _metadata_from_key(key, cycle=None)
        if missing:
            for modality in missing:
                _save_issue(ctx, metadata, "trial_analysis", "missing_modality", modality=modality, message=f"Missing {modality} processed record for trial.")
                issues += 1
            skipped += 1
            continue

        xsens_row = indexed["xsens"][key][0]
        delsys_row = indexed["delsys"][key][0]
        gaitrite_row = indexed["gaitrite"][key][0]
        cycles = _rows_for_key(gaitrite_cycle, key)
        payload = {
            "trial_uid": _trial_uid(metadata),
            "source_record_ids": {
                "xsens": _row_value(xsens_row, "__record_id"),
                "delsys": _row_value(delsys_row, "__record_id"),
                "gaitrite_loaded": _row_value(gaitrite_row, "__record_id"),
                "gaitrite_cycle": [_row_value(row, "__record_id") for row in cycles],
            },
            "xsens": _row_value(xsens_row, "data"),
            "delsys": _row_value(delsys_row, "data"),
            "gaitrite_loaded": _dataframe_payload(_row_value(gaitrite_row, "data")),
            "gaitrite_cycles": [_dataframe_payload(_row_value(row, "data")) for row in cycles],
            "created_at": _now(),
        }
        if _safe_save(ctx, "trial", payload, metadata):
            saved += 1
        else:
            skipped += 1
    return {"saved": saved, "issues": issues, "skipped": skipped, "source_trials": len(all_keys)}


def build_cycle_unmatched(study: str = "R2", **filters) -> dict[str, int]:
    ctx = _context(study, filters)
    trials = _load_table(ctx, "trial")
    _require_rows(trials, "TrialAnalysis", "build-trial")
    saved = 0
    issues = 0
    skipped = 0
    for _, trial in trials.iterrows():
        metadata_base = _metadata_from_row(trial, cycle=None)
        data = _row_value(trial, "data")
        if not isinstance(data, Mapping):
            continue
        gaitrite_loaded = _first_record(_payload_value(data, "gaitrite_loaded", []))
        gaitrite_cycles = _payload_value(data, "gaitrite_cycles", []) or []
        if not gaitrite_loaded or not gaitrite_cycles:
            _save_issue(ctx, metadata_base, "cycle_unmatched", "missing_gait_events", message="Trial has no GAITRite cycle/event payload.")
            issues += 1
            continue
        event_seconds = _event_seconds(gaitrite_loaded)
        if not event_seconds:
            _save_issue(ctx, metadata_base, "cycle_unmatched", "missing_gait_events", message="GAITRite event seconds are missing.")
            issues += 1
            continue
        side_counts = Counter()
        for cycle_payload in gaitrite_cycles:
            cycle_row = _first_record(cycle_payload)
            if not cycle_row:
                continue
            side = str(cycle_row.get("StartFoot") or "").upper()
            if side not in {"L", "R"}:
                skipped += 1
                continue
            side_counts[side] += 1
            side_cycle_index = side_counts[side] - 1
            start_end = _cycle_start_end(event_seconds, side, side_cycle_index)
            cycle_index = _cycle_number(cycle_row, default=sum(side_counts.values()))
            metadata = {**metadata_base, "cycle": str(cycle_index)}
            if start_end is None:
                _save_issue(ctx, metadata, "cycle_unmatched", "slice_failure", message=f"Not enough {side} heel strikes for cycle {cycle_index}.")
                issues += 1
                continue
            start_seconds, end_seconds = start_end
            try:
                xsens_cycle = _slice_xsens(_payload_value(data, "xsens"), start_seconds, end_seconds)
                delsys_cycle = _slice_delsys(_payload_value(data, "delsys"), start_seconds, end_seconds)
            except Exception as exc:
                _save_issue(ctx, metadata, "cycle_unmatched", "slice_failure", message=str(exc))
                issues += 1
                continue
            payload = {
                "trial_uid": _payload_value(data, "trial_uid") or _trial_uid(metadata_base),
                "cycle_index": cycle_index,
                "side": side,
                "start_foot": side,
                "cycle_start_seconds": start_seconds,
                "cycle_end_seconds": end_seconds,
                "xsens_time_normalized": xsens_cycle,
                "delsys_time_normalized": delsys_cycle,
                "delsys_normalized_time_normalized": {},
                "normalized_at": None,
                "gaitrite_metrics": cycle_row,
                "source_record_ids": _payload_value(data, "source_record_ids", {}),
                "created_at": _now(),
            }
            if _safe_save(ctx, "cycle_unmatched", payload, metadata):
                saved += 1
            else:
                skipped += 1
    return {"saved": saved, "issues": issues, "skipped": skipped, "source_trials": len(trials)}


def finalize_visit_summary(study: str = "R2", **filters) -> dict[str, int]:
    ctx = _context(study, filters)
    cycles = _load_table(ctx, "cycle_unmatched")
    _require_rows(cycles, "CycleUnmatched", "build-cycles")
    saved = 0
    for key, group in cycles.groupby(["participant_number", "visit"], dropna=False):
        participant_number, visit = key
        max_values: dict[str, float] = {}
        trial_ids = set()
        for _, row in group.iterrows():
            data = _row_value(row, "data")
            if not isinstance(data, Mapping):
                continue
            trial_ids.add(_trial_uid(_metadata_from_row(row, cycle=None)))
            for muscle, values in (_payload_value(data, "delsys_time_normalized", {}) or {}).items():
                arr = _as_float_array(values)
                if arr.size == 0 or np.all(np.isnan(arr)):
                    continue
                max_values[muscle] = max(max_values.get(muscle, np.nan), float(np.nanmax(arr))) if muscle in max_values else float(np.nanmax(arr))
        metadata = {
            "participant_number": _clean_schema_value(participant_number),
            "visit": _clean_schema_value(visit),
            "test": None,
            "condition": None,
            "speed": None,
            "trial": None,
            "cycle": None,
        }
        payload = {
            "max_emg": max_values,
            **{f"max_emg_{_safe_name(name)}": value for name, value in max_values.items()},
            "source_trial_count": len(trial_ids),
            "source_cycle_count": int(len(group)),
            "finalized_at": _now(),
            "normalization_scope": "participant_number+visit",
        }
        if _safe_save(ctx, "visit", payload, metadata):
            saved += 1
    return {"saved": saved, "source_cycles": len(cycles)}


def normalize_cycles_to_visit(study: str = "R2", **filters) -> dict[str, int]:
    ctx = _context(study, filters)
    cycles = _load_table(ctx, "cycle_unmatched")
    visits = _load_table(ctx, "visit")
    _require_rows(cycles, "CycleUnmatched", "build-cycles")
    _require_rows(visits, "VisitSummary", "finalize-visit")
    visits_by_key = {
        (_clean_schema_value(row["participant_number"]), _clean_schema_value(row["visit"])): _row_value(row, "data")
        for _, row in visits.iterrows()
    }
    saved = 0
    issues = 0
    skipped = 0
    for _, row in cycles.iterrows():
        metadata = _metadata_from_row(row)
        visit_key = (metadata["participant_number"], metadata["visit"])
        summary = visits_by_key.get(visit_key)
        if not isinstance(summary, Mapping):
            _save_issue(ctx, metadata, "cycle_normalization", "missing_visit_summary", message="VisitSummary is missing for cycle.")
            issues += 1
            continue
        max_emg = _payload_value(summary, "max_emg", {}) if isinstance(summary, Mapping) else {}
        data = dict(_row_value(row, "data") or {})
        normalized = {}
        for muscle, values in (_payload_value(data, "delsys_time_normalized", {}) or {}).items():
            denom = max_emg.get(muscle)
            if denom in (None, 0) or (isinstance(denom, float) and np.isnan(denom)):
                _save_issue(ctx, metadata, "cycle_normalization", "missing_or_zero_visit_max", modality="delsys", message=f"Missing or zero visit max for {muscle}.")
                issues += 1
                normalized[muscle] = _nan_like(values)
                continue
            normalized[muscle] = (_as_float_array(values) / float(denom)).tolist()
        data["delsys_normalized_time_normalized"] = normalized
        data["normalized_at"] = _now()
        if _safe_save(ctx, "cycle_unmatched", data, metadata):
            saved += 1
        else:
            skipped += 1
    return {"saved": saved, "issues": issues, "skipped": skipped, "source_cycles": len(cycles)}


def build_cycle_matched(study: str = "R2", **filters) -> dict[str, int]:
    ctx = _context(study, filters)
    cycles = _load_table(ctx, "cycle_unmatched")
    _require_rows(cycles, "CycleUnmatched", "normalize-cycles")
    if not _has_normalized_cycles(cycles):
        raise AnalysisPreconditionError("build-matched requires normalized CycleUnmatched rows. Run normalize-cycles first.")
    saved = 0
    issues = 0
    grouped = cycles.sort_values(["participant_number", "visit", "test", "condition", "speed", "trial", "cycle"]).groupby(list(TRIAL_KEYS), dropna=False)
    for _, group in grouped:
        records = [row for _, row in group.iterrows()]
        for idx in range(max(len(records) - 1, 0)):
            current = records[idx]
            nxt = records[idx + 1]
            current_data = _row_value(current, "data") or {}
            next_data = _row_value(nxt, "data") or {}
            current_side = str(_payload_value(current_data, "side") or _payload_value(current_data, "start_foot") or "").upper()
            next_side = str(_payload_value(next_data, "side") or _payload_value(next_data, "start_foot") or "").upper()
            metadata = _metadata_from_row(current, cycle=str(idx + 1))
            if current_side not in {"L", "R"} or next_side not in {"L", "R"} or current_side == next_side:
                _save_issue(ctx, metadata, "cycle_matching", "non_alternating_cycles", source_record_id=_row_value(current, "__record_id"), related_record_ids=[_row_value(nxt, "__record_id")], message="Adjacent cycles do not alternate L/R.")
                issues += 1
                continue
            payload = {
                "matched_cycle_index": idx + 1,
                "ipsilateral_side": current_side,
                "contralateral_side": next_side,
                "left_cycle_source_id": _row_value(current if current_side == "L" else nxt, "__record_id"),
                "right_cycle_source_id": _row_value(current if current_side == "R" else nxt, "__record_id"),
                "current_cycle": current_data,
                "next_cycle": next_data,
                "delsys_time_normalized": _merge_side_signals(current_data, next_data, "delsys_time_normalized", current_side, next_side),
                "delsys_normalized_time_normalized": _merge_side_signals(current_data, next_data, "delsys_normalized_time_normalized", current_side, next_side),
                "xsens_time_normalized": _merge_side_signals(current_data, next_data, "xsens_time_normalized", current_side, next_side),
                "gaitrite_metrics": {"current": _payload_value(current_data, "gaitrite_metrics"), "next": _payload_value(next_data, "gaitrite_metrics")},
                "created_at": _now(),
            }
            if _safe_save(ctx, "cycle_matched", payload, metadata):
                saved += 1
    return {"saved": saved, "issues": issues, "source_cycles": len(cycles)}


def export_analysis_tables(study: str = "R2", output_dir: str | Path | None = None, **filters) -> dict[str, str]:
    ctx = _context(study, filters)
    output_root = Path(output_dir) if output_dir is not None else Path("analysis_scripts") / "exports"
    output_root.mkdir(parents=True, exist_ok=True)
    date_prefix = datetime.now().strftime("%Y%m%d")
    written = {}
    for key, filename in EXPORT_FILES.items():
        df = _load_table(ctx, key)
        if df.empty:
            if key == "issue" and written:
                output = output_root / f"{date_prefix}_{filename}"
                pd.DataFrame(columns=ISSUE_EXPORT_COLUMNS).to_csv(output, index=False)
                written[key] = str(output)
            continue
        output = output_root / f"{date_prefix}_{filename}"
        _analysis_export_frame(df).to_csv(output, index=False)
        written[key] = str(output)
    if not written:
        raise AnalysisPreconditionError("No derived analysis tables exist for export.")
    return written


def build_all(study: str = "R2", output_dir: str | Path | None = None, **filters) -> dict[str, Any]:
    result = {
        "build_trial": build_trial_analysis(study=study, **filters),
        "build_cycles": build_cycle_unmatched(study=study, **filters),
        "finalize_visit": finalize_visit_summary(study=study, **filters),
        "normalize_cycles": normalize_cycles_to_visit(study=study, **filters),
        "build_matched": build_cycle_matched(study=study, **filters),
    }
    result["export"] = export_analysis_tables(study=study, output_dir=output_dir, **filters)
    return result


def _context(study: str, filters: Mapping[str, Any]):
    study_config = load_study_config(study)
    db = configure_scistack_database(filters.get("database_path"), study_config=study_config)
    return {"study": study_config.study, "config": study_config, "db": db, "filters": _clean_filters(filters)}


def _clean_filters(filters: Mapping[str, Any]) -> dict[str, Any]:
    cleaned = {}
    for key in SCHEMA_KEYS:
        value = filters.get(key)
        if value is not None:
            cleaned[key] = str(value) if key != "trial" else value
    return cleaned


def _table(ctx, key: str):
    return get_table_class(ctx["study"], ANALYSIS_TABLES[ctx["study"]][key])


def _load_table(ctx, key: str) -> pd.DataFrame:
    table = _table(ctx, key)
    metadata = {k: v for k, v in ctx["filters"].items() if k in SCHEMA_KEYS and v is not None}
    try:
        return ctx["db"].load_all_as_df(table, metadata=metadata or None, include_rid=True)
    except Exception as exc:
        if _looks_like_missing_table(exc):
            return pd.DataFrame()
        if key == "issue" and _looks_like_json_decode(exc):
            return _load_issue_table_direct(ctx, metadata)
        raise


def _load_issue_table_direct(ctx, metadata: Mapping[str, Any]) -> pd.DataFrame:
    """Load AnalysisIssue rows when SciDB JSON dtype inference rejects text columns."""
    import duckdb

    table_name = ANALYSIS_TABLES[ctx["study"]]["issue"]
    db_path = str(ctx["config"].database_path)
    where = []
    params = []
    for key, value in metadata.items():
        if key in SCHEMA_KEYS and value is not None:
            where.append(f'"{key}" = ?')
            params.append(str(value))
    sql = f'SELECT * FROM "{table_name}"'
    if where:
        sql += " WHERE " + " AND ".join(where)
    try:
        existing_con = getattr(getattr(ctx["db"], "_duck", None), "con", None)
        if existing_con is not None:
            raw = existing_con.execute(sql, params).fetchdf()
        else:
            with duckdb.connect(db_path, read_only=True) as con:
                raw = con.execute(sql, params).fetchdf()
    except Exception as exc:
        if _looks_like_missing_table(exc):
            return pd.DataFrame()
        raise
    if raw.empty:
        return pd.DataFrame()
    rows = []
    for _, row in raw.iterrows():
        data = {}
        for column in ISSUE_EXPORT_COLUMNS:
            if column in raw.columns:
                data[column] = _decode_payload_value(row[column])
        rows.append(
            {
                "__record_id": row.get("record_id"),
                **{key: _clean_schema_value(row.get(key)) for key in SCHEMA_KEYS if key in raw.columns},
                "data": data,
            }
        )
    return pd.DataFrame(rows)


def _by_trial(df: pd.DataFrame) -> dict[tuple, list[pd.Series]]:
    rows = defaultdict(list)
    if df.empty:
        return rows
    for _, row in df.iterrows():
        rows[_trial_key(row)].append(row)
    return rows


def _rows_for_key(df: pd.DataFrame, key: tuple) -> list[pd.Series]:
    if df.empty:
        return []
    return [row for _, row in df.iterrows() if _trial_key(row) == key]


def _trial_key(row) -> tuple:
    return tuple(_clean_schema_value(row.get(key)) for key in TRIAL_KEYS)


def _metadata_from_key(key: tuple, cycle=None) -> dict[str, Any]:
    return dict(zip(TRIAL_KEYS, key)) | {"cycle": cycle}


def _metadata_from_row(row, cycle=None) -> dict[str, Any]:
    metadata = {key: _clean_schema_value(row.get(key)) for key in SCHEMA_KEYS}
    if cycle is not None:
        metadata["cycle"] = cycle
    return metadata


def _clean_schema_value(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value)
    return None if text in {"", "None", "null", "nan", "NaN", "<NA>", "NaT"} else text


def _safe_save(ctx, table_key: str, payload: Any, metadata: Mapping[str, Any]) -> bool:
    table = _table(ctx, table_key)
    try:
        table.save(_storage_payload(payload), **metadata)
        return True
    except Exception as exc:
        if _looks_like_duplicate_record(exc):
            return False
        raise


def _save_issue(ctx, metadata: Mapping[str, Any], stage: str, issue_type: str, *, modality=None, source_table=None, source_record_id=None, related_record_ids=None, message="") -> None:
    payload = {
        **{key: metadata.get(key) for key in SCHEMA_KEYS},
        "cycle_index": metadata.get("cycle"),
        "stage": stage,
        "issue_type": issue_type,
        "severity": ISSUE_SEVERITY[issue_type],
        "modality": modality,
        "source_table": source_table,
        "source_record_id": source_record_id,
        "related_record_ids": related_record_ids or [],
        "message": message,
        "created_at": _now(),
    }
    _safe_save(ctx, "issue", payload, metadata)


def _dataframe_payload(value):
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, list):
        return value
    return []


def _first_record(value):
    if isinstance(value, pd.DataFrame):
        records = value.to_dict(orient="records")
        return records[0] if records else None
    if isinstance(value, list):
        return value[0] if value else None
    if isinstance(value, Mapping):
        return value
    return None
def _storage_payload(payload: Any) -> Any:
    if not isinstance(payload, Mapping):
        return payload
    storage = {}
    for key, value in payload.items():
        if isinstance(value, (Mapping, list, tuple, pd.DataFrame, np.ndarray)):
            storage[key] = json.dumps(_json_ready(value), sort_keys=True)
        else:
            storage[key] = _json_ready(value)
    return storage


def _payload_value(payload: Mapping[str, Any], key: str, default=None):
    if not isinstance(payload, Mapping) or key not in payload:
        return default
    return _decode_payload_value(payload.get(key), default=default)


def _decode_payload_value(value, default=None):
    if isinstance(value, str):
        text = value.strip()
        if text == "null":
            return None
        if text and text[0] in "[{\"":
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return value
    return default if value is None else value


def _json_ready(value):
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _json_ready(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value



def _event_seconds(gaitrite_loaded: Mapping[str, Any]) -> dict[str, list[float]]:
    seconds = gaitrite_loaded.get("seconds", {}) if isinstance(gaitrite_loaded, Mapping) else {}
    events = seconds.get("gaitEvents", {}) if isinstance(seconds, Mapping) else {}
    return {
        "L": [float(v) for v in events.get("leftHeelStrikes", []) if v is not None],
        "R": [float(v) for v in events.get("rightHeelStrikes", []) if v is not None],
    }


def _cycle_start_end(events: Mapping[str, list[float]], side: str, side_cycle_index: int):
    strikes = events.get(side, [])
    if side_cycle_index + 1 >= len(strikes):
        return None
    return strikes[side_cycle_index], strikes[side_cycle_index + 1]


def _cycle_number(cycle_row: Mapping[str, Any], default: int) -> int:
    raw = cycle_row.get("GaitRiteRow") or default
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return int(default)


def _slice_xsens(data, start_seconds: float, end_seconds: float) -> dict[str, list[float]]:
    if not isinstance(data, Mapping):
        return {}
    fs = float(data.get("sampling_frequency") or 100)
    signals = data.get("processed_kinematics") or {}
    return _slice_and_resample_signals(signals, start_seconds, end_seconds, fs)


def _slice_delsys(data, start_seconds: float, end_seconds: float) -> dict[str, list[float]]:
    if not isinstance(data, Mapping):
        return {}
    fs = float(data.get("sampling_frequency") or 2000)
    signals = data.get("processed_emg") or {}
    return _slice_and_resample_signals(signals, start_seconds, end_seconds, fs)


def _slice_and_resample_signals(signals: Mapping[str, Any], start_seconds: float, end_seconds: float, fs: float) -> dict[str, list[float]]:
    start = max(int(round(start_seconds * fs)), 0)
    end = max(int(round(end_seconds * fs)), start + 1)
    out = {}
    for name, values in signals.items():
        arr = _as_float_array(values)
        if arr.size == 0:
            continue
        sliced = arr[min(start, arr.size): min(end, arr.size)]
        if sliced.size < 2:
            continue
        out[str(name)] = _resample_to_points(sliced, NUM_POINTS).tolist()
    return out


def _resample_to_points(values: np.ndarray, n_points: int) -> np.ndarray:
    values = _as_float_array(values)
    if values.size == 0:
        return np.full(n_points, np.nan)
    if values.size == 1:
        return np.full(n_points, values[0])
    old_x = np.linspace(0, 1, values.size)
    new_x = np.linspace(0, 1, n_points)
    return np.interp(new_x, old_x, values)


def _as_float_array(values: Any) -> np.ndarray:
    return np.asarray(values, dtype=float).reshape(-1)


def _nan_like(values: Any) -> list[float]:
    arr = _as_float_array(values)
    return np.full(arr.size, np.nan).tolist()


def _has_normalized_cycles(cycles: pd.DataFrame) -> bool:
    for _, row in cycles.iterrows():
        data = _row_value(row, "data")
        if isinstance(data, Mapping) and _payload_value(data, "delsys_normalized_time_normalized"):
            return True
    return False


def _merge_side_signals(current: Mapping[str, Any], nxt: Mapping[str, Any], field: str, current_side: str, next_side: str) -> dict[str, Any]:
    merged = {}
    for source, side in ((current, current_side), (nxt, next_side)):
        signals = _payload_value(source, field, {}) or {}
        for name, values in signals.items():
            text = str(name).upper()
            if text.startswith(side):
                merged[name] = values
    return merged


def _analysis_export_frame(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        base = {key: _clean_schema_value(row.get(key)) for key in SCHEMA_KEYS if key in row}
        if "__record_id" in row:
            base["source_record_id"] = row["__record_id"]
        data = _row_value(row, "data")
        if isinstance(data, Mapping):
            rows.append(base | _flatten_payload_for_export(data))
        else:
            rows.append(base)
    return pd.DataFrame(rows)


def _flatten_payload_for_export(data: Mapping[str, Any]) -> dict[str, Any]:
    out = {}
    for key, value in data.items():
        if isinstance(value, Mapping):
            for subkey, subvalue in value.items():
                flat_key = f"{key}_{_safe_name(subkey)}"
                out[flat_key] = _export_value(subvalue)
        else:
            out[_safe_name(key)] = _export_value(value)
    return out


def _export_value(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (Mapping, list, tuple, np.ndarray)):
        return _json_safe(value)
    return value


def _json_safe(value: Any):
    import json

    def convert(item):
        if isinstance(item, Mapping):
            return {str(k): convert(v) for k, v in item.items()}
        if isinstance(item, np.ndarray):
            return convert(item.tolist())
        if isinstance(item, (list, tuple)):
            return [convert(v) for v in item]
        if isinstance(item, np.generic):
            return item.item()
        return item

    return json.dumps(convert(value), sort_keys=True)


def _row_value(row, key: str):
    try:
        return row[key]
    except Exception:
        return None


def _trial_uid(metadata: Mapping[str, Any]) -> str:
    return "_".join(str(metadata.get(key)) for key in TRIAL_KEYS if metadata.get(key) not in (None, "None", ""))


def _safe_name(value: Any) -> str:
    text = str(value).strip()
    cleaned = "".join(char if char.isalnum() else "_" for char in text).strip("_")
    return cleaned or "value"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _require_rows(df: pd.DataFrame, table_name: str, command_name: str) -> None:
    if df.empty:
        raise AnalysisPreconditionError(f"{table_name} rows are required. Run {command_name} first.")


def _looks_like_missing_table(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}"
    return "CatalogException" in text or "does not exist" in text or "not found" in text

def _looks_like_json_decode(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}"
    return "JSONDecodeError" in text or "Expecting value" in text



def _looks_like_duplicate_record(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}"
    return "Duplicate key" in text and "record_id" in text
