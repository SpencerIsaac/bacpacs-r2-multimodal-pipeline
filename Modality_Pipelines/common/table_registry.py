"""Study-aware SciDB table routing."""

from __future__ import annotations

from typing import Any

from Modality_Pipelines.common import r1_scidb_tables as r1_tables
from Modality_Pipelines.common import r2_scidb_tables as r2_tables
from Modality_Pipelines.common.lightweight_registry import (
    get_stage_registry as get_stage_table_names,
    get_supported_modalities as get_supported_modalities_light,
    get_supported_studies as get_supported_studies_light,
)


STUDY_TABLE_MODULES = {
    "R1": r1_tables,
    "R2": r2_tables,
}

RAW_FILE_TABLES = {
    "R1": {
        "gaitrite": r1_tables.R1GAITRiteRawFile,
        "xsens": r1_tables.R1XsensRawFile,
        "delsys": r1_tables.R1DelsysRawFile,
        "cosmed": r1_tables.R1CosmedRawFile,
        "afo": r1_tables.R1AfoRawFile,
    },
    "R2": {
        "gaitrite": r2_tables.GAITRiteRawFile,
        "xsens": r2_tables.XsensRawFile,
        "delsys": r2_tables.DelsysRawFile,
        "cosmed": r2_tables.CosmedRawFile,
        "afo": r2_tables.AfoRawFile,
    },
}

PROCESSED_TABLES = {
    "R1": {
        "gaitrite": [r1_tables.R1GAITRiteLoaded, r1_tables.R1GAITRiteCycle],
        "xsens": [r1_tables.R1XsensProcessed],
        "delsys": [r1_tables.R1DelsysProcessed],
        "cosmed": [r1_tables.R1CosmedProcessed],
        "afo": [r1_tables.R1AfoProcessed],
    },
    "R2": {
        "gaitrite": [r2_tables.GAITRiteLoaded, r2_tables.GAITRiteCycle],
        "xsens": [r2_tables.XsensProcessed],
        "delsys": [r2_tables.DelsysProcessed],
        "cosmed": [r2_tables.CosmedProcessed],
        "afo": [r2_tables.AfoProcessed],
    },
}


def _normalize_study(study: str) -> str:
    study_key = study.upper()
    if study_key not in RAW_FILE_TABLES:
        supported = ", ".join(get_supported_studies())
        raise ValueError(f"Unsupported study {study!r}. Currently supported studies: {supported}")
    return study_key


def _normalize_modality(modality: str) -> str:
    return modality.lower()


def get_supported_studies() -> list[str]:
    """Return study namespaces known to the table registry."""
    return get_supported_studies_light()


def get_supported_modalities(study: str) -> list[str]:
    """Return modalities with registered RawFile tables for a study."""
    return get_supported_modalities_light(study)


def get_study_table_module(study: str) -> Any:
    """Return the Python module containing study-specific SciDB table classes."""
    study_key = _normalize_study(study)
    return STUDY_TABLE_MODULES[study_key]


def get_table_class(study: str, table_name: str):
    """Resolve a study-specific SciDB table class by class name.

    This is intentionally dynamic so a future analysis table can be added to
    r1_scidb_tables.py/r2_scidb_tables.py and discovered by registry metadata
    without editing CLI code.
    """
    module = get_study_table_module(study)
    try:
        return getattr(module, table_name)
    except AttributeError as exc:
        raise KeyError(f"Table {table_name!r} is not defined for study {_normalize_study(study)}") from exc


def get_raw_file_table(study: str, modality: str):
    """Return the RawFile table class for a study/modality pair."""
    study_key = _normalize_study(study)
    modality_key = _normalize_modality(modality)
    try:
        return RAW_FILE_TABLES[study_key][modality_key]
    except KeyError as exc:
        raise KeyError(f"Unknown modality {modality!r} for study {study_key}") from exc


def get_processed_tables(study: str, modality: str) -> list[type]:
    """Return processed output table classes for a study/modality pair."""
    study_key = _normalize_study(study)
    modality_key = _normalize_modality(modality)
    try:
        return list(PROCESSED_TABLES[study_key][modality_key])
    except KeyError as exc:
        raise KeyError(f"Unknown modality {modality!r} for study {study_key}") from exc


def get_primary_processed_table(study: str, modality: str):
    """Return the default processed input table for downstream analyses."""
    processed_tables = get_processed_tables(study, modality)
    if not processed_tables:
        raise KeyError(f"No processed tables registered for {study!r}/{modality!r}")
    return processed_tables[0]


def get_stage_registry(study: str) -> dict[str, dict[str, Any]]:
    """Return raw and processed table names grouped by modality for status/CLI views."""
    return get_stage_table_names(study)
