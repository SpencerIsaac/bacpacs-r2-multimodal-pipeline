"""
Delsys processing methods for loaded EMG records.
Set up to process one trial/test file at a time, with optional rectification and low-pass filtering.
one level above the filtering methods in delsys_filtering.py, which are called by this module.

@author shensley01
@version 0.2.0
@last_updated 2026-07-02
@change_log
    - 2026-07-02 v0.2.0: Updated processing scaffold to use MATLAB-style Delsys filter config.
    - 2026-07-02 v0.1.0: Added loaded-data filtering scaffold for Delsys processing.

File under construction: The raw-file loader still needs to be implemented once the Delsys export format is finalized. This function is the intended SciStack processing target: raw-file record in, processed Delsys artifact out.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from Modality_Pipelines.Delsys_Pipeline.delsys_filtering import filter_delsys

DELSYS_CONFIG_PATH = Path(__file__).with_name("delsys_config.json")


def load_delsys_config(config_path: str | Path = DELSYS_CONFIG_PATH) -> dict[str, Any]:
    """Load Delsys modality-specific processing config."""
    with Path(config_path).open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def process_loaded_delsys(
    loaded_data: Mapping[str, np.ndarray],
    config: Mapping[str, Any] | None = None,
) -> dict[str, np.ndarray]:
    """Filter all loaded Delsys muscle channels for one trial/test file."""
    config = dict(config or load_delsys_config())
    filter_config = config["FILTER"]
    sampling_frequency = config.get("EMG_SAMPLING_FREQUENCY", filter_config["SAMPLING_FREQUENCY"])
    return filter_delsys(loaded_data, filter_config, sampling_frequency)


def process_delsys_raw_file(raw_file_record: Mapping[str, Any]) -> dict[str, Any]:
    """Process one registered Delsys raw-file record.
    @todo: The raw-file loader still needs to be implemented once the Delsys export
    The raw-file loader still needs to be implemented once the Delsys export
    format is finalized. This function is the intended SciStack processing
    target: raw-file record in, processed Delsys artifact out.
    """
    raise NotImplementedError(
        "Delsys raw-file loading is not implemented yet. Add the file reader, "
        "then call process_loaded_delsys() on the loaded muscle-channel data."
    )
