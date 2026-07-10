from pathlib import Path

from Modality_Pipelines.common.common_config import format_participant, parse_file_name
from Modality_Pipelines.common.manifest import build_raw_file_manifest, validate_raw_file
from Modality_Pipelines.common.study_config import load_study_config
from Modality_Pipelines.common.table_registry import get_processed_tables, get_raw_file_table


def test_r1_and_r2_study_configs_load():
    r1 = load_study_config("R1")
    r2 = load_study_config("R2")

    assert r1.study == "R1"
    assert r1.participant_prefix == "R1"
    assert r1.participant_glob == "R1_*"
    assert r1.visits["baseline"]["folder"] == "1. Baseline"
    assert r1.visits["mid_test"]["folder"] == "2. Mid-Test"
    assert r1.visits["mid_test"]["file_code"] == "MP"
    assert r1.modalities["afo"]["folder"] == "AFO Data"
    assert r1.database_path == r2.database_path

    assert r2.study == "R2"
    assert r2.participant_prefix == "R2"
    assert r2.participant_glob == "R2_*"
    assert r2.visits["baseline"]["folder"] == "2. Baseline"


def test_r1_and_r2_filename_and_participant_formatting():
    r1 = load_study_config("R1")
    r2 = load_study_config("R2")

    assert format_participant("001", study_config=r1) == "R1_001"
    assert format_participant("001", study_config=r2) == "R2_001"
    assert parse_file_name("R1_001_BL_delsys_SSV1_noAFO.mat", study_config=r1)["participant_number"] == "001"
    assert parse_file_name("R2_001_BL_delsys_SSV1_noAFO.mat", study_config=r2)["participant_number"] == "001"


def test_r1_and_r2_table_registry_routes_to_separate_tables():
    assert get_raw_file_table("R1", "delsys").__name__ == "R1DelsysRawFile"
    assert get_raw_file_table("R2", "delsys").__name__ == "DelsysRawFile"
    assert [table.__name__ for table in get_processed_tables("R1", "gaitrite")] == [
        "R1GAITRiteLoaded",
        "R1GAITRiteCycle",
    ]
    assert [table.__name__ for table in get_processed_tables("R2", "gaitrite")] == [
        "GAITRiteLoaded",
        "GAITRiteCycle",
    ]


def test_validate_raw_file_catches_visit_folder_mismatch(tmp_path: Path):
    root = tmp_path / "Subject Data"
    folder = root / "R2_001" / "3. Pre-Test" / "Delsys"
    folder.mkdir(parents=True)
    raw_file = folder / "R2_001_BL_delsys_SSV1_noAFO.mat"
    raw_file.write_text("mock")

    record = validate_raw_file(raw_file, root, study="R2")

    assert record.status == "review"
    assert "visit folder mismatch" in record.issues


def test_validate_raw_file_accepts_correct_r1_and_r2_layouts(tmp_path: Path):
    r1_root = tmp_path / "R1 Subject Data"
    r2_root = tmp_path / "R2 Subject Data"

    r1_folder = r1_root / "R1_001" / "1. Baseline" / "Delsys"
    r2_folder = r2_root / "R2_001" / "2. Baseline" / "Delsys"
    r1_folder.mkdir(parents=True)
    r2_folder.mkdir(parents=True)
    r1_mid_folder = r1_root / "R1_001" / "2. Mid-Test" / "Delsys"
    r1_mid_folder.mkdir(parents=True)
    r1_file = r1_folder / "R1_001_BL_delsys_SSV1_noAFO.mat"
    r1_mid_file = r1_mid_folder / "R1_001_MP_delsys_SSV2_noAFO.mat"
    r2_file = r2_folder / "R2_001_BL_delsys_SSV1_noAFO.mat"
    r1_file.write_text("mock")
    r1_mid_file.write_text("mock")
    r2_file.write_text("mock")

    r1_record = validate_raw_file(r1_file, r1_root, study="R1")
    r1_mid_record = validate_raw_file(r1_mid_file, r1_root, study="R1")
    r2_record = validate_raw_file(r2_file, r2_root, study="R2")

    assert r1_record.status == "valid"
    assert r1_record.participant_number == "001"
    assert r1_record.visit == "BL"
    assert r1_record.modality == "delsys"
    assert r1_record.test == "10MWT"
    assert r1_record.speed == "SSV"
    assert r1_record.trial == "1"

    assert r1_mid_record.status == "valid"
    assert r1_mid_record.visit == "MP"
    assert r1_mid_record.trial == "2"

    assert r2_record.status == "valid"
    assert r2_record.participant_number == "001"
    assert r2_record.visit == "BL"
    assert r2_record.modality == "delsys"


def test_build_manifest_keeps_r1_and_r2_roots_separate(tmp_path: Path):
    r1_root = tmp_path / "R1 Subject Data"
    r2_root = tmp_path / "R2 Subject Data"
    (r1_root / "R1_001" / "1. Baseline" / "Delsys").mkdir(parents=True)
    (r2_root / "R2_001" / "2. Baseline" / "Delsys").mkdir(parents=True)
    (r1_root / "R1_001" / "1. Baseline" / "Delsys" / "R1_001_BL_delsys_SSV1_noAFO.mat").write_text("mock")
    (r2_root / "R2_001" / "2. Baseline" / "Delsys" / "R2_001_BL_delsys_SSV1_noAFO.mat").write_text("mock")

    r1_manifest = build_raw_file_manifest(["delsys"], r1_root, study="R1")
    r2_manifest = build_raw_file_manifest(["delsys"], r2_root, study="R2")

    assert len(r1_manifest) == 1
    assert len(r2_manifest) == 1
    assert r1_manifest.iloc[0]["file_name"].startswith("R1_")
    assert r2_manifest.iloc[0]["file_name"].startswith("R2_")
