"""Lightweight study/stage metadata for CLI startup.

This module intentionally avoids importing SciDB table classes. It is safe for
fast commands such as ``bacpacs --help``, ``bacpacs studies``, and
``bacpacs status``.
"""

from __future__ import annotations

from typing import Any

SUPPORTED_STUDIES = ("R1", "R2")
SUPPORTED_MODALITIES = ("afo", "cosmed", "delsys", "gaitrite", "xsens")

RAW_FILE_TABLE_NAMES = {
    "R1": {
        "gaitrite": "R1GAITRiteRawFile",
        "xsens": "R1XsensRawFile",
        "delsys": "R1DelsysRawFile",
        "cosmed": "R1CosmedRawFile",
        "afo": "R1AfoRawFile",
    },
    "R2": {
        "gaitrite": "GAITRiteRawFile",
        "xsens": "XsensRawFile",
        "delsys": "DelsysRawFile",
        "cosmed": "CosmedRawFile",
        "afo": "AfoRawFile",
    },
}

PROCESSED_TABLE_NAMES = {
    "R1": {
        "gaitrite": ["R1GAITRiteLoaded", "R1GAITRiteCycle"],
        "xsens": ["R1XsensProcessed"],
        "delsys": ["R1DelsysProcessed"],
        "cosmed": ["R1CosmedProcessed"],
        "afo": ["R1AfoProcessed"],
    },
    "R2": {
        "gaitrite": ["GAITRiteLoaded", "GAITRiteCycle"],
        "xsens": ["XsensProcessed"],
        "delsys": ["DelsysProcessed"],
        "cosmed": ["CosmedProcessed"],
        "afo": ["AfoProcessed"],
    },
}


def normalize_study(study: str) -> str:
    study_key = study.upper()
    if study_key not in SUPPORTED_STUDIES:
        supported = ", ".join(SUPPORTED_STUDIES)
        raise ValueError(f"Unsupported study {study!r}. Currently supported studies: {supported}")
    return study_key


def get_supported_studies() -> list[str]:
    return list(SUPPORTED_STUDIES)


def get_supported_modalities(study: str) -> list[str]:
    study_key = normalize_study(study)
    return sorted(RAW_FILE_TABLE_NAMES[study_key])


def get_stage_registry(study: str) -> dict[str, dict[str, Any]]:
    study_key = normalize_study(study)
    return {
        modality: {
            "raw_file": RAW_FILE_TABLE_NAMES[study_key][modality],
            "processed": list(PROCESSED_TABLE_NAMES[study_key][modality]),
        }
        for modality in get_supported_modalities(study_key)
    }
