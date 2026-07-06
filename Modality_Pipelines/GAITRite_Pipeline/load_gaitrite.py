"""
GAITRite loading and trial/cycle processing methods.

Translated from the shared MATLAB load-gaitrite library:
loadGaitRiteOneFile.m, preprocessGaitRiteOneTrial.m, and
DistributeGaitRiteDataToSeparateTable.m.

@author shensley01
@version 0.1.0
@last_updated 2026-07-06
@change_log
    - 2026-07-06 v0.1.0: Added Python GAITRite Excel loader, trial preprocessing,
      hardware-frame conversion, and cycle-row distribution.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

GAITRITE_CONFIG_PATH = Path(__file__).with_name("gaitrite_config.json")


_VECTOR_PREFIXES = ("L_", "R_", "All_")


def load_gaitrite_config(config_path: str | Path = GAITRITE_CONFIG_PATH) -> dict[str, Any]:
    """Load GAITRite modality-specific processing config."""
    with Path(config_path).open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def load_gaitrite_file(
    gaitrite_path: str | Path,
    gaitrite_config: Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    """Load one GAITRite Excel workbook into one processed row per walk/trial.

    This is the Python equivalent of MATLAB ``loadGaitRiteOneFile``. It reads
    the footfall-level rows, separates unique GAITRite trial IDs, and calls
    ``preprocess_gaitrite_one_trial`` for each trial.
    """
    config = dict(gaitrite_config or load_gaitrite_config())
    raw = pd.read_excel(gaitrite_path, header=None, dtype=object)
    header_idx = _find_header_row(raw, config)
    headers = _clean_header(raw.iloc[header_idx].tolist())

    anchor = _column_index(headers, _aliases(config, "LEFT_RIGHT"))
    trial_idx = _column_index(headers, _aliases(config, "GAIT_ID"), anchor=anchor)
    time_idx = _optional_column_index(headers, _aliases(config, "TIME"), anchor=anchor)

    data = raw.iloc[header_idx + 1 :].reset_index(drop=True)
    numeric_trial = pd.to_numeric(data.iloc[:, trial_idx], errors="coerce")
    numeric_foot = pd.to_numeric(data.iloc[:, anchor], errors="coerce")
    data = data[numeric_trial.notna() & numeric_foot.notna()].copy()
    numeric_trial = numeric_trial.loc[data.index]

    trial_ids = pd.unique(numeric_trial)
    rows: list[dict[str, Any]] = []
    for trial_id in trial_ids:
        trial_data = data.loc[numeric_trial == trial_id].copy()
        processed = preprocess_gaitrite_one_trial(config, headers, trial_data)
        processed["DateTimeSaved_GaitRite"] = _date_time_saved(trial_data, time_idx)
        processed["GaitRiteTrialId"] = _json_scalar(trial_id)
        rows.append(processed)

    return pd.DataFrame(rows)


def preprocess_gaitrite_one_trial(
    gaitrite_config: Mapping[str, Any],
    header_row: Sequence[str],
    data: pd.DataFrame,
) -> dict[str, Any]:
    """Preprocess one parsed GAITRite trial.

    This function mirrors MATLAB ``preprocessGaitRiteOneTrial`` and returns a
    single dictionary suitable for a one-row pandas DataFrame or SciDB payload.
    """
    fs = float(gaitrite_config["SAMPLING_FREQUENCY"])
    anchor = _column_index(header_row, _aliases(gaitrite_config, "LEFT_RIGHT"))

    idx = {
        key: _column_index(header_row, _aliases(gaitrite_config, key), anchor=anchor)
        for key in (
            "LEFT_RIGHT",
            "HEEL_ON",
            "TOE_OFF",
            "HEEL_OFF",
            "TOE_ON",
            "STEP_LENGTH",
            "SWING_TIME",
            "STEP_TIME",
            "STANCE_TIME",
            "STRIDE_TIME",
            "STRIDE_LENGTH",
            "STEP_WIDTH",
            "STRIDE_WIDTH",
            "STRIDE_VELOCITY",
            "SINGLE_SUPPORT_TIME",
            "DOUBLE_SUPPORT_TIME",
        )
    }

    numeric = data.apply(pd.to_numeric, errors="coerce")
    zero_to_nan = [
        "STEP_LENGTH",
        "SWING_TIME",
        "STEP_TIME",
        "STANCE_TIME",
        "STRIDE_TIME",
        "STRIDE_LENGTH",
        "STEP_WIDTH",
        "STRIDE_WIDTH",
        "HEEL_ON",
        "HEEL_OFF",
        "TOE_ON",
        "TOE_OFF",
        "STRIDE_VELOCITY",
        "SINGLE_SUPPORT_TIME",
        "DOUBLE_SUPPORT_TIME",
    ]
    for key in zero_to_nan:
        col = idx[key]
        numeric.iloc[:, col] = numeric.iloc[:, col].mask(numeric.iloc[:, col] == 0, np.nan)

    left_right = _series(numeric, idx["LEFT_RIGHT"]).astype(float)
    heel_on = _series(numeric, idx["HEEL_ON"])
    heel_off = _series(numeric, idx["HEEL_OFF"])
    toe_on = _series(numeric, idx["TOE_ON"])
    toe_off = _series(numeric, idx["TOE_OFF"])
    step_len = _series(numeric, idx["STEP_LENGTH"]) / 100.0
    swing_durations = _series(numeric, idx["SWING_TIME"])
    stride_lens = _series(numeric, idx["STRIDE_LENGTH"]) / 100.0
    stride_durations = _series(numeric, idx["STRIDE_TIME"])
    stance_durations = _series(numeric, idx["STANCE_TIME"])
    step_widths = _series(numeric, idx["STEP_WIDTH"]) / 100.0
    stride_widths = _series(numeric, idx["STRIDE_WIDTH"]) / 100.0
    step_durations = _series(numeric, idx["STEP_TIME"])
    stride_velocities = _series(numeric, idx["STRIDE_VELOCITY"]) / 100.0
    single_support_time = _series(numeric, idx["SINGLE_SUPPORT_TIME"])
    double_support_time = _series(numeric, idx["DOUBLE_SUPPORT_TIME"])

    left_right = _normalize_left_right(left_right)
    if len(left_right) > 1 and np.any(np.diff(left_right) == 0):
        raise ValueError("Left and right GAITRite steps are not alternating.")

    left_events_idx = left_right == 0
    right_events_idx = left_right == 1
    num_heel_strikes = len(left_right)

    processed: dict[str, Any] = {
        "L_Idx_GR": _to_list(left_events_idx),
        "R_Idx_GR": _to_list(right_events_idx),
        "All_Idx_GR": _to_list(left_right.astype(bool)),
        "L_StepLengths_GR": _to_list(step_len[left_events_idx]),
        "R_StepLengths_GR": _to_list(step_len[right_events_idx]),
        "All_StepLengths_GR": _to_list(step_len),
        "L_SwingDurations_GR": _to_list(swing_durations[left_events_idx]),
        "R_SwingDurations_GR": _to_list(swing_durations[right_events_idx]),
        "All_SwingDurations_GR": _to_list(swing_durations),
        "L_StrideLengths_GR": _to_list(stride_lens[left_events_idx]),
        "R_StrideLengths_GR": _to_list(stride_lens[right_events_idx]),
        "All_StrideLengths_GR": _to_list(stride_lens),
        "L_StanceDurations_GR": _to_list(stance_durations[left_events_idx]),
        "R_StanceDurations_GR": _to_list(stance_durations[right_events_idx]),
        "All_StanceDurations_GR": _to_list(stance_durations),
        "L_StepWidths_GR": _to_list(step_widths[left_events_idx]),
        "R_StepWidths_GR": _to_list(step_widths[right_events_idx]),
        "All_StepWidths_GR": _to_list(step_widths),
        "L_StrideWidths_GR": _to_list(stride_widths[left_events_idx]),
        "R_StrideWidths_GR": _to_list(stride_widths[right_events_idx]),
        "All_StrideWidths_GR": _to_list(stride_widths),
        "L_StepDurations_GR": _to_list(step_durations[left_events_idx]),
        "R_StepDurations_GR": _to_list(step_durations[right_events_idx]),
        "All_StepDurations_GR": _to_list(step_durations),
        "L_StrideDurations_GR": _to_list(stride_durations[left_events_idx]),
        "R_StrideDurations_GR": _to_list(stride_durations[right_events_idx]),
        "All_StrideDurations_GR": _to_list(stride_durations),
        "L_NumFootfalls_GR": int(np.sum(left_events_idx)),
        "R_NumFootfalls_GR": int(np.sum(right_events_idx)),
        "All_NumFootfalls_GR": int(num_heel_strikes),
        "L_StrideVelocities_GR": _to_list(stride_velocities[left_events_idx]),
        "R_StrideVelocities_GR": _to_list(stride_velocities[right_events_idx]),
        "All_StrideVelocities_GR": _to_list(stride_velocities),
        "L_SwingPhasePerc_GR": _to_list(_safe_divide(swing_durations[left_events_idx], stride_durations[left_events_idx])),
        "R_SwingPhasePerc_GR": _to_list(_safe_divide(swing_durations[right_events_idx], stride_durations[right_events_idx])),
        "All_SwingPhasePerc_GR": _to_list(_safe_divide(swing_durations, stride_durations)),
        "L_StancePhasePerc_GR": _to_list(1 - _safe_divide(swing_durations[left_events_idx], stride_durations[left_events_idx])),
        "R_StancePhasePerc_GR": _to_list(1 - _safe_divide(swing_durations[right_events_idx], stride_durations[right_events_idx])),
        "All_StancePhasePerc_GR": _to_list(1 - _safe_divide(swing_durations, stride_durations)),
        "All_Single_Support_Time_GR": _to_list(single_support_time),
        "L_Single_Support_Time_GR": _to_list(single_support_time[left_events_idx]),
        "R_Single_Support_Time_GR": _to_list(single_support_time[right_events_idx]),
        "All_Double_Support_Time_GR": _to_list(double_support_time),
        "L_Double_Support_Time_GR": _to_list(double_support_time[left_events_idx]),
        "R_Double_Support_Time_GR": _to_list(double_support_time[right_events_idx]),
    }

    if len(left_right) and left_events_idx[0]:
        num_steps_l = int(np.sum(left_events_idx) - 1)
        num_steps_r = int(np.sum(right_events_idx))
    elif len(left_right) and right_events_idx[0]:
        num_steps_l = int(np.sum(left_events_idx))
        num_steps_r = int(np.sum(right_events_idx) - 1)
    else:
        num_steps_l = 0
        num_steps_r = 0

    processed.update(
        {
            "L_NumSteps_GR": num_steps_l,
            "R_NumSteps_GR": num_steps_r,
            "All_NumSteps_GR": num_steps_l + num_steps_r,
            "L_NumGaitCycles_GR": max(int(np.sum(left_events_idx) - 1), 0),
            "R_NumGaitCycles_GR": max(int(np.sum(right_events_idx) - 1), 0),
        }
    )
    processed["All_NumGaitCycles_GR"] = processed["L_NumGaitCycles_GR"] + processed["R_NumGaitCycles_GR"]

    seconds = {
        "gaitEvents": {
            "leftHeelStrikes": _to_list(heel_on[left_events_idx]),
            "leftToeOffs": _to_list(toe_off[left_events_idx]),
            "leftHeelOffs": _to_list(heel_off[left_events_idx]),
            "leftToeOns": _to_list(toe_on[left_events_idx]),
            "rightHeelStrikes": _to_list(heel_on[right_events_idx]),
            "rightToeOffs": _to_list(toe_off[right_events_idx]),
            "rightHeelOffs": _to_list(heel_off[right_events_idx]),
            "rightToeOns": _to_list(toe_on[right_events_idx]),
        }
    }

    left_stance, right_stance, left_swing, right_swing = _gait_phase_start_stop(
        left_right, heel_on, toe_off
    )
    seconds["gaitPhases"] = {
        "leftStanceStartStop": _to_nested_list(left_stance),
        "rightStanceStartStop": _to_nested_list(right_stance),
        "leftSwingStartStop": _to_nested_list(left_swing),
        "rightSwingStartStop": _to_nested_list(right_swing),
    }
    seconds["gaitPhasesDurations"] = {
        "leftStanceDurations": _to_list(left_stance[:, 1] - left_stance[:, 0]) if len(left_stance) else [],
        "rightStanceDurations": _to_list(right_stance[:, 1] - right_stance[:, 0]) if len(right_stance) else [],
        "leftSwingDurations": _to_list(left_swing[:, 1] - left_swing[:, 0]) if len(left_swing) else [],
        "rightSwingDurations": _to_list(right_swing[:, 1] - right_swing[:, 0]) if len(right_swing) else [],
    }

    processed["seconds"] = seconds
    processed["frames"] = get_hardware_indices_from_seconds(seconds, fs)
    return processed


def distribute_gaitrite_data_to_separate_table(
    gr_table: pd.DataFrame | Sequence[Mapping[str, Any]] | Mapping[str, Any],
    col_names_to_remove: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Split trial-level GAITRite rows into one row per GAITRite footfall row.

    This mirrors MATLAB ``distributeGaitRiteDataToSeparateTable``. Scalar columns
    are repeated on each output row, and ``All_*`` vector columns become one
    row-level value per GAITRite row.
    """
    table = _as_dataframe(gr_table)
    col_names_to_remove = set(col_names_to_remove or ["All_Idx_GR"])
    records: list[dict[str, Any]] = []

    for _, row in table.iterrows():
        all_idx = _as_list(row["All_Idx_GR"])
        l_idx = _as_list(row["L_Idx_GR"])
        r_idx = _as_list(row["R_Idx_GR"])
        if not (len(l_idx) == len(all_idx) == len(r_idx)):
            raise ValueError("GAITRite L/R/all index vectors must have the same length.")

        scalar_values = {
            key: value
            for key, value in row.items()
            if not _is_vector_column_value(value) and key not in {"seconds", "frames"}
        }
        all_columns = [
            name
            for name in table.columns
            if name.startswith("All_") and name not in col_names_to_remove
        ]

        for row_num in range(len(all_idx)):
            start_foot = "L" if bool(l_idx[row_num]) else "R" if bool(r_idx[row_num]) else None
            out = dict(scalar_values)
            out["GaitRiteRow"] = f"{row_num + 1:02d}"
            out["StartFoot"] = start_foot
            for col_name in all_columns:
                values = _as_list(row[col_name])
                out[col_name.removeprefix("All_")] = values[row_num] if row_num < len(values) else None
            records.append(out)

    return pd.DataFrame(records)


