from Modality_Pipelines.common import scistack_runner as sr


def test_ensure_legacy_tmp_dir_creates_expected_directory(tmp_path, monkeypatch):
    legacy_tmp = tmp_path / "legacy_tmp"

    def fake_path(value):
        assert value == "/tmp"
        return legacy_tmp

    monkeypatch.setattr(sr, "Path", fake_path)

    sr._ensure_legacy_tmp_dir()

    assert legacy_tmp.is_dir()