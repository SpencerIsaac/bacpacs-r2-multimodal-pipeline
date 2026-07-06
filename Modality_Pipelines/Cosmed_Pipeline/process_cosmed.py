"""
COSMED loading methods for breath-by-breath metabolic records.

Translated from the shared MATLAB cosmed/loadCosmedData.m utility.

@author shensley01
@version 0.1.0
@last_updated 2026-07-06
@change_log
    - 2026-07-06 v0.1.0: Added Python COSMED CSV/XLSX loader and raw-file
      processing entry point for SciDB wrappers.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

COSMED_CONFIG_PATH = Path(__file__).with_name("cosmed_config.json")
SECONDS_PER_DAY = 24 * 60 * 60


def load_cosmed_config(config_path: str | Path = COSMED_CONFIG_PATH) -> dict[str, Any]:
    """Load COSMED modality-specific processing config."""
    with Path(config_path).open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def load_cosmed_file(
    file_path: str | Path,
    cosmed_config: Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    """Load one COSMED CSV/XLSX export into a cleaned breath-by-breath table.

    The output mirrors MATLAB ``loadCosmedData``: time is converted to ``t_sec``,
    configured metabolic variables are numeric, invalid all-zero/all-NaN rows are
    removed, and the phase column is preserved when present.
    """
    path = Path(file_path)
    config = dict(cosmed_config or load_cosmed_config())
    raw = _read_raw_cosmed_export(path, config)

    time_column = config["TIME_COLUMN"]
    if time_column not in raw.columns:
        raise KeyError(f"COSMED file {path.name!r} is missing time column {time_column!r}.")

    output = pd.DataFrame()
    output["t_sec"] = raw[time_column].map(_parse_time_seconds)

    for output_name, source_name in config["NUMERIC_COLUMNS"].items():
        if source_name not in raw.columns:
            raise KeyError(f"COSMED file {path.name!r} is missing column {source_name!r}.")
        output[output_name] = pd.to_numeric(raw[source_name], errors="coerce")

    valid_time = output["t_sec"].notna() & (output["t_sec"] >= 0)
    raw = raw.loc[valid_time].reset_index(drop=True)
    output = output.loc[valid_time].reset_index(drop=True)
    output = output.sort_values("t_sec").reset_index(drop=True)

    numeric_columns = list(config["NUMERIC_COLUMNS"].keys())
    invalid_rows = output[numeric_columns].isna() | (output[numeric_columns] == 0)
    keep_rows = ~invalid_rows.all(axis=1)
    output = output.loc[keep_rows].reset_index(drop=True)
    raw = raw.loc[keep_rows].reset_index(drop=True)

    phase_column = config.get("PHASE_COLUMN", "Phase")
    if phase_column in raw.columns:
        output["Phase"] = raw[phase_column].astype("string")

    return output


def process_cosmed_raw_file(raw_file_record: Mapping[str, Any] | str | Path) -> pd.DataFrame:
    """Process one registered COSMED raw-file record into loaded COSMED output."""
    return load_cosmed_file(_file_path_from_record(raw_file_record))


def _read_raw_cosmed_export(path: Path, config: Mapping[str, Any]) -> pd.DataFrame:
    data_start_row = int(config.get("DATA_START_ROW", 4))
    rows_to_skip_after_header = max(data_start_row - 2, 0)

    if path.suffix.lower() == ".csv":
        skiprows = list(range(1, 1 + rows_to_skip_after_header))
        return pd.read_csv(path, header=0, skiprows=skiprows, dtype=object)

    if path.suffix.lower() in {".xlsx", ".xls"}:
        raw = pd.read_excel(path, header=0, dtype=object)
        return raw.iloc[rows_to_skip_after_header:].reset_index(drop=True)

    raise ValueError(f"Unsupported COSMED file extension {path.suffix!r}.")


def _parse_time_seconds(value: Any) -> float | None:
    if pd.isna(value):
        return None

    if isinstance(value, pd.Timestamp):
        return float(value.hour * 3600 + value.minute * 60 + value.second + value.microsecond / 1e6)

    if isinstance(value, datetime):
        return float(value.hour * 3600 + value.minute * 60 + value.second + value.microsecond / 1e6)

    if isinstance(value, time):
        return float(value.hour * 3600 + value.minute * 60 + value.second + value.microsecond / 1e6)

    if isinstance(value, timedelta):
        return value.total_seconds()

    if isinstance(value, (int, float, np.integer, np.floating)):
        number = float(value)
        if math.isnan(number):
            return None
        # Excel stores times as fractions of a day. If the value includes a date
        # serial, the fractional part still contains the time-of-day.
        fraction = number % 1
        return fraction * SECONDS_PER_DAY if fraction else number

    text = str(value).strip()
    if not text:
        return None

    parts = text.split(":")
    try:
        if len(parts) == 2:
            minutes, seconds = parts
            return float(minutes) * 60 + float(seconds)
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
        return float(text)
    except ValueError:
        parsed = pd.to_datetime(text, errors="coerce")
        if pd.isna(parsed):
            return None
        return float(parsed.hour * 3600 + parsed.minute * 60 + parsed.second + parsed.microsecond / 1e6)


def _file_path_from_record(raw_file_record: Mapping[str, Any] | str | Path) -> Path:
    if isinstance(raw_file_record, (str, Path)):
        return Path(raw_file_record)
    if "file_path" in raw_file_record:
        return _path_from_field(raw_file_record["file_path"])
    if "path" in raw_file_record:
        return _path_from_field(raw_file_record["path"])
    raise KeyError("COSMED raw_file_record must contain a file_path field.")


def _path_from_field(value: Any) -> Path:
    if hasattr(value, "iloc"):
        if len(value) == 0:
            raise ValueError("raw_file_record file_path field is empty.")
        value = value.iloc[0]
    elif isinstance(value, (list, tuple, np.ndarray)):
        if len(value) == 0:
            raise ValueError("raw_file_record file_path field is empty.")
        value = value[0]
    return Path(str(value))