def get_hardware_indices_from_seconds(seconds_struct: Mapping[str, Any], fs: float) -> dict[str, Any]:
    """Convert nested second values to sample/frame indices for one hardware FS."""
    digits = len(str(int(fs)))
    return {
        field: {
            subfield: _seconds_to_indices(value, fs, digits)
            for subfield, value in subfields.items()
        }
        for field, subfields in seconds_struct.items()
    }


def process_gaitrite_raw_file(raw_file_record: Mapping[str, Any] | str | Path) -> pd.DataFrame:
    """Process one registered GAITRite raw-file record into trial-level output."""
    file_path = _file_path_from_record(raw_file_record)
    return load_gaitrite_file(file_path)


def distribute_gaitrite_loaded(gaitrite_loaded: pd.DataFrame | Mapping[str, Any]) -> pd.DataFrame:
    """Process one GAITRiteLoaded payload into row/cycle-level GAITRite output."""
    return distribute_gaitrite_data_to_separate_table(gaitrite_loaded)


def _find_header_row(raw: pd.DataFrame, config: Mapping[str, Any]) -> int:
    required = ["LEFT_RIGHT", "HEEL_ON", "TOE_OFF"]
    aliases_by_key = [_aliases(config, key) for key in required]
    for idx, row in raw.iterrows():
        headers = _clean_header(row.tolist())
        if all(_optional_column_index(headers, aliases) is not None for aliases in aliases_by_key):
            return int(idx)

    first_col = raw.iloc[:, 0].astype(str).str.contains("ID", case=False, na=False)
    if first_col.any():
        return int(first_col[first_col].index[0])

    raise ValueError("Could not find a GAITRite header row in workbook.")


