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
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.json"


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

VISITS = CONFIG["visits"]
MODALITIES = CONFIG["modalities"]
CONDITIONS = CONFIG["conditions"]
TASKS = CONFIG["tasks"]
SPEED_OUTCOME_CODES = CONFIG["speed_outcome_codes"]


def format_participant_number(participant: int | str) -> str:
    """Return the three-digit participant number used in SOP file names.

    Examples: ``1``, ``"001"``, and ``"R2_001"`` all return ``"001"``.
    """
    if isinstance(participant, str):
        participant = participant.strip().upper().removeprefix("R2_")

    return PARTICIPANT_NUMBER_FORMAT.format(int(participant))


def format_participant(participant: int | str) -> str:
    """Return the participant folder name used under ``SUBJECT_DATA_ROOT``.

    Example: ``format_participant("001")`` returns ``"R2_001"``.
    """
    return PARTICIPANT_FOLDER_TEMPLATE.format(
        participant_number=format_participant_number(participant)
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
) -> str:
    """Build a raw-file stem from the four SOP file-name fields.

    ``visit`` and ``modality`` should be canonical config keys, such as
    ``baseline`` and ``gaitrite``. The returned file stem does not include an
    extension.
    """
    return FILE_NAME_PATTERN.format(
        participant_number=format_participant_number(participant),
        visit=VISITS[visit]["file_code"],
        modality=MODALITIES[modality]["file_code"],
        outcome=outcome,
    )


def parse_file_name(file_name: str | Path) -> dict[str, str]:
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

    if len(parts) != 5 or parts[0] != "R2":
        raise ValueError(
            f"File name {Path(file_name).name!r} does not match "
            f"R2_{{participant_number}}_{{visit}}_{{modality}}_{{outcome}}"
        )

    return {
        "participant_number": format_participant_number(parts[1]),
        "visit": parts[2],
        "modality": parts[3],
        "outcome": parts[4],
    }


def participant_folder(participant: int | str) -> Path:
    """Return the participant folder path under ``SUBJECT_DATA_ROOT``."""
    return BASEPATH / format_participant(participant)


def modality_folder(participant: int | str, visit: str, modality: str) -> Path:
    """Return the expected raw-data folder for one participant/visit/modality.

    Parameters use canonical config keys, such as ``visit="baseline"`` and
    ``modality="gaitrite"``.
    """
    return participant_folder(participant) / VISITS[visit]["folder"] / MODALITIES[modality]["folder"]


def configure_scistack_database(database_path: str | Path | None = None):
    """Configure the SciStack/scidb DuckDB database for the R2 pipeline."""
    from scidb import configure_database

    return configure_database(database_path or DATABASE_PATH, list(SCHEMA_KEYS))




