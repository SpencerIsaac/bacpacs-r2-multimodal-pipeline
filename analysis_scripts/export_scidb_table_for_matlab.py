"""Export a BACPACS SciDB table to CSV for MATLAB ad hoc analysis."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from Modality_Pipelines.common.common_config import configure_scistack_database
from Modality_Pipelines.common.study_config import load_study_config
from Modality_Pipelines.common.table_registry import get_table_class


SCHEMA_FILTERS = ("participant_number", "visit", "test", "condition", "speed", "trial", "cycle")
INDEX_COLUMNS = (*SCHEMA_FILTERS, "__record_id")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", default="R1", choices=["R1", "R2"])
    parser.add_argument("--table", default="XsensProcessed")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--layout",
        choices=["analysis", "timeseries", "records"],
        default="analysis",
        help=(
            "analysis/timeseries expands processed trial payloads into one row per frame/sample; "
            "records preserves one database record per row and JSON-encodes nested payloads."
        ),
    )
    parser.add_argument("--include-rid", action="store_true", default=True)
    for key in SCHEMA_FILTERS:
        parser.add_argument(f"--{key.replace('_', '-')}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    study_config = load_study_config(args.study)
    db = configure_scistack_database(study_config=study_config)
    table_class = _resolve_table_class(args.study, args.table)
    metadata = {
        key: getattr(args, key)
        for key in SCHEMA_FILTERS
        if getattr(args, key) not in (None, "")
    }

    raw_df = db.load_all_as_df(table_class, metadata=metadata or None, include_rid=args.include_rid)
    if args.layout in {"analysis", "timeseries"}:
        export_df = _expand_timeseries_rows(raw_df)
        layout = "analysis" if args.layout == "analysis" else "timeseries"
        if export_df.empty and not raw_df.empty:
            export_df = _flatten_object_columns(raw_df.copy())
            layout = "records"
    else:
        export_df = _flatten_object_columns(raw_df.copy())
        layout = "records"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    export_df.to_csv(args.output, index=False)
    print(
        json.dumps(
            {
                "study": args.study,
                "table": table_class.__name__,
                "source_records": int(len(raw_df)),
                "rows": int(len(export_df)),
                "columns": list(export_df.columns),
                "output": str(args.output),
                "metadata": metadata,
                "layout": layout,
            }
        )
    )
    return 0


def _resolve_table_class(study: str, table_name: str):
    """Resolve exactly the requested table class for a study.

    R1 and R2 do not share a table-name prefix convention, so callers must pass
    the real table class name, e.g. R1DelsysProcessed for R1 and DelsysProcessed
    for R2.
    """
    return get_table_class(study, table_name)


def _expand_timeseries_rows(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if "data" not in df.columns:
        return pd.DataFrame(rows)

    for _, record in df.iterrows():
        data = record.get("data")
        index_values = _record_index_values(record, df.columns)

        if isinstance(data, pd.DataFrame):
            rows.extend(_dataframe_payload_rows(index_values, data))
            continue
        if not isinstance(data, Mapping):
            continue

        _enrich_index_from_payload(index_values, data)
        rows.extend(_xsens_timeseries_rows(index_values, data))
        rows.extend(_delsys_timeseries_rows(index_values, data))

    return pd.DataFrame(rows)



def _record_index_values(record: pd.Series, columns: Sequence[str]) -> dict[str, Any]:
    index_values = {
        _analysis_column_name(column): _scalar_value(record[column])
        for column in INDEX_COLUMNS
        if column in columns
    }
    if "source_record_id" not in index_values and "__record_id" in record:
        index_values["source_record_id"] = _scalar_value(record["__record_id"])
    index_values.pop("__record_id", None)
    index_values["trial_uid"] = _trial_uid(index_values)
    return index_values


def _enrich_index_from_payload(index_values: dict[str, Any], data: Mapping[str, Any]) -> None:
    if "file_path" in data:
        source_file = str(data["file_path"])
        index_values["source_file"] = source_file
        index_values["source_file_name"] = Path(source_file).name
    if "sampling_frequency" in data:
        index_values["sampling_frequency"] = _scalar_value(data["sampling_frequency"])
    metadata = data.get("metadata", {})
    if isinstance(metadata, Mapping):
        for metadata_key in ("loader", "subject_label", "frame_rate"):
            if metadata_key in metadata:
                index_values[metadata_key] = _scalar_value(metadata[metadata_key])


def _dataframe_payload_rows(index_values: Mapping[str, Any], payload: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for payload_index, payload_row in payload.reset_index(drop=True).iterrows():
        row = dict(index_values)
        row["analysis_row_index"] = int(payload_index)
        for column, value in payload_row.items():
            row[_matlab_column_name(column)] = _flatten_analysis_cell(value)
        rows.append(row)
    return rows

def _xsens_timeseries_rows(index_values: Mapping[str, Any], data: Mapping[str, Any]) -> list[dict[str, Any]]:
    signals = data.get("processed_kinematics")
    if not isinstance(signals, Mapping):
        return []

    frame_index = _as_1d_array(data.get("frame_index"))
    time_seconds = _as_1d_array(data.get("time_seconds"))
    length = _timeseries_length(signals, fallback=len(frame_index))
    if length == 0:
        return []
    if len(frame_index) != length:
        frame_index = np.arange(length)
    if len(time_seconds) != length:
        sampling_frequency = index_values.get("sampling_frequency")
        if sampling_frequency:
            time_seconds = np.arange(length, dtype=float) / float(sampling_frequency)
        else:
            time_seconds = np.full(length, np.nan)

    rows = []
    signal_arrays = {
        _matlab_column_name(name): _as_1d_array(values)
        for name, values in signals.items()
        if len(_as_1d_array(values)) == length
    }
    for idx in range(length):
        row = dict(index_values)
        row["sample_index"] = idx
        row["frame_index"] = _scalar_value(frame_index[idx])
        row["time_seconds"] = _scalar_value(time_seconds[idx])
        for name, values in signal_arrays.items():
            row[name] = _scalar_value(values[idx])
        rows.append(row)
    return rows


def _delsys_timeseries_rows(index_values: Mapping[str, Any], data: Mapping[str, Any]) -> list[dict[str, Any]]:
    processed = data.get("processed_emg")
    normalized = data.get("normalized_emg")
    if not isinstance(processed, Mapping):
        return []

    signal_groups = [("processed", processed)]
    if isinstance(normalized, Mapping):
        signal_groups.append(("normalized", normalized))

    length = 0
    for _, signals in signal_groups:
        length = max(length, _timeseries_length(signals))
    if length == 0:
        return []

    signal_arrays = {}
    for prefix, signals in signal_groups:
        for name, values in signals.items():
            array = _as_1d_array(values)
            if len(array) == length:
                signal_arrays[f"{prefix}_{_matlab_column_name(name)}"] = array

    sampling_frequency = index_values.get("sampling_frequency")
    rows = []
    for idx in range(length):
        row = dict(index_values)
        row["sample_index"] = idx
        if sampling_frequency:
            row["time_seconds"] = idx / float(sampling_frequency)
        for name, values in signal_arrays.items():
            row[name] = _scalar_value(values[idx])
        rows.append(row)
    return rows


def _timeseries_length(signals: Mapping[str, Any], fallback: int = 0) -> int:
    lengths = [len(_as_1d_array(values)) for values in signals.values()]
    lengths = [length for length in lengths if length > 0]
    if not lengths:
        return fallback
    return max(set(lengths), key=lengths.count)


def _as_1d_array(value: Any) -> np.ndarray:
    if value is None:
        return np.asarray([])
    array = np.asarray(value)
    if array.ndim == 0:
        return array.reshape(1)
    return array.reshape(-1)



def _analysis_column_name(column: str) -> str:
    return "source_record_id" if column == "__record_id" else column


def _trial_uid(index_values: Mapping[str, Any]) -> str:
    parts = [
        index_values.get("participant_number", ""),
        index_values.get("visit", ""),
        index_values.get("test", ""),
        index_values.get("condition", ""),
        index_values.get("speed", ""),
        index_values.get("trial", ""),
        index_values.get("cycle", ""),
    ]
    return "_".join(str(part) for part in parts if str(part) not in {"", "None", "nan"})

def _matlab_column_name(value: Any) -> str:
    text = str(value).strip()
    cleaned = []
    for char in text:
        cleaned.append(char if char.isalnum() else "_")
    name = "".join(cleaned).strip("_") or "value"
    if name[0].isdigit():
        name = f"v_{name}"
    return name



def _flatten_analysis_cell(value: Any):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        value = value.tolist()
    if isinstance(value, Mapping) or isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return json.dumps(_json_safe(value), sort_keys=True)
    return value

def _flatten_object_columns(df: pd.DataFrame) -> pd.DataFrame:
    for column in df.columns:
        if df[column].dtype == "object":
            df[column] = df[column].map(_flatten_value)
    return df


def _flatten_value(value: Any):
    if isinstance(value, Mapping):
        return json.dumps(_json_safe(value), sort_keys=True)
    if isinstance(value, (list, tuple, np.ndarray)):
        return json.dumps(_json_safe(value))
    if isinstance(value, np.generic):
        return value.item()
    return value


def _json_safe(value: Any):
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return value


def _scalar_value(value: Any):
    if isinstance(value, np.generic):
        return value.item()
    return value


if __name__ == "__main__":
    raise SystemExit(main())