def _aliases(config: Mapping[str, Any], key: str) -> list[str]:
    names = []
    column_name = config.get("COLUMN_NAMES", {}).get(key)
    if column_name:
        names.append(str(column_name))
    names.extend(str(value) for value in config.get("COLUMN_ALIASES", {}).get(key, []))
    return list(dict.fromkeys(name.strip() for name in names if name and name.strip()))


def _column_index(headers: Sequence[str], names: Sequence[str], anchor: int | None = None) -> int:
    match = _optional_column_index(headers, names, anchor=anchor)
    if match is None:
        raise KeyError(f"Could not find any GAITRite column matching {list(names)!r}.")
    return match


def _optional_column_index(
    headers: Sequence[str],
    names: Sequence[str],
    anchor: int | None = None,
) -> int | None:
    normalized_names = {_normalize_name(name) for name in names}
    matches = [
        idx for idx, header in enumerate(headers) if _normalize_name(header) in normalized_names
    ]
    if not matches:
        return None
    if anchor is None:
        return matches[0]
    return min(matches, key=lambda idx: abs(idx - anchor))


def _clean_header(values: Sequence[Any]) -> list[str]:
    return ["" if pd.isna(value) else str(value).strip() for value in values]


def _normalize_name(value: Any) -> str:
    return " ".join(str(value).strip().lower().split())


