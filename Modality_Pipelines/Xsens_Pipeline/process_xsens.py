"""
Xsens processing methods for loaded kinematic records.

@author shensley01
@version 0.1.0
@last_updated 2026-07-02
@change_log
    - 2026-07-02 v0.1.0: Added loaded-data filtering scaffold for Xsens processing.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from Modality_Pipelines.Xsens_Pipeline.xsens_filtering import filter_xsens

XSENS_CONFIG_PATH = Path(__file__).with_name("xsens_config.json")


def load_xsens_config(config_path: str | Path = XSENS_CONFIG_PATH) -> dict[str, Any]:
    """Load Xsens modality-specific processing config."""
    with Path(config_path).open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def process_loaded_xsens(
    loaded_data: Mapping[str, np.ndarray],
    config: Mapping[str, Any] | None = None,
) -> dict[str, np.ndarray]:
    """Filter all loaded Xsens columns for one trial/test file."""
    config = dict(config or load_xsens_config())
    filter_config = config["FILTER"]
    sampling_frequency = config.get("XSENS_SAMPLING_FREQUENCY", filter_config["SAMPLING_FREQUENCY"])
    return filter_xsens(loaded_data, filter_config, sampling_frequency)


def process_xsens_raw_file(raw_file_record: Mapping[str, Any]) -> dict[str, Any]:
    """Process one registered Xsens raw-file record.

    The raw-file loader still needs to be implemented once the Xsens export
    format is finalized. This function is the intended SciStack processing
    target: raw-file record in, processed Xsens artifact out.
    """
    raise NotImplementedError(
        "Xsens raw-file loading is not implemented yet. Add the file reader, "
        "then call process_loaded_xsens() on the loaded kinematic data."
    )
