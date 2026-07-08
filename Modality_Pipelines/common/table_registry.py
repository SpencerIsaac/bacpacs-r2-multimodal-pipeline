"""Study-aware SciDB table routing."""

from __future__ import annotations

from Modality_Pipelines.common import r1_scidb_tables as r1_tables
from Modality_Pipelines.common import r2_scidb_tables as r2_tables


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
        raise ValueError(f"Unsupported study {study!r}. Currently supported studies: R1, R2")
    return study_key


def get_raw_file_table(study: str, modality: str):
    """Return the RawFile table class for a study/modality pair."""
    study_key = _normalize_study(study)
    try:
        return RAW_FILE_TABLES[study_key][modality]
    except KeyError as exc:
        raise KeyError(f"Unknown modality {modality!r}") from exc


def get_processed_tables(study: str, modality: str) -> list[type]:
    """Return processed output table classes for a study/modality pair."""
    study_key = _normalize_study(study)
    try:
        return list(PROCESSED_TABLES[study_key][modality])
    except KeyError as exc:
        raise KeyError(f"Unknown modality {modality!r}") from exc
