"""
Common configuration helpers for the R2 Spinal Stim pipeline.

Created on June 30th 2026
Last updated on July 1st 2026
@author shensley01
@version 0.5.0
@last_updated 2026-07-02
@change_log
    - 2026-07-02 v0.5.0: Split SOP file-name keys from SciDB analysis schema keys.
    - 2026-07-01 v0.4.0: Replaced vague basepath/database_name config references with explicit project_root, subject_data_root, pipeline_root, and database_path.
    - 2026-07-01 v0.3.1: Updated config loader to read JSON with utf-8-sig for Windows-written files.
    - 2026-07-01 v0.3.0: Renamed from common_globals.py to common_config.py
      and moved shared SOP vocabulary into root config.json.
    - 2026-07-01 v0.2.1: Expanded method documentation for SOP naming,
      folder navigation, and SciStack/scidb.for_each setup.
    - 2026-07-01 v0.2.0: Removed backward-compatible aliases and aligned shared
      vocabulary with SOP fields: participant_number, visit, modality, outcome.
    - 2026-07-01 v0.1.0: Updated file naming globals to match SOP convention.

This module is the Python wrapper around the shared pipeline config. The JSON
file stores SOP-backed project vocabulary. This module loads that vocabulary and
provides small helpers for path building, file-name parsing, and SciStack/scidb
configuration.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.json"
_CONFIGURE_DATABASE_LOCK = threading.RLock()


def load_config(config_path: str | Path | None = None) -> dict:
    """Load the shared R2 pipeline JSON configuration.

    Parameters
    ----------
    config_path:
        Optional config path. If omitted, the root ``Modality_Pipelines``
        ``config.json`` file is loaded.

    Returns
    -------
    dict
        Parsed JSON configuration.
    """
    path = Path(config_path) if config_path is not None else CONFIG_PATH
    with path.open("r", encoding="utf-8-sig") as config_file:
        return json.load(config_file)


CONFIG = load_config()

PROJECT_ROOT = Path(CONFIG["project"]["project_root"])
SUBJECT_DATA_ROOT = Path(CONFIG["project"]["subject_data_root"])
BASEPATH = SUBJECT_DATA_ROOT
PIPELINE_ROOT = Path(CONFIG["project"]["pipeline_root"])
DATABASE_PATH = Path(CONFIG["project"]["database_path"])

FILE_NAME_PATTERN = CONFIG["file_naming"]["pattern"]
FILE_NAME_KEYS = tuple(CONFIG["file_naming"]["file_name_keys"])
SCHEMA_KEYS = tuple(CONFIG["file_naming"]["schema_keys"])

PARTICIPANT_NUMBER_FORMAT = CONFIG["file_naming"]["participant_number_format"]
PARTICIPANT_FOLDER_TEMPLATE = CONFIG["file_naming"]["participant_folder_template"]
PARTICIPANT_PREFIX = PARTICIPANT_FOLDER_TEMPLATE.split("_", maxsplit=1)[0]

VISITS = CONFIG["visits"]
MODALITIES = CONFIG["modalities"]
CONDITIONS = CONFIG["conditions"]
TASKS = CONFIG["tasks"]
SPEED_OUTCOME_CODES = CONFIG["speed_outcome_codes"]


def _study_value(study_config, field: str, default):
    """Return a study config value when provided, otherwise the R2 default."""
    return getattr(study_config, field, default) if study_config is not None else default


def format_participant_number(participant: int | str, study_config=None) -> str:
    """Return the three-digit participant number used in SOP file names.

    Examples: ``1``, ``"001"``, and ``"R2_001"`` all return ``"001"``.
    """
    participant_prefix = _study_value(study_config, "participant_prefix", PARTICIPANT_PREFIX)
    participant_number_format = _study_value(
        study_config,
        "participant_number_format",
        PARTICIPANT_NUMBER_FORMAT,
    )

    if isinstance(participant, str):
        participant = participant.strip().upper().removeprefix(f"{participant_prefix.upper()}_")

    return participant_number_format.format(int(participant))


def format_participant(participant: int | str, study_config=None) -> str:
    """Return the participant folder name used under ``SUBJECT_DATA_ROOT``.

    Example: ``format_participant("001")`` returns ``"R2_001"``.
    """
    participant_folder_template = _study_value(
        study_config,
        "participant_folder_template",
        PARTICIPANT_FOLDER_TEMPLATE,
    )
    return participant_folder_template.format(
        participant_number=format_participant_number(participant, study_config)
    )


def format_outcome(task: str, condition: str, speed: str = "none", trial: int | str = "01") -> str:
    """Return the SOP outcome token for a single walking-test file.

    For 10MWT files, this returns values such as ``SSV1_noAFO`` or ``FV3_AFO``.
    For 6MWT files, this returns values such as ``6MWT_noAFO``.
    """
    condition_code = CONDITIONS[condition]["file_code"]

    if task == "6mwt":
        return f"{TASKS[task]['outcome_code']}_{condition_code}"

    trial_code = SPEED_OUTCOME_CODES[speed].format(int(trial))
    return f"{trial_code}_{condition_code}"


def build_file_name(
    participant: int | str,
    visit: str,
    modality: str,
    outcome: str,
    study_config=None,
) -> str:
    """Build a raw-file stem from the four SOP file-name fields.

    ``visit`` and ``modality`` should be canonical config keys, such as
    ``baseline`` and ``gaitrite``. The returned file stem does not include an
    extension.
    """
    file_name_pattern = _study_value(study_config, "file_name_pattern", FILE_NAME_PATTERN)
    visits = _study_value(study_config, "visits", VISITS)
    modalities = _study_value(study_config, "modalities", MODALITIES)

    return file_name_pattern.format(
        participant_number=format_participant_number(participant, study_config),
        visit=visits[visit]["file_code"],
        modality=modalities[modality]["file_code"],
        outcome=outcome,
    )


def parse_file_name(file_name: str | Path, study_config=None) -> dict[str, str]:
    """Parse an SOP file name into SOP file-name metadata.

    Parameters
    ----------
    file_name:
        File name or path. The extension is ignored.

    Returns
    -------
    dict[str, str]
        Dictionary with ``participant_number``, ``visit``, ``modality``, and
        ``outcome``.

    Raises
    ------
    ValueError
        If the file stem does not match ``FILE_NAME_PATTERN``.
    """
    stem = Path(file_name).stem
    parts = stem.split("_", maxsplit=4)
    participant_prefix = _study_value(study_config, "participant_prefix", PARTICIPANT_PREFIX)
    expected_pattern = _study_value(study_config, "file_name_pattern", FILE_NAME_PATTERN)

    if len(parts) != 5 or parts[0] != participant_prefix:
        raise ValueError(
            f"File name {Path(file_name).name!r} does not match "
            f"{expected_pattern}"
        )

    return {
        "participant_number": format_participant_number(parts[1], study_config),
        "visit": parts[2],
        "modality": parts[3],
        "outcome": parts[4],
    }


def participant_folder(participant: int | str, study_config=None) -> Path:
    """Return the participant folder path under ``SUBJECT_DATA_ROOT``."""
    basepath = _study_value(study_config, "subject_data_root", BASEPATH)
    return basepath / format_participant(participant, study_config)


def modality_folder(participant: int | str, visit: str, modality: str, study_config=None) -> Path:
    """Return the expected raw-data folder for one participant/visit/modality.

    Parameters use canonical config keys, such as ``visit="baseline"`` and
    ``modality="gaitrite"``.
    """
    visits = _study_value(study_config, "visits", VISITS)
    modalities = _study_value(study_config, "modalities", MODALITIES)
    return (
        participant_folder(participant, study_config)
        / visits[visit]["folder"]
        / modalities[modality]["folder"]
    )


def configure_scistack_database(database_path: str | Path | None = None, study_config=None):
    """Configure or reuse the SciStack/scidb DuckDB database.

    DuckDB permits only one writable connection to a database file per process.
    The Streamlit control panel may query SciDB before launching processing, so
    reuse the existing SciStack DatabaseManager when it already points at the
    requested study database and schema. New database initialization is guarded
    because an empty DB can trigger concurrent metadata-table creation from UI
    reruns and pipeline commands.
    """
    from scidb import configure_database, get_database

    resolved_database_path = Path(database_path or _study_value(study_config, "database_path", DATABASE_PATH))
    schema_keys = list(_study_value(study_config, "schema_keys", SCHEMA_KEYS))

    def current_matching_database():
        try:
            current_database = get_database()
        except Exception:
            return None

        if current_database is None:
            return None
        current_path = Path(getattr(current_database, "dataset_db_path", ""))
        current_schema_keys = list(getattr(current_database, "dataset_schema_keys", []))
        if current_path == resolved_database_path and current_schema_keys == schema_keys:
            if getattr(current_database, "_closed", False):
                current_database.reopen()
            return current_database
        return None

    current_database = current_matching_database()
    if current_database is not None:
        return current_database

    last_error = None
    for attempt in range(3):
        with _CONFIGURE_DATABASE_LOCK:
            current_database = current_matching_database()
            if current_database is not None:
                return current_database
            try:
                return configure_database(resolved_database_path, schema_keys)
            except Exception as exc:
                last_error = exc
                if not _looks_like_duckdb_catalog_conflict(exc):
                    raise
        time.sleep(0.25 * (attempt + 1))

    raise last_error


def _looks_like_duckdb_catalog_conflict(exc: Exception) -> bool:
    text = f"{exc.__class__.__name__}: {exc}"
    return "TransactionException" in text and "Catalog write-write conflict" in text

