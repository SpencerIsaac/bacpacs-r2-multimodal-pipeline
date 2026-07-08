"""
Xsens processing methods for single-file Excel and MVNX kinematic records.

@author shensley01
@version 0.3.0
@last_updated 2026-07-07
@change_log
    - 2026-07-07 v0.3.0: Added MATLAB-compatible Excel loader for the Joint Angles XZY sheet.
    - 2026-07-07 v0.2.0: Added MVNX XML loader and raw-file processing entry point.
    - 2026-07-02 v0.1.0: Added loaded-data filtering scaffold for Xsens processing.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

from Modality_Pipelines.Xsens_Pipeline.xsens_filtering import filter_xsens

XSENS_CONFIG_PATH = Path(__file__).with_name("xsens_config.json")
MVNX_NAMESPACE = {"mvnx": "http://www.xsens.com/mvn/mvnx"}
VECTOR_FIELDS = {
    "orientation": 4,
    "position": 3,
    "velocity": 3,
    "acceleration": 3,
    "angularVelocity": 3,
    "angularAcceleration": 3,
    "jointAngle": 3,
    "jointAngleXZY": 3,
    "jointAngleErgo": 3,
    "jointAngleErgoXZY": 3,
    "centerOfMass": 9,
    "footContacts": 1,
    "sensorFreeAcceleration": 3,
    "sensorMagneticField": 3,
    "sensorOrientation": 4,
}


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


def load_xsens_file(
    xsens_file: str | Path,
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Load one Xsens export using the supported single-file loader for its format."""
    path = Path(xsens_file)
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return load_xsens_excel_file(path, config)
    if suffix == ".mvnx":
        return load_xsens_mvnx_file(path)
    raise ValueError(f"Unsupported Xsens file extension {path.suffix!r}.")


