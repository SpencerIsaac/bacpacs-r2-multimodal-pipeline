from pathlib import Path

import pytest

from Modality_Pipelines.common.manifest import _looks_like_duplicate_record, register_raw_files, validate_study_files


def touch_raw(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("raw", encoding="utf-8")


@pytest.mark.parametrize(
    ("modality_filter", "expected_file", "expected_modality"),
    [
        ("xsens", "R2_001_BL_xsens_SSV1_noAFO.mvnx", "xsens"),
        ("GR", "R2_001_BL_GR_SSV1_noAFO.xlsx", "GR"),
    ],
)
def test_validate_filters_by_participant_visit_and_modality_aliases(
    tmp_path: Path,
    modality_filter: str,
    expected_file: str,
    expected_modality: str,
):
    touch_raw(tmp_path / "R2_001" / "2. Baseline" / "Xsens" / "R2_001_BL_xsens_SSV1_noAFO.mvnx")
    touch_raw(tmp_path / "R2_001" / "2. Baseline" / "GAITRite" / "R2_001_BL_GR_SSV1_noAFO.xlsx")
    touch_raw(tmp_path / "R2_002" / "2. Baseline" / "Xsens" / "R2_002_BL_xsens_SSV1_noAFO.mvnx")

    manifest = validate_study_files(
        study="R2",
        root=tmp_path,
        participant_number="001",
        visit="BL",
        modality=modality_filter,
    )

    assert len(manifest) == 1
    assert manifest.iloc[0]["file_name"] == expected_file
    assert manifest.iloc[0]["modality"] == expected_modality
    assert manifest.iloc[0]["status"] == "valid"


def test_register_raw_files_is_idempotent_for_schema_identity(tmp_path: Path):
    from Modality_Pipelines.common.common_config import configure_scistack_database
    from Modality_Pipelines.common.study_config import load_study_config
    from Modality_Pipelines.common.table_registry import get_raw_file_table

    touch_raw(tmp_path / "R2_001" / "2. Baseline" / "Xsens" / "R2_001_BL_xsens_SSV1_noAFO.mvnx")
    database_path = tmp_path / "pipeline.duckdb"

    filters = {
        "study": "R2",
        "root": tmp_path,
        "database_path": database_path,
        "participant_number": "001",
        "visit": "BL",
        "modality": "xsens",
    }
    first = register_raw_files(**filters)
    second = register_raw_files(**filters)

    db = configure_scistack_database(database_path, study_config=load_study_config("R2"))
    table = get_raw_file_table("R2", "xsens")
    rows = db.load_all_as_df(table, include_rid=True)

    assert first["registered"] == 1
    assert second["registered"] == 0
    assert second["skipped_existing"] == 1
    assert len(rows) == 1

def test_duplicate_record_id_exception_is_treated_as_existing_record():
    exc = Exception('Constraint Error: Duplicate key "record_id: 098b7ea55807e054" violates primary key constraint.')

    assert _looks_like_duplicate_record(exc) is True
