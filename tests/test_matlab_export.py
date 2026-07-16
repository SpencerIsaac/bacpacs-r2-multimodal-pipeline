import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


_HELPER_PATH = Path(__file__).resolve().parents[1] / "analysis_scripts" / "export_scidb_table_for_matlab.py"
_SPEC = importlib.util.spec_from_file_location("export_scidb_table_for_matlab", _HELPER_PATH)
export_helper = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(export_helper)


def test_xsens_analysis_export_expands_trials_to_frame_rows():
    source = pd.DataFrame(
        [
            {
                "participant_number": "001",
                "visit": "BL",
                "test": "10MWT",
                "condition": "AFO",
                "speed": "FV",
                "trial": 1,
                "cycle": "None",
                "__record_id": "abc123",
                "data": {
                    "file_path": r"Y:\data\R1_001_BL_xsens_FV1_AFO.mvnx",
                    "sampling_frequency": 100,
                    "frame_index": np.array([10, 11]),
                    "time_seconds": np.array([0.0, 0.01]),
                    "metadata": {
                        "loader": "mvnx_xml",
                        "subject_label": "R1001",
                        "frame_rate": 100,
                    },
                    "processed_kinematics": {
                        "position_Pelvis_x": np.array([1.0, 2.0]),
                        "orientation_Pelvis_q0": np.array([0.5, 0.6]),
                    },
                },
            }
        ]
    )

    exported = export_helper._expand_timeseries_rows(source)

    assert list(exported["participant_number"]) == ["001", "001"]
    assert list(exported["trial_uid"]) == ["001_BL_10MWT_AFO_FV_1", "001_BL_10MWT_AFO_FV_1"]
    assert list(exported["sample_index"]) == [0, 1]
    assert list(exported["frame_index"]) == [10, 11]
    assert list(exported["time_seconds"]) == [0.0, 0.01]
    assert list(exported["position_Pelvis_x"]) == [1.0, 2.0]
    assert "data" not in exported.columns
    assert "source_record_id" in exported.columns
    assert "source_file_name" in exported.columns

def test_delsys_analysis_export_expands_emg_samples_with_normalized_copy():
    source = pd.DataFrame(
        [
            {
                "participant_number": "001",
                "visit": "BL",
                "test": "10MWT",
                "condition": "AFO",
                "speed": "FV",
                "trial": 1,
                "cycle": "None",
                "__record_id": "delsys123",
                "data": {
                    "file_path": r"Y:\data\R1_001_BL_delsys_FV1_AFO.mat",
                    "sampling_frequency": 2000,
                    "processed_emg": {"LTA": np.array([0.2, 0.4])},
                    "normalized_emg": {"LTA": np.array([0.5, 1.0])},
                },
            }
        ]
    )

    exported = export_helper._expand_timeseries_rows(source)

    assert list(exported["sample_index"]) == [0, 1]
    assert list(exported["time_seconds"]) == [0.0, 0.0005]
    assert list(exported["processed_LTA"]) == [0.2, 0.4]
    assert list(exported["normalized_LTA"]) == [0.5, 1.0]
    assert list(exported["source_file_name"]) == ["R1_001_BL_delsys_FV1_AFO.mat"] * 2


def test_gaitrite_analysis_export_flattens_dataframe_payload_rows():
    source = pd.DataFrame(
        [
            {
                "participant_number": "001",
                "visit": "BL",
                "test": "10MWT",
                "condition": "AFO",
                "speed": "SSV",
                "trial": 2,
                "cycle": "None",
                "__record_id": "gr123",
                "data": pd.DataFrame(
                    [
                        {
                            "GaitRiteRow": "01",
                            "StartFoot": "L",
                            "StepLengths_GR": 0.7,
                            "All_StepLengths_GR": [0.7, 0.8],
                        },
                        {
                            "GaitRiteRow": "02",
                            "StartFoot": "R",
                            "StepLengths_GR": 0.8,
                            "All_StepLengths_GR": [0.7, 0.8],
                        },
                    ]
                ),
            }
        ]
    )

    exported = export_helper._expand_timeseries_rows(source)

    assert list(exported["analysis_row_index"]) == [0, 1]
    assert list(exported["GaitRiteRow"]) == ["01", "02"]
    assert list(exported["StartFoot"]) == ["L", "R"]
    assert list(exported["StepLengths_GR"]) == [0.7, 0.8]
    assert exported.loc[0, "All_StepLengths_GR"] == "[0.7, 0.8]"
    assert list(exported["trial_uid"]) == ["001_BL_10MWT_AFO_SSV_2"] * 2

def test_table_resolution_uses_exact_table_name_without_study_prefix_fallback():
    assert export_helper._resolve_table_class("R1", "R1DelsysProcessed").__name__ == "R1DelsysProcessed"

    try:
        export_helper._resolve_table_class("R1", "DelsysProcessed")
    except KeyError:
        pass
    else:
        raise AssertionError("R1 DelsysProcessed should not auto-resolve to R1DelsysProcessed")
