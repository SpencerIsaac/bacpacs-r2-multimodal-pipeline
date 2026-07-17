import numpy as np
import pytest

from Modality_Pipelines.common import downstream_analysis as da
from Modality_Pipelines.common.table_registry import get_table_class


def test_analysis_table_names_are_exact_per_study():
    assert get_table_class("R1", "R1TrialAnalysis").__name__ == "R1TrialAnalysis"
    assert get_table_class("R2", "TrialAnalysis").__name__ == "TrialAnalysis"
    with pytest.raises(KeyError):
        get_table_class("R1", "TrialAnalysis")
    with pytest.raises(KeyError):
        get_table_class("R2", "R2TrialAnalysis")


def test_resample_to_points_preserves_linear_shape():
    result = da._resample_to_points(np.array([0.0, 10.0]), 5)

    assert np.allclose(result, [0.0, 2.5, 5.0, 7.5, 10.0])


def test_slice_and_resample_signals_uses_seconds_and_sampling_frequency():
    signals = {"LTA": np.arange(10, dtype=float)}

    result = da._slice_and_resample_signals(signals, start_seconds=0.2, end_seconds=0.6, fs=10)

    assert set(result) == {"LTA"}
    assert len(result["LTA"]) == da.NUM_POINTS
    assert np.isclose(result["LTA"][0], 2.0)
    assert np.isclose(result["LTA"][-1], 5.0)


def test_merge_side_signals_keeps_current_ipsilateral_and_next_contralateral():
    current = {"delsys_time_normalized": {"LTA": [1], "RTA": [99]}}
    next_cycle = {"delsys_time_normalized": {"LTA": [88], "RTA": [2]}}

    result = da._merge_side_signals(current, next_cycle, "delsys_time_normalized", "L", "R")

    assert result == {"LTA": [1], "RTA": [2]}


def test_build_cycles_hard_fails_without_trial_analysis(tmp_path):
    with pytest.raises(da.AnalysisPreconditionError, match="TrialAnalysis rows are required"):
        da.build_cycle_unmatched(study="R2", database_path=tmp_path / "empty.duckdb")


def test_issue_severity_defaults_cover_required_issue_types():
    assert da.ISSUE_SEVERITY == {
        "missing_modality": "error",
        "mismatched_trial": "error",
        "missing_gait_events": "error",
        "slice_failure": "error",
        "missing_visit_summary": "error",
        "missing_or_zero_visit_max": "error",
        "non_alternating_cycles": "warning",
        "export_failure": "error",
    }

def test_storage_payload_serializes_nested_values_and_decodes_them():
    stored = da._storage_payload({"scalar": "ok", "nested": {"LTA": np.array([1.0, 2.0])}})

    assert stored["scalar"] == "ok"
    assert isinstance(stored["nested"], str)
    assert da._payload_value(stored, "nested") == {"LTA": [1.0, 2.0]}


def test_has_normalized_cycles_reads_json_storage_payloads():
    row = {"data": da._storage_payload({"delsys_normalized_time_normalized": {"LTA": [0.1]}})}

    assert da._has_normalized_cycles(__import__("pandas").DataFrame([row]))


def test_normalize_cycles_hard_fails_without_visit_summary(tmp_path):
    with pytest.raises(da.AnalysisPreconditionError, match="CycleUnmatched rows are required"):
        da.normalize_cycles_to_visit(study="R2", database_path=tmp_path / "empty.duckdb")


def test_export_hard_fails_without_analysis_tables(tmp_path):
    with pytest.raises(da.AnalysisPreconditionError, match="No derived analysis tables exist"):
        da.export_analysis_tables(study="R2", database_path=tmp_path / "empty.duckdb", output_dir=tmp_path)



def test_export_filename_includes_study_prefix():
    assert da._export_filename("20260716", "R1", "bacpacs_trial.csv") == "20260716_r1_bacpacs_trial.csv"
    assert da._export_filename("20260716", "R2", "bacpacs_visit.csv") == "20260716_r2_bacpacs_visit.csv"

def test_trial_export_is_manifest_not_full_signal_payload():
    df = __import__("pandas").DataFrame([
        {
            "participant_number": "001",
            "visit": "BL",
            "test": "10MWT",
            "condition": "AFO",
            "speed": "FV",
            "trial": "1",
            "cycle": None,
            "__record_id": "trial-record",
            "data": {
                "trial_uid": "001_BL_10MWT_AFO_FV_1",
                "source_record_ids": {
                    "xsens": "x1",
                    "delsys": "d1",
                    "gaitrite_loaded": "g1",
                    "gaitrite_cycle": ["c1", "c2"],
                },
                "xsens": {"processed_kinematics": {"hip": list(range(200))}},
                "delsys": {"processed_emg": {"LTA": list(range(200))}},
                "gaitrite_loaded": {"rows": [1, 2]},
                "gaitrite_cycles": [{"cycle": 1}, {"cycle": 2}],
                "created_at": "2026-07-16T12:00:00",
            },
        }
    ])

    exported = da._analysis_export_frame(df, table_key="trial")

    assert "xsens" not in exported.columns
    assert "delsys" not in exported.columns
    assert "gaitrite_loaded" not in exported.columns
    assert "gaitrite_cycles" not in exported.columns
    assert exported.loc[0, "gaitrite_cycle_count"] == 2
    assert exported.loc[0, "xsens_source_record_id"] == "x1"

def test_cycle_matched_export_omits_duplicate_source_cycle_blobs():
    df = __import__("pandas").DataFrame([
        {
            "participant_number": "001",
            "visit": "BL",
            "test": "10MWT",
            "condition": "noAFO",
            "speed": "FV",
            "trial": "1",
            "cycle": "1",
            "__record_id": "matched-record",
            "data": {
                "matched_cycle_index": 1,
                "ipsilateral_side": "R",
                "contralateral_side": "L",
                "left_cycle_source_id": "left-id",
                "right_cycle_source_id": "right-id",
                "current_cycle": {"delsys_time_normalized": {"RTA": list(range(101))}},
                "next_cycle": {"delsys_time_normalized": {"LTA": list(range(101))}},
                "delsys_time_normalized": {"LTA": [0.1], "RTA": [0.2]},
                "delsys_normalized_time_normalized": {"LTA": [0.01], "RTA": [0.02]},
                "xsens_time_normalized": {"LKnee": [1.0], "RKnee": [2.0]},
                "created_at": "2026-07-16T12:00:00",
            },
        }
    ])

    exported = da._analysis_export_frame(df, table_key="cycle_matched")

    assert "current_cycle_delsys_time_normalized" not in exported.columns
    assert "next_cycle_delsys_time_normalized" not in exported.columns
    assert "delsys_time_normalized_LTA" in exported.columns
    assert "delsys_normalized_time_normalized_RTA" in exported.columns
    assert exported.loc[0, "left_cycle_source_id"] == "left-id"
