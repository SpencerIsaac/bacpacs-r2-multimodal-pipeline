"""
Raw-file manifest and registration helpers for the R2 Spinal Stim pipeline.

@author shensley01
@version 0.2.1
@last_updated 2026-07-02
@change_log
    - 2026-07-02 v0.2.1: Reordered module so dry-run validation helpers are grouped at the end.
    - 2026-07-02 v0.2.0: Added AFO raw-file registration and slimmed RawFile DB payload to path registry fields.
    - 2026-07-02 v0.1.3: Added config-driven primary raw-file extension filtering for sidecar-aware registration.
    - 2026-07-02 v0.1.2: Added database_path override to raw-file registration for isolated testing.
    - 2026-07-02 v0.1.1: Added subject_data_root override to validation for isolated testing and dry-runs.
    - 2026-07-02 v0.1.0: Replaced template-only scaffold with raw-file discovery,
      SOP validation, outcome parsing, and modality-specific SciDB registration helpers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from Modality_Pipelines.common.common_config import (
    CONDITIONS,
    DATABASE_PATH,
    FILE_NAME_PATTERN,
    MODALITIES,
    SCHEMA_KEYS,
    SUBJECT_DATA_ROOT,
    VISITS,
    configure_scistack_database,
    format_participant,
    parse_file_name,
)
from Modality_Pipelines.common.scidb_tables import (
    AfoRawFile,
    CosmedRawFile,
    DelsysRawFile,
    GAITRiteRawFile,
    XsensRawFile,
)


# ---------------------------------------------------------------------------
# Raw-file table routing
# ---------------------------------------------------------------------------
# The manifest keeps one raw-file registry table per modality. Each RawFile
# table stores the file path payload, while participant/visit/test identity is
# stored through the configured SciDB schema keys.

RAW_FILE_TABLES = {
    "gaitrite": GAITRiteRawFile,
    "xsens": XsensRawFile,
    "delsys": DelsysRawFile,
    "cosmed": CosmedRawFile,
    "afo": AfoRawFile,
}

VISIT_BY_FILE_CODE = {value["file_code"]: key for key, value in VISITS.items()}
MODALITY_BY_FILE_CODE = {value["file_code"]: key for key, value in MODALITIES.items()}
CONDITION_BY_FILE_CODE = {value["file_code"]: value["file_code"] for value in CONDITIONS.values()}


@dataclass
class RawFileManifestRecord:
    """One discovered raw-file record before or after SciDB registration."""

    file_path: str
    file_name: str
    extension: str
    participant_number: str | None
    visit: str | None
    modality: str | None
    outcome: str | None
    test: str | None
    condition: str | None
    speed: str | None
    trial: str | None
    cycle: str | None
    status: str
    issues: str

    @property
    def schema_metadata(self) -> dict:
        """Return analysis schema metadata used to address the raw-file record."""
        return {key: getattr(self, key) for key in SCHEMA_KEYS}

    @property
    def payload(self) -> dict:
        """Return path-registry payload stored in the raw-file table."""
        return {
            "file_path": self.file_path,
            "file_name": self.file_name,
            "extension": self.extension,
        }


# ---------------------------------------------------------------------------
# SOP parsing and path helpers
# ---------------------------------------------------------------------------
# These helpers turn the SOP file-name convention into the schema fields that
# SciDB uses for querying and for_each processing.


def modality_path_template(modality_key: str) -> str:
    """Return the relative raw-file path template for one modality."""
    modality_config = MODALITIES[modality_key]
    return (
        "R2_{participant_number}/"
        "{visit_folder}/"
        f"{modality_config['folder']}/"
        f"{FILE_NAME_PATTERN}.{{extension}}"
    )


def parse_outcome(outcome: str) -> dict[str, str | None]:
    """Parse the SOP outcome field into analysis schema fields.

    Examples
    --------
    ``SSV1_noAFO`` -> test=10MWT, speed=SSV, trial=1, condition=noAFO
    ``6MWT_AFO`` -> test=6MWT, speed=None, trial=None, condition=AFO
    """
    if "_" not in outcome:
        raise ValueError(f"Outcome {outcome!r} does not contain a condition token")

    test_token, condition_token = outcome.rsplit("_", maxsplit=1)
    if condition_token not in CONDITION_BY_FILE_CODE:
        raise ValueError(f"Outcome {outcome!r} has unknown condition {condition_token!r}")

    if test_token == "6MWT":
        return {
            "test": "6MWT",
            "condition": condition_token,
            "speed": None,
            "trial": None,
            "cycle": None,
        }

    for speed in ("SSV", "FV"):
        if test_token.startswith(speed):
            trial = test_token.removeprefix(speed)
            if not trial.isdigit():
                raise ValueError(f"Outcome {outcome!r} has invalid trial token {trial!r}")
            return {
                "test": "10MWT",
                "condition": condition_token,
                "speed": speed,
                "trial": str(int(trial)),
                "cycle": None,
            }

    raise ValueError(f"Outcome {outcome!r} does not match 6MWT, SSV, or FV patterns")


# ---------------------------------------------------------------------------
# SciDB registration
# ---------------------------------------------------------------------------
# Registration is the first write step. It saves valid raw files into the
# modality-specific RawFile table. The stored payload is intentionally small:
# file_path, file_name, and extension. Query identity is stored through the
# SciDB schema keys.


def register_raw_files(
    manifest_df: pd.DataFrame | None = None,
    modality_keys: Iterable[str] | None = None,
    only_valid: bool = True,
    database_path: str | Path | None = None,
) -> dict[str, int]:
    """Register raw-file manifest records in modality-specific SciDB tables.

    If ``manifest_df`` is omitted, the dry-run manifest is built first and then
    valid rows are registered. Raw data are not stored in SciDB.
    """
    configure_scistack_database(database_path or DATABASE_PATH)
    df = manifest_df if manifest_df is not None else build_raw_file_manifest(modality_keys)
    counts = {"registered": 0, "skipped": 0}

    for _, row in df.iterrows():
        if only_valid and row["status"] != "valid":
            counts["skipped"] += 1
            continue

        modality_key = MODALITY_BY_FILE_CODE.get(str(row["modality"]))
        table = RAW_FILE_TABLES.get(modality_key) if modality_key else None
        if table is None:
            counts["skipped"] += 1
            continue

        metadata = {key: (None if pd.isna(row[key]) else row[key]) for key in SCHEMA_KEYS}
        payload = {
            "file_path": row["file_path"],
            "file_name": row["file_name"],
            "extension": row["extension"],
        }
        table.save(payload, **metadata)
        counts["registered"] += 1

    return counts


# ---------------------------------------------------------------------------
# Dry-run validation helpers
# ---------------------------------------------------------------------------
# This section is intentionally at the end of the script. These functions crawl
# the filesystem, parse SOP file names, check folder/name agreement, and return
# a reviewable DataFrame. They do not write to SciDB unless the caller passes
# the resulting DataFrame into register_raw_files().


def iter_modality_files(
    modality_key: str,
    subject_data_root: str | Path = SUBJECT_DATA_ROOT,
) -> Iterable[Path]:
    """Yield primary raw files from expected participant/visit/modality folders."""
    root = Path(subject_data_root)
    modality_config = MODALITIES[modality_key]
    modality_folder_name = modality_config["folder"]
    primary_extensions = {
        extension.lower().lstrip(".")
        for extension in modality_config.get("primary_extensions", [])
    }

    for participant_dir in root.glob("R2_*"):
        if not participant_dir.is_dir():
            continue
        for visit_config in VISITS.values():
            folder = participant_dir / visit_config["folder"] / modality_folder_name
            if folder.exists():
                for path in folder.iterdir():
                    extension = path.suffix.lstrip(".").lower()
                    if path.is_file() and (not primary_extensions or extension in primary_extensions):
                        yield path


def validate_raw_file(
    file_path: str | Path,
    subject_data_root: str | Path = SUBJECT_DATA_ROOT,
) -> RawFileManifestRecord:
    """Parse and validate one raw file against the SOP folder/name rules."""
    path = Path(file_path)
    issues: list[str] = []
    parsed: dict[str, str | None] = {
        "participant_number": None,
        "visit": None,
        "modality": None,
        "outcome": None,
    }
    outcome_metadata = {
        "test": None,
        "condition": None,
        "speed": None,
        "trial": None,
        "cycle": None,
    }

    try:
        parsed.update(parse_file_name(path.name))
    except ValueError as exc:
        issues.append(f"filename: {exc}")

    if parsed["outcome"]:
        try:
            outcome_metadata.update(parse_outcome(str(parsed["outcome"])))
        except ValueError as exc:
            issues.append(f"outcome: {exc}")

    try:
        relative_parts = path.relative_to(Path(subject_data_root)).parts
    except ValueError:
        relative_parts = path.parts
        issues.append("location: file is not under SUBJECT_DATA_ROOT")

    if len(relative_parts) < 4:
        issues.append("location: expected participant/visit/modality/file structure")
    else:
        participant_folder, visit_folder, modality_folder = relative_parts[:3]

        if parsed["participant_number"]:
            expected_participant_folder = format_participant(str(parsed["participant_number"]))
            if participant_folder != expected_participant_folder:
                issues.append(
                    f"participant folder mismatch: expected {expected_participant_folder}, found {participant_folder}"
                )

        if parsed["visit"]:
            visit_key = VISIT_BY_FILE_CODE.get(str(parsed["visit"]))
            expected_visit_folder = VISITS[visit_key]["folder"] if visit_key else None
            if expected_visit_folder is None:
                issues.append(f"visit code: unknown visit {parsed['visit']!r}")
            elif visit_folder != expected_visit_folder:
                issues.append(
                    f"visit folder mismatch: expected {expected_visit_folder}, found {visit_folder}"
                )

        if parsed["modality"]:
            modality_key = MODALITY_BY_FILE_CODE.get(str(parsed["modality"]))
            expected_modality_folder = MODALITIES[modality_key]["folder"] if modality_key else None
            if expected_modality_folder is None:
                issues.append(f"modality code: unknown modality {parsed['modality']!r}")
            elif modality_folder != expected_modality_folder:
                issues.append(
                    f"modality folder mismatch: expected {expected_modality_folder}, found {modality_folder}"
                )

    status = "valid" if not issues else "review"

    return RawFileManifestRecord(
        file_path=str(path),
        file_name=path.name,
        extension=path.suffix.lstrip("."),
        participant_number=parsed["participant_number"],
        visit=parsed["visit"],
        modality=parsed["modality"],
        outcome=parsed["outcome"],
        status=status,
        issues="; ".join(issues),
        **outcome_metadata,
    )


def build_raw_file_manifest(
    modality_keys: Iterable[str] | None = None,
    subject_data_root: str | Path = SUBJECT_DATA_ROOT,
) -> pd.DataFrame:
    """Build a dry-run validation manifest for discovered primary raw files.

    This function does not write to SciDB. It only reports what exists and
    whether each primary raw file is ready for registration.
    """
    keys = list(modality_keys) if modality_keys is not None else list(MODALITIES)
    records = []
    seen = set()

    for modality_key in keys:
        for file_path in iter_modality_files(modality_key, subject_data_root):
            record = validate_raw_file(file_path, subject_data_root)
            duplicate_key = (
                record.modality,
                record.participant_number,
                record.visit,
                record.test,
                record.condition,
                record.speed,
                record.trial,
                record.cycle,
            )
            if duplicate_key in seen:
                record.status = "review"
                record.issues = "; ".join(filter(None, [record.issues, "duplicate schema identity"]))
            seen.add(duplicate_key)
            records.append(asdict(record))

    return pd.DataFrame(records)