def _series(data: pd.DataFrame, idx: int) -> np.ndarray:
    return data.iloc[:, idx].to_numpy(dtype=float)


def _normalize_left_right(values: np.ndarray) -> np.ndarray:
    normalized = []
    for value in values:
        if pd.isna(value):
            normalized.append(np.nan)
        elif float(value) in (0.0, 1.0):
            normalized.append(int(value))
        else:
            raise ValueError(f"Unexpected GAITRite left/right foot code {value!r}; expected 0/1.")
    result = np.asarray(normalized, dtype=float)
    if np.isnan(result).any():
        raise ValueError("GAITRite left/right foot column contains missing values.")
    return result.astype(int)


def _gait_phase_start_stop(
    left_right: np.ndarray,
    heel_on: np.ndarray,
    toe_off: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    left_stance: list[list[float]] = []
    right_stance: list[list[float]] = []
    left_swing: list[list[float]] = []
    right_swing: list[list[float]] = []

    for idx in range(max(len(left_right) - 2, 0)):
        if left_right[idx] == 0:
            left_stance.append([heel_on[idx], toe_off[idx]])
            left_swing.append([toe_off[idx], heel_on[idx + 2]])
        else:
            right_stance.append([heel_on[idx], toe_off[idx]])
            right_swing.append([toe_off[idx], heel_on[idx + 2]])

    return (
        np.asarray(left_stance, dtype=float).reshape(-1, 2),
        np.asarray(right_stance, dtype=float).reshape(-1, 2),
        np.asarray(left_swing, dtype=float).reshape(-1, 2),
        np.asarray(right_swing, dtype=float).reshape(-1, 2),
    )


def _safe_divide(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.divide(numerator, denominator)


def _date_time_saved(data: pd.DataFrame, time_idx: int | None) -> str | None:
    if time_idx is None:
        return None
    values = data.iloc[:, time_idx].dropna()
    if values.empty:
        return None
    parsed = pd.to_datetime(values.iloc[0], errors="coerce")
    if pd.isna(parsed):
        return str(values.iloc[0])
    if parsed.tzinfo is None:
        parsed = parsed.tz_localize("America/Chicago")
    return parsed.isoformat()


def _seconds_to_indices(value: Any, fs: float, digits: int) -> Any:
    arr = np.asarray(value, dtype=float)
    rounded_seconds = np.round(arr, max(digits - 1, 0))
    indices = np.round(rounded_seconds * fs)
    return _to_nested_list(indices)


def _to_list(values: Any) -> list[Any]:
    arr = np.asarray(values)
    return [_json_scalar(value) for value in arr.tolist()]


def _to_nested_list(values: Any) -> Any:
    arr = np.asarray(values)
    if arr.ndim == 0:
        return _json_scalar(arr.item())
    return _json_clean(arr.tolist())


def _json_clean(value: Any) -> Any:
    if isinstance(value, list):
        return [_json_clean(item) for item in value]
    return _json_scalar(value)


def _json_scalar(value: Any) -> Any:
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if math.isnan(float(value)) else float(value)
    if pd.isna(value):
        return None
    return value


def _as_dataframe(value: pd.DataFrame | Sequence[Mapping[str, Any]] | Mapping[str, Any]) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value
    if isinstance(value, Mapping):
        if "gaitrite_trials" in value:
            return pd.DataFrame(value["gaitrite_trials"])
        return pd.DataFrame([value])
    return pd.DataFrame(list(value))


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _is_vector_column_value(value: Any) -> bool:
    return isinstance(value, (list, tuple, np.ndarray, dict))


def _file_path_from_record(raw_file_record: Mapping[str, Any] | str | Path) -> Path:
    if isinstance(raw_file_record, (str, Path)):
        return Path(raw_file_record)
    if "file_path" in raw_file_record:
        return _path_from_field(raw_file_record["file_path"])
    if "path" in raw_file_record:
        return _path_from_field(raw_file_record["path"])
    raise KeyError("GAITRite raw_file_record must contain a file_path field.")


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
