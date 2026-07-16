"""Study configuration helpers for BACPACS pipeline backends."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from Modality_Pipelines.common.common_config import load_config


@dataclass(frozen=True)
class StudyConfig:
    """Resolved study-specific configuration used by backend plumbing."""

    study: str
    project_name: str
    project_root: Path
    subject_data_root: Path
    pipeline_root: Path
    database_path: Path
    participant_prefix: str
    participant_folder_template: str
    file_name_pattern: str
    visits: Mapping[str, dict]
    modalities: Mapping[str, dict]
    conditions: Mapping[str, dict]
    tasks: Mapping[str, dict]
    speed_outcome_codes: Mapping[str, str]
    schema_keys: tuple[str, ...]
    file_name_keys: tuple[str, ...]
    participant_number_format: str

    @property
    def participant_glob(self) -> str:
        """Return the participant folder glob for this study."""
        return f"{self.participant_prefix}_*"


R1_VISITS = {
    "baseline": {"folder": "1. Baseline", "file_code": "BL"},
    "mid_test": {"folder": "2. Mid-Test", "file_code": "MP"},
    "post_test": {"folder": "3. Post-Test", "file_code": "PT"},
    "follow_up": {"folder": "4. Follow-Up", "file_code": "FU"},
}


def _study_dict(study: str, config_path: str | Path | None = None) -> dict:
    config = deepcopy(load_config(config_path))
    study_key = study.upper()

    if study_key == "R2":
        return config

    if study_key == "R1":
        config["metadata"]["project_name"] = "BACPACS R1 Smart AFO"
        config["project"]["project_root"] = r"Y:\BACPACS R1 - Smart AFO"
        config["project"]["subject_data_root"] = r"Y:\BACPACS R1 - Smart AFO\Subject Data"
        config["file_naming"]["pattern"] = "R1_{participant_number}_{visit}_{modality}_{outcome}"
        config["file_naming"]["participant_folder_template"] = "R1_{participant_number}"
        config["visits"] = R1_VISITS
        config["modalities"]["afo"]["folder"] = "AFO"
        return config

    raise ValueError(f"Unsupported study {study!r}. Currently supported studies: R1, R2")


def load_study_config(study: str = "R2", config_path: str | Path | None = None) -> StudyConfig:
    """Load a study configuration."""
    study_key = study.upper()
    config = _study_dict(study_key, config_path)
    project = config["project"]
    file_naming = config["file_naming"]
    participant_prefix = file_naming["participant_folder_template"].split("_", maxsplit=1)[0]

    return StudyConfig(
        study=study_key,
        project_name=config["metadata"]["project_name"],
        project_root=Path(project["project_root"]),
        subject_data_root=Path(project["subject_data_root"]),
        pipeline_root=Path(project["pipeline_root"]),
        database_path=Path(project["database_path"]),
        participant_prefix=participant_prefix,
        participant_folder_template=file_naming["participant_folder_template"],
        file_name_pattern=file_naming["pattern"],
        visits=config["visits"],
        modalities=config["modalities"],
        conditions=config["conditions"],
        tasks=config["tasks"],
        speed_outcome_codes=config["speed_outcome_codes"],
        schema_keys=tuple(file_naming["schema_keys"]),
        file_name_keys=tuple(file_naming["file_name_keys"]),
        participant_number_format=file_naming["participant_number_format"],
    )
