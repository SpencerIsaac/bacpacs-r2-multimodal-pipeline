"""
Xsens filtering methods ported from MATLAB.

@author shensley01
@version 0.1.0
@last_updated 2026-07-02
@change_log
    - 2026-07-02 v0.1.0: Added direct Python port of filterXSENS MATLAB logic.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
from scipy.signal import butter, filtfilt


def filter_xsens(
    loaded_data: Mapping[str, np.ndarray],
    filter_config: Mapping[str, Any],
    fs: float,
) -> dict[str, np.ndarray]:
    """Low-pass filter each loaded Xsens data column."""
    fc = filter_config["LOWPASS_CUTOFF"]
    n = filter_config["LOWPASS_ORDER"]
    b, a = butter(n, fc / (fs / 2), btype="low")

    filtered_data = {}
    for column_name, column_data in loaded_data.items():
        filtered_data[column_name] = filtfilt(b, a, np.asarray(column_data, dtype=float))

    return filtered_data
