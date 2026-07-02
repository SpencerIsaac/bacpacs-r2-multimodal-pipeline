"""
Delsys EMG filtering methods ported from MATLAB.
Handles one muscle channel at a time, with optional notch filtering,
rectification, and low-pass envelope filtering.
Helper methods only; intended to be called by process_delsys.py.

@author shensley01
@version 0.4.0
@last_updated 2026-07-02
@change_log
    - 2026-07-02 v0.4.0: Added config-controlled optional notch filtering, defaulted off.
    - 2026-07-02 v0.3.0: Replaced scaffold with direct Python port of filterEMGOneMuscle and filterDelsys MATLAB logic.
    - 2026-07-02 v0.2.0: Ported MATLAB filterEMGOneMuscle and filterDelsys logic to Python.
    - 2026-07-01 v0.1.0: Created initial Delsys filtering module scaffold.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
from scipy.signal import butter, filtfilt, iirnotch


def _apply_optional_notch(
    signal: np.ndarray,
    filter_emg_config: Mapping[str, Any],
    emg_fs: float,
) -> np.ndarray:
    """Apply an optional power-line notch filter when enabled in config."""
    notch_config = filter_emg_config.get("NOTCH", {})
    if not notch_config.get("ENABLED", False):
        return signal

    notch_frequency = float(notch_config.get("FREQUENCY", 60))
    quality_factor = float(notch_config.get("QUALITY_FACTOR", 30))
    b_notch, a_notch = iirnotch(notch_frequency, quality_factor, fs=emg_fs)
    return filtfilt(b_notch, a_notch, signal)


def filter_emg_one_muscle(
    raw_emg_one_muscle: np.ndarray,
    filter_emg_config: Mapping[str, Any],
    emg_fs: float,
    rectify: bool = True,
) -> np.ndarray:
    """Parse configuration and filter one muscle's raw EMG data."""
    raw_emg_one_muscle = np.asarray(raw_emg_one_muscle, dtype=float)
    rectify = bool(rectify)

    if np.all(np.isnan(raw_emg_one_muscle)):
        return np.full(raw_emg_one_muscle.shape, np.nan, dtype=float)

    fpass = filter_emg_config["BANDPASS_CUTOFF"]
    order = filter_emg_config["BANDPASS_ORDER"]
    fcut = filter_emg_config["LOWPASS_CUTOFF"]
    lowpass_order = filter_emg_config.get("LOWPASS_ORDER", 2)

    b_band, a_band = butter(order, np.asarray(fpass, dtype=float) / (emg_fs / 2), btype="bandpass")
    b_low, a_low = butter(lowpass_order, fcut / (emg_fs / 2), btype="low")

    emg_subtracted_mean = raw_emg_one_muscle - np.nanmean(raw_emg_one_muscle)
    emg_notched = _apply_optional_notch(emg_subtracted_mean, filter_emg_config, emg_fs)
    emg_bandpass = filtfilt(b_band, a_band, emg_notched)

    if rectify:
        emg_rectified = np.abs(emg_bandpass)
        filtered_emg = filtfilt(b_low, a_low, emg_rectified)
    else:
        filtered_emg = emg_bandpass

    return filtered_emg


def filter_delsys(
    loaded_data: Mapping[str, np.ndarray],
    config: Mapping[str, Any],
    fs: float,
) -> dict[str, np.ndarray]:
    """Filter each muscle channel in a loaded Delsys data record."""
    filtered_data = {}

    for muscle_name, muscle_data in loaded_data.items():
        filtered_data[muscle_name] = filter_emg_one_muscle(muscle_data, config, fs)

    return filtered_data
