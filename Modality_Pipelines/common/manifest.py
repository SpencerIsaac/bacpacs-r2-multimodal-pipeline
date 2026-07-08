"""
Raw-file manifest and registration helpers for the BACPACS pipeline.

The backend is study-aware, but modality processors remain study-agnostic.
Raw-file registration stores validated file-path records in the selected
study's modality-specific RawFile tables.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from Modality_Pipelines.common.common_config import (
    CONDITIONS,
    MODALITIES,
    SCHEMA_KEYS,
    SUBJECT_DATA_ROOT,
    VISITS,
    configure_scistack_database,
    format_participant,
    parse_file_name,
)
from Modality_Pipelines.common.study_config import StudyConfig, load_study_config
from Modality_Pipelines.common.table_registry import get_raw_file_table


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


def _resolve_study(study: str | StudyConfig = "R2") -> StudyConfig:
    if isinstance(study, StudyConfig):
        return study
    return load_study_config(study)


def _visit_by_file_code(study_config: StudyConfig) -> dict[str, str]:
    return {value["file_code"]: key for key, value in study_config.visits.items()}


def _modality_by_file_code(study_config: StudyConfig) -> dict[str, str]:
    return {value["file_code"]: key for key, value in study_config.modalities.items()}


def _condition_by_file_code(study_config: StudyConfig) -> dict[str, str]:
    return {value["file_code"]: value["file_code"] for value in study_config.conditions.values()}


def _as_filter_values(value):
    if isinstance(value, str):
        return [value]
    try:
        return list(value)
    except TypeError:
        return [value]


def _modality_filter_values(modality, study_config: StudyConfig):
    return [
        study_config.modalities.get(str(value), {}).get("file_code", value)
        for value in _as_filter_values(modality)
    ]


def _apply_manifest_filters(
    df: pd.DataFrame,
    *,
    participant_number=None,
    visit=None,
    modality=None,
    test=None,
    condition=None,
    speed=None,
    trial=None,
    study_config: StudyConfig,
) -> pd.DataFrame:
    if df.empty:
        return df

    filters = {
        "participant_number": participant_number,
        "visit": visit,
        "test": test,
        "condition": condition,
        "speed": speed,
        "trial": trial,
    }
    if modality is not None:
        filters["modality"] = _modality_filter_values(modality, study_config)

    filtered = df
    for column, value in filters.items():
        if value is None or column not in filtered.columns:
            continue
        values = _as_filter_values(value)
        filtered = filtered[filtered[column].isin([str(item) for item in values])]
    return filtered


# ---------------------------------------------------------------------------
# SOP parsing and path helpers
# ---------------------------------------------------------------------------


def modality_path_template(modality_key: str, study: str | StudyConfig = "R2") -> str:
    """Return the relative raw-file path template for one modality."""
    study_config = _resolve_study(study)
    modality_config = study_config.modalities[modality_key]
    return (
        f"{study_config.participant_folder_template}/"
        "{visit_folder}/"
        f"{modality_config['folder']}/"
        f"{study_config.file_name_pattern}.{{extension}}"
    )


def parse_outcome(outcome: str, study: str | StudyConfig = "R2") -> dict[str, str | None]:
    """Parse the SOP outcome field into analysis schema fields."""
    study_config = _resolve_study(study)
    condition_by_file_code = _condition_by_file_code(study_config)

    if "_" not in outcome:
        raise ValueError(f"Outcome {outcome!r} does not contain a condition token")

    test_token, condition_token = outcome.rsplit("_", maxsplit=1)
    if condition_token not in condition_by_file_code:
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


def register_raw_files(
    manifest_df: pd.DataFrame | None = None,
    modality_keys: Iterable[str] | None = None,
    only_valid: bool = True,
    database_path: str | Path | None = None,
    *,
    study: str = "R2",
    root: str | Path | None = None,
    participant_number=None,
    visit=None,
    modality=None,
    test=None,
    condition=None,
    speed=None,
    trial=None,
    dry_run: bool = False,
    update_existing: bool = False,
) -> dict[str, int]:
    """Register raw-file manifest records in study-specific RawFile tables."""
    study_config = _resolve_study(study)
    configure_scistack_database(database_path, study_config=study_config)

    selected_modalities = list(modality_keys) if modality_keys is not None else None
    if modality is not None:
        selected_modalities = [modality] if isinstance(modality, str) else list(modality)

    df = manifest_df if manifest_df is not None else build_raw_file_manifest(
        selected_modalities,
        subject_data_root=root or study_config.subject_data_root,
        study=study_config,
    )
    df = _apply_manifest_filters(
        df,
        participant_number=participant_number,
        visit=visit,
        modality=modality,
        test=test,
        condition=condition,
        speed=speed,
        trial=trial,
        study_config=study_config,
    )

    counts = {"registered": 0, "skipped": 0}
    modality_by_file_code = _modality_by_file_code(study_config)

    for _, row in df.iterrows():
        if only_valid and row["status"] != "valid":
            counts["skipped"] += 1
            continue

        modality_key = modality_by_file_code.get(str(row["modality"]))
        if modality_key is None:
            counts["skipped"] += 1
            continue

        table = get_raw_file_table(study_config.study, modality_key)
        metadata = {key: (None if pd.isna(row[key]) else row[key]) for key in study_config.schema_keys}
        payload = {
            "file_path": row["file_path"],
            "file_name": row["file_name"],
            "extension": row["extension"],
        }
        if not dry_run:
            table.save(payload, **metadata)
        counts["registered"] += 1

    return counts


# ---------------------------------------------------------------------------
# Dry-run validation helpers
# ---------------------------------------------------------------------------


def iter_modality_files(
    modality_key: str,
    subject_data_root: str | Path | None = None,
    *,
    study: str | StudyConfig = "R2",
) -> Iterable[Path]:
    """Yield primary raw files from expected participant/visit/modality folders."""
    study_config = _resolve_study(study)
    root = Path(subject_data_root) if subject_data_root is not None else study_config.subject_data_root
    modality_config = study_config.modalities[modality_key]
    modality_folder_name = modality_config["folder"]
    primary_extensions = {
        extension.lower().lstrip(".")
        for extension in modality_config.get("primary_extensions", [])
    }

    for participant_dir in root.glob(study_config.participant_glob):
        if not participant_dir.is_dir():
            continue
        for visit_config in study_config.visits.values():
            folder = participant_dir / visit_config["folder"] / modality_folder_name
            if folder.exists():
                for path in folder.iterdir():
                    extension = path.suffix.lstrip(".").lower()
                    if path.is_file() and (not primary_extensions or extension in primary_extensions):
                        yield path


def validate_raw_file(
    file_path: str | Path,
    subject_data_root: str | Path | None = None,
    *,
    study: str | StudyConfig = "R2",
) -> RawFileManifestRecord:
    """Parse and validate one raw file against the SOP folder/name rules."""
    study_config = _resolve_study(study)
    root = Path(subject_data_root) if subject_data_root is not None else study_config.subject_data_root
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
        parsed.update(parse_file_name(path.name, study_config=study_config))
    except ValueError as exc:
        issues.append(f"filename: {exc}")

    if parsed["outcome"]:
        try:
            outcome_metadata.update(parse_outcome(str(parsed["outcome"]), study_config))
        except ValueError as exc:
            issues.append(f"outcome: {exc}")

    try:
        relative_parts = path.relative_to(root).parts
    except ValueError:
        relative_parts = path.parts
        issues.append("location: file is not under study subject_data_root")

    visit_by_file_code = _visit_by_file_code(study_config)
    modality_by_file_code = _modality_by_file_code(study_config)

    if len(relative_parts) < 4:
        issues.append("location: expected participant/visit/modality/file structure")
    else:
        participant_folder, visit_folder, modality_folder = relative_parts[:3]

        if parsed["participant_number"]:
            expected_participant_folder = format_participant(
                str(parsed["participant_number"]),
                study_config=study_config,
            )
            if participant_folder != expected_participant_folder:
                issues.append(
                    f"participant folder mismatch: expected {expected_participant_folder}, found {participant_folder}"
                )

        if parsed["visit"]:
            visit_key = visit_by_file_code.get(str(parsed["visit"]))
            expected_visit_folder = study_config.visits[visit_key]["folder"] if visit_key else None
            if expected_visit_folder is None:
                issues.append(f"visit code: unknown visit {parsed['visit']!r}")
            elif visit_folder != expected_visit_folder:
                issues.append(
                    f"visit folder mismatch: expected {expected_visit_folder}, found {visit_folder}"
                )

        if parsed["modality"]:
            modality_key = modality_by_file_code.get(str(parsed["modality"]))
            expected_modality_folder = study_config.modalities[modality_key]["folder"] if modality_key else None
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
    subject_data_root: str | Path | None = None,
    *,
    study: str | StudyConfig = "R2",
) -> pd.DataFrame:
    """Build a dry-run validation manifest for discovered primary raw files."""
    study_config = _resolve_study(study)
    keys = list(modality_keys) if modality_keys is not None else list(study_config.modalities)
    records = []
    seen = set()

    for modality_key in keys:
        for file_path in iter_modality_files(
            modality_key,
            subject_data_root,
            study=study_config,
        ):
            record = validate_raw_file(file_path, subject_data_root, study=study_config)
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


def validate_study_files(
    study: str = "R2",
    root: str | Path | None = None,
    participant_number=None,
    visit=None,
    modality=None,
    test=None,
    condition=None,
    speed=None,
    trial=None,
) -> pd.DataFrame:
    """Build and filter the dry-run validation manifest for one study."""
    study_config = _resolve_study(study)
    modality_keys = None
    if modality is not None:
        modality_keys = [modality] if isinstance(modality, str) else list(modality)

    df = build_raw_file_manifest(
        modality_keys,
        subject_data_root=root or study_config.subject_data_root,
        study=study_config,
    )
    return _apply_manifest_filters(
        df,
        participant_number=participant_number,
        visit=visit,
        modality=modality,
        test=test,
        condition=condition,
        speed=speed,
        trial=trial,
        study_config=study_config,
    )