def load_xsens_excel_file(
    xsens_file: str | Path,
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Load MATLAB-style Xsens Excel joint-angle exports.

    This mirrors loadXSENSOneFile.m: read the configured sheet, find configured
    column names, remove rows where the last requested column is NaN, and return
    one numeric array per configured output field.
    """
    path = Path(xsens_file)
    config = dict(config or load_xsens_config())
    column_names = dict(config.get("COLUMN_NAMES", {}))
    if not column_names:
        raise KeyError("Xsens config must define COLUMN_NAMES for Excel loading.")

    sheet_name = config.get("EXCEL_SHEET_NAME", "Joint Angles XZY")
    raw = pd.read_excel(path, sheet_name=sheet_name, dtype=object)
    header_map = {_normalize_header(column): column for column in raw.columns}

    indices = {}
    for output_name, source_name in column_names.items():
        normalized_source = _normalize_header(source_name)
        if normalized_source not in header_map:
            raise KeyError(
                f"Xsens file {path.name!r} sheet {sheet_name!r} is missing column {source_name!r}."
            )
        indices[output_name] = header_map[normalized_source]

    reference_column = indices[next(reversed(indices))]
    numeric_reference = pd.to_numeric(raw[reference_column], errors="coerce")
    valid_rows = numeric_reference.notna()

    data = {
        output_name: pd.to_numeric(raw.loc[valid_rows, source_column], errors="coerce").to_numpy(dtype=float)
        for output_name, source_column in indices.items()
    }

    return {
        "file_path": str(path),
        "sampling_frequency": config.get("XSENS_SAMPLING_FREQUENCY"),
        "data": data,
        "metadata": {
            "file_path": str(path),
            "loader": "excel_joint_angles_xzy",
            "sheet_name": sheet_name,
            "column_names": column_names,
            "row_count": int(valid_rows.sum()),
        },
    }


def load_xsens_mvnx_file(mvnx_file: str | Path) -> dict[str, Any]:
    """Load normal-frame numeric time series from an Xsens MVNX XML export."""
    path = Path(mvnx_file)
    root = ET.parse(path).getroot()
    subject = root.find("mvnx:subject", MVNX_NAMESPACE)
    if subject is None:
        raise ValueError(f"Xsens MVNX file {path.name!r} is missing a subject element.")

    frame_rate = _optional_float(subject.attrib.get("frameRate"))
    segment_labels = _labels(subject, "segments", "segment")
    sensor_labels = _labels(subject, "sensors", "sensor")
    joint_labels = _labels(subject, "joints", "joint")
    frames = subject.find("mvnx:frames", MVNX_NAMESPACE)
    if frames is None:
        raise ValueError(f"Xsens MVNX file {path.name!r} is missing a frames element.")

    normal_frames = [
        frame
        for frame in frames.findall("mvnx:frame", MVNX_NAMESPACE)
        if frame.attrib.get("type") == "normal"
    ]
    if not normal_frames:
        raise ValueError(f"Xsens MVNX file {path.name!r} has no normal data frames.")

    frame_index = np.asarray(
        [_optional_int(frame.attrib.get("index")) for frame in normal_frames],
        dtype=float,
    )
    time_ms = np.asarray(
        [_optional_float(frame.attrib.get("time")) for frame in normal_frames],
        dtype=float,
    )
    data: dict[str, np.ndarray] = {
        "frame_index": frame_index,
        "time_seconds": time_ms / 1000.0,
    }

    metadata = {
        "file_path": str(path),
        "loader": "mvnx_xml",
        "mvnx_version": root.attrib.get("version"),
        "mvn_version": _child_attrib(root, "mvn", "version"),
        "mvn_build": _child_attrib(root, "mvn", "build"),
        "subject_label": subject.attrib.get("label"),
        "frame_rate": frame_rate,
        "segment_labels": segment_labels,
        "sensor_labels": sensor_labels,
        "joint_labels": joint_labels,
        "normal_frame_count": len(normal_frames),
    }

    for field_name, components_per_item in VECTOR_FIELDS.items():
        rows = []
        for frame in normal_frames:
            child = frame.find(f"mvnx:{field_name}", MVNX_NAMESPACE)
            rows.append(_parse_float_vector(child.text if child is not None else None))
        data.update(_expand_field(field_name, rows, components_per_item, metadata))

    return {
        "file_path": str(path),
        "sampling_frequency": frame_rate,
        "data": data,
        "metadata": metadata,
    }


def process_xsens_raw_file(raw_file_record: Mapping[str, Any] | str | Path) -> dict[str, Any]:
    """Process one registered Xsens raw-file record or direct file path."""
    config = load_xsens_config()
    file_path = _file_path_from_record(raw_file_record)
    loaded = load_xsens_file(file_path, config)
    sampling_frequency = loaded["sampling_frequency"] or config.get(
        "XSENS_SAMPLING_FREQUENCY",
        config["FILTER"]["SAMPLING_FREQUENCY"],
    )
    filterable_data = {
        key: value
        for key, value in loaded["data"].items()
        if key not in {"frame_index", "time_seconds"} and _can_filter(value)
    }
    processed = process_loaded_xsens(
        filterable_data,
        {**config, "XSENS_SAMPLING_FREQUENCY": sampling_frequency},
    )

    return {
        "file_path": loaded["file_path"],
        "sampling_frequency": sampling_frequency,
        "time_seconds": loaded["data"].get("time_seconds"),
        "frame_index": loaded["data"].get("frame_index"),
        "processed_kinematics": processed,
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
        return Path(str(raw_file_record["file_path"]))
    if "path" in raw_file_record:
        return Path(str(raw_file_record["path"]))
    raise KeyError("Xsens raw_file_record must contain a file_path field.")


def _normalize_header(value: Any) -> str:
    return " ".join(str(value).strip().lower().split())


def _labels(subject: ET.Element, container_name: str, item_name: str) -> list[str]:
    container = subject.find(f"mvnx:{container_name}", MVNX_NAMESPACE)
    if container is None:
        return []
    return [
        str(item.attrib.get("label", "")).strip()
        for item in container.findall(f"mvnx:{item_name}", MVNX_NAMESPACE)
    ]


def _child_attrib(root: ET.Element, child_name: str, attrib_name: str) -> str | None:
    child = root.find(f"mvnx:{child_name}", MVNX_NAMESPACE)
    return child.attrib.get(attrib_name) if child is not None else None


def _parse_float_vector(text: str | None) -> list[float]:
    if text is None or not text.strip():
        return []
    return [float(value) for value in text.split()]


def _expand_field(
    field_name: str,
    rows: list[list[float]],
    components_per_item: int,
    metadata: Mapping[str, Any],
) -> dict[str, np.ndarray]:
    max_width = max((len(row) for row in rows), default=0)
    if max_width == 0:
        return {}
    arr = np.full((len(rows), max_width), np.nan, dtype=float)
    for row_index, row in enumerate(rows):
        arr[row_index, : len(row)] = row

    labels = _field_labels(field_name, max_width, components_per_item, metadata)
    return {label: arr[:, index] for index, label in enumerate(labels)}


def _field_labels(
    field_name: str,
    width: int,
    components_per_item: int,
    metadata: Mapping[str, Any],
) -> list[str]:
    if field_name in {"position", "velocity", "acceleration", "angularVelocity", "angularAcceleration"}:
        item_labels = list(metadata.get("segment_labels", []))
    elif field_name in {"sensorFreeAcceleration", "sensorMagneticField", "sensorOrientation"}:
        item_labels = list(metadata.get("sensor_labels", []))
    elif field_name in {"jointAngle", "jointAngleXZY", "jointAngleErgo", "jointAngleErgoXZY"}:
        item_labels = list(metadata.get("joint_labels", []))
    elif field_name == "orientation":
        item_labels = list(metadata.get("segment_labels", []))
    elif field_name == "centerOfMass":
        item_labels = ["centerOfMass"] * (width // components_per_item)
    elif field_name == "footContacts":
        item_labels = [f"footContact{index + 1:02d}" for index in range(width)]
    else:
        item_labels = []

    component_names = _component_names(field_name, components_per_item)
    labels = []
    for index in range(width):
        item_index = index // components_per_item
        component_index = index % components_per_item
        item = item_labels[item_index] if item_index < len(item_labels) else f"{item_index + 1:02d}"
        component = component_names[component_index] if component_index < len(component_names) else str(component_index + 1)
        labels.append(f"{field_name}_{_safe_name(item)}_{component}")
    return labels


def _component_names(field_name: str, components_per_item: int) -> list[str]:
    if components_per_item == 4:
        return ["q0", "q1", "q2", "q3"]
    if field_name == "centerOfMass":
        return ["x", "y", "z", "vx", "vy", "vz", "ax", "ay", "az"]
    if components_per_item == 3:
        return ["x", "y", "z"]
    return ["value"]


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value.strip()).strip("_")


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _can_filter(value: np.ndarray) -> bool:
    return value.ndim == 1 and value.size > 12 and not np.all(np.isnan(value))
