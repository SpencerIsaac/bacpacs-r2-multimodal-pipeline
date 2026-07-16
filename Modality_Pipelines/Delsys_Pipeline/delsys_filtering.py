"""
Delsys EMG filtering methods.

Current first-pass processing follows the configured Delsys method:
1. subtract channel mean
2. optional notch filter
3. Butterworth bandpass
4. full-wave rectification
5. RMS moving-window smoothing
6. optional dynamic normalization by trial maximum
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
    processing_config: Mapping[str, Any] | None = None,
) -> np.ndarray:
    """Bandpass, rectify, and RMS-smooth one raw EMG channel."""
    raw_emg_one_muscle = np.asarray(raw_emg_one_muscle, dtype=float)
    processing_config = dict(processing_config or {})

    if np.all(np.isnan(raw_emg_one_muscle)):
        return np.full(raw_emg_one_muscle.shape, np.nan, dtype=float)

    fpass = np.asarray(filter_emg_config["BANDPASS_CUTOFF"], dtype=float)
    order = int(filter_emg_config["BANDPASS_ORDER"])
    b_band, a_band = butter(order, fpass, btype="bandpass", fs=emg_fs)

    emg_subtracted_mean = raw_emg_one_muscle - np.nanmean(raw_emg_one_muscle)
    emg_notched = _apply_optional_notch(emg_subtracted_mean, filter_emg_config, emg_fs)
    emg_bandpass = filtfilt(b_band, a_band, emg_notched)

    if processing_config.get("FULL_WAVE_RECTIFY", True):
        emg_processed = np.abs(emg_bandpass)
    else:
        emg_processed = emg_bandpass

    window_ms = float(processing_config.get("RMS_WINDOW_MS", 50))
    return rms_moving_window(emg_processed, emg_fs, window_ms)


def rms_moving_window(signal: np.ndarray, fs: float, window_ms: float) -> np.ndarray:
    """Return RMS-smoothed signal using a centered moving window."""
    signal = np.asarray(signal, dtype=float)
    window_samples = max(int(round(float(fs) * float(window_ms) / 1000.0)), 1)
    kernel = np.ones(window_samples, dtype=float) / window_samples
    mean_square = np.convolve(np.square(signal), kernel, mode="same")
    return np.sqrt(mean_square)


def normalize_to_trial_max(processed_channel: np.ndarray) -> np.ndarray:
    """Normalize a processed channel by its maximum finite value in the trial."""
    processed_channel = np.asarray(processed_channel, dtype=float)
    finite = processed_channel[np.isfinite(processed_channel)]
    if finite.size == 0:
        return np.full(processed_channel.shape, np.nan, dtype=float)
    max_value = float(np.nanmax(np.abs(finite)))
    if max_value == 0:
        return np.zeros(processed_channel.shape, dtype=float)
    return processed_channel / max_value


def filter_delsys(
    loaded_data: Mapping[str, np.ndarray],
    config: Mapping[str, Any],
    fs: float,
    processing_config: Mapping[str, Any] | None = None,
) -> dict[str, np.ndarray]:
    """Process each muscle channel in a loaded Delsys data record."""
    return {
        muscle_name: filter_emg_one_muscle(muscle_data, config, fs, processing_config)
        for muscle_name, muscle_data in loaded_data.items()
    }


def normalize_delsys_trial(processed_data: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Create a trial-maximum-normalized copy of processed Delsys channels."""
    return {
        muscle_name: normalize_to_trial_max(muscle_data)
        for muscle_name, muscle_data in processed_data.items()
    }