import numpy as np
from scipy.io import savemat

from Modality_Pipelines.Delsys_Pipeline.delsys_filtering import (
    filter_delsys,
    normalize_delsys_trial,
    rms_moving_window,
)
from Modality_Pipelines.Delsys_Pipeline.process_delsys import load_delsys_config, load_delsys_mat_file


def test_delsys_config_matches_current_emg_processing_settings():
    config = load_delsys_config()

    assert config["FILTER"]["BANDPASS_ORDER"] == 4
    assert config["FILTER"]["BANDPASS_CUTOFF"] == [20, 450]
    assert config["PROCESSING"]["FULL_WAVE_RECTIFY"] is True
    assert config["PROCESSING"]["RMS_WINDOW_MS"] == 50
    assert config["PROCESSING"]["NORMALIZATION"]["METHOD"] == "trial_max"


def test_rms_moving_window_preserves_length_and_is_nonnegative():
    signal = np.array([-1.0, 1.0, -1.0, 1.0, 0.0])

    smoothed = rms_moving_window(signal, fs=1000, window_ms=2)

    assert smoothed.shape == signal.shape
    assert np.all(smoothed >= 0)


def test_filter_delsys_returns_rms_envelope_and_normalized_copy():
    fs = 2000
    seconds = np.arange(0, 1, 1 / fs)
    raw = np.sin(2 * np.pi * 100 * seconds) + 0.1 * np.sin(2 * np.pi * 10 * seconds)
    config = {
        "BANDPASS_ORDER": 4,
        "BANDPASS_CUTOFF": [20, 450],
        "NOTCH": {"ENABLED": False},
    }
    processing = {"FULL_WAVE_RECTIFY": True, "RMS_WINDOW_MS": 50}

    processed = filter_delsys({"TA": raw}, config, fs, processing)
    normalized = normalize_delsys_trial(processed)

    assert set(processed) == {"TA"}
    assert processed["TA"].shape == raw.shape
    assert np.all(processed["TA"] >= 0)
    assert np.isclose(np.nanmax(normalized["TA"]), 1.0)

def test_delsys_loader_skips_invalid_non_emg_trigger_span(tmp_path):
    mat_path = tmp_path / "R1_001_BL_delsys_FV1_AFO.mat"
    savemat(
        mat_path,
        {
            "data": np.array([1.0, 2.0, 3.0, 4.0]),
            "datastart": np.array([1, -1]),
            "dataend": np.array([4, -1]),
            "titles": np.array(["TA", "Stim Tr"], dtype=object),
            "samplerate": np.array([2000, 2000]),
        },
    )

    loaded = load_delsys_mat_file(mat_path)

    assert set(loaded["emg_channels"]) == {"TA"}
    assert "Stim Tr" not in loaded["auxiliary_channels"]
    assert loaded["metadata"]["skipped_channel_spans"] == {
        "Stim Tr": {"datastart": -1, "dataend": -1}
    }


