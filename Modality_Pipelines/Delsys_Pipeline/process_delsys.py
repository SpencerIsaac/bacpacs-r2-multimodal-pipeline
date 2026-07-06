"""
Delsys processing methods for ADInstruments MATLAB exports.
Set up to process one trial/test file at a time, with optional rectification and low-pass filtering.
One level above the filtering methods in delsys_filtering.py, which are called by this module.

@author shensley01
@version 0.3.0
@last_updated 2026-07-06
@change_log
    - 2026-07-06 v0.3.0: Added ADInstruments MAT loader and RawFile -> processed artifact path.
    - 2026-07-02 v0.2.0: Updated processing scaffold to use MATLAB-style Delsys filter config.
    - 2026-07-02 v0.1.0: Added loaded-data filtering scaffold for Delsys processing.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import loadmat

from Modality_Pipelines.Delsys_Pipeline.delsys_filtering import filter_delsys

DELSYS_CONFIG_PATH = Path(__file__).with_name("delsys_config.json")
NON_EMG_CHANNEL_KEYWORDS = ("trig", "trigger", "sync", "stim", "event")


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


def load_delsys_mat_file(mat_file: str | Path) -> dict[str, Any]:
    """Load an ADInstruments-style Delsys MATLAB export.

    LabChart exports Delsys files as one flat ``data`` vector with one-based,
    inclusive ``datastart``/``dataend`` indices for each channel.
    """
    mat_path = Path(mat_file)
    mat_data = loadmat(mat_path, squeeze_me=True, struct_as_record=False)

    required_keys = ("data", "datastart", "dataend", "titles", "samplerate")
    missing_keys = [key for key in required_keys if key not in mat_data]
    if missing_keys:
        raise KeyError(f"Delsys MAT file is missing required keys: {missing_keys}")

    flat_data = np.asarray(mat_data["data"]).squeeze()
    starts = np.asarray(mat_data["datastart"], dtype=int).ravel()
    ends = np.asarray(mat_data["dataend"], dtype=int).ravel()
    titles = [_clean_label(title) for title in np.asarray(mat_data["titles"]).ravel()]
    samplerates = np.asarray(mat_data["samplerate"], dtype=float).ravel()

    if not (len(starts) == len(ends) == len(titles) == len(samplerates)):
        raise ValueError("Delsys MAT channel metadata lengths do not match.")

    unit_by_channel = _channel_units(mat_data, len(titles))
    channels = {}
    for title, start, end in zip(titles, starts, ends):
        if start < 1 or end < start or end > flat_data.size:
            raise ValueError(f"Invalid one-based data span for channel {title!r}: {start}-{end}")
        channels[title] = np.asarray(flat_data[start - 1 : end], dtype=float)

    emg_channel_names = [
        title
        for title in titles
        if _is_emg_channel(title, unit_by_channel.get(title, ""))
    ]
    auxiliary_channel_names = [title for title in titles if title not in emg_channel_names]

    return {
        "file_path": str(mat_path),
        "channels": channels,
        "emg_channels": {name: channels[name] for name in emg_channel_names},
        "auxiliary_channels": {name: channels[name] for name in auxiliary_channel_names},
        "metadata": {
            "channel_names": titles,
            "emg_channel_names": emg_channel_names,
            "auxiliary_channel_names": auxiliary_channel_names,
            "samplerate_by_channel": {
                title: float(rate) for title, rate in zip(titles, samplerates)
            },
            "unit_by_channel": unit_by_channel,
            "tickrate": _optional_float(mat_data.get("tickrate")),
            "blocktimes": _optional_float(mat_data.get("blocktimes")),
            "firstsampleoffset": _as_float_list(mat_data.get("firstsampleoffset")),
            "sample_count_by_channel": {
                title: int(ends[index] - starts[index] + 1)
                for index, title in enumerate(titles)
            },
        },
    }


def process_delsys_raw_file(raw_file_record: Mapping[str, Any] | str | Path) -> dict[str, Any]:
    """Process one registered Delsys raw-file record or direct MAT file path."""
    config = load_delsys_config()
    file_path = _file_path_from_record(raw_file_record)
    loaded = load_delsys_mat_file(file_path)
    sampling_frequency = _emg_sampling_frequency(loaded["metadata"], config)
    processed_emg = filter_delsys(loaded["emg_channels"], config["FILTER"], sampling_frequency)

    return {
        "file_path": loaded["file_path"],
        "sampling_frequency": sampling_frequency,
        "processed_emg": processed_emg,
        "auxiliary_channels": loaded["auxiliary_channels"],
        "metadata": {
            **loaded["metadata"],
            "filter": config["FILTER"],
            "pipeline_metadata": config.get("pipeline_metadata", {}),
        },
    }


def _file_path_from_record(raw_file_record: Mapping[str, Any] | str | Path) -> Path:
    if isinstance(raw_file_record, (str, Path)):
        return Path(raw_file_record)
    if "file_path" in raw_file_record:
        return _path_from_field(raw_file_record["file_path"])
    if "path" in raw_file_record:
        return _path_from_field(raw_file_record["path"])
    raise KeyError("Delsys raw_file_record must contain a file_path field.")


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


def _clean_label(label: Any) -> str:
    return str(label).strip()


def _channel_units(mat_data: Mapping[str, Any], channel_count: int) -> dict[str, str]:
    titles = [_clean_label(title) for title in np.asarray(mat_data["titles"]).ravel()]
    unittext = [_clean_label(unit) for unit in np.asarray(mat_data.get("unittext", [])).ravel()]
    unittextmap = np.asarray(mat_data.get("unittextmap", []), dtype=int).ravel()

    if len(unittext) == 0 or len(unittextmap) != channel_count:
        return {title: "" for title in titles}

    units = {}
    for title, unit_index in zip(titles, unittextmap):
        if 1 <= unit_index <= len(unittext):
            units[title] = unittext[unit_index - 1]
        else:
            units[title] = ""
    return units


def _is_emg_channel(channel_name: str, unit: str) -> bool:
    channel_name_lower = channel_name.lower()
    if any(keyword in channel_name_lower for keyword in NON_EMG_CHANNEL_KEYWORDS):
        return False
    return unit.lower() in {"mv", ""} or unit.lower().endswith("mv")


def _emg_sampling_frequency(metadata: Mapping[str, Any], config: Mapping[str, Any]) -> float:
    configured_fs = float(
        config.get("EMG_SAMPLING_FREQUENCY", config["FILTER"]["SAMPLING_FREQUENCY"])
    )
    rates = metadata.get("samplerate_by_channel", {})
    emg_names = metadata.get("emg_channel_names", [])
    emg_rates = {float(rates[name]) for name in emg_names if name in rates}
    if len(emg_rates) > 1:
        raise ValueError(f"Delsys EMG channels have mismatched sample rates: {sorted(emg_rates)}")
    if len(emg_rates) == 1:
        return emg_rates.pop()
    return configured_fs


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    array = np.asarray(value, dtype=float).ravel()
    if array.size == 0:
        return None
    return float(array[0])


def _as_float_list(value: Any) -> list[float]:
    if value is None:
        return []
    return [float(item) for item in np.asarray(value, dtype=float).ravel()]
