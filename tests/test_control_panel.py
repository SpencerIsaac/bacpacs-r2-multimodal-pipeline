from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from Modality_Pipelines.control_panel.db_service import (
    build_processing_ledger,
    classify_ledger_row,
    get_ledger_stage_map,
)
from Modality_Pipelines.control_panel.pipeline_api import run_modality_processing


SCHEMA_SQL = """
create table _schema(
    schema_id integer,
    schema_level varchar,
    participant_number varchar,
    visit varchar,
    test varchar,
    condition varchar,
    speed varchar,
    trial varchar,
    cycle varchar
)
"""

RECORD_SQL = """
create table _record(
    record_id varchar,
    created_at varchar,
    type varchar,
    schema_id integer,
    content_hash varchar,
    schema_version integer,
    excluded boolean
)
"""


@pytest.fixture
def ledger_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "ledger.duckdb"
    with duckdb.connect(str(db_path)) as con:
        con.execute(SCHEMA_SQL)
        con.execute(RECORD_SQL)
    return db_path


def insert_schema(con, schema_id: int, participant: str = "001") -> None:
    con.execute(
        "insert into _schema values (?, 'participant_number', ?, 'BL', '10MWT', 'noAFO', 'SSV', '1', NULL)",
        [schema_id, participant],
    )


def insert_record(con, record_id: str, record_type: str, schema_id: int) -> None:
    con.execute(
        "insert into _record values (?, 'now', ?, ?, NULL, 1, false)",
        [record_id, record_type, schema_id],
    )


def test_empty_database_returns_stable_empty_ledger(ledger_db: Path):
    ledger = build_processing_ledger(ledger_db)

    assert ledger.empty
    assert {"participant", "raw_delsys", "processed_delsys"}.issubset(ledger.columns)


def test_ledger_counts_and_attention_sorting(ledger_db: Path):
    with duckdb.connect(str(ledger_db)) as con:
        insert_schema(con, 1, "000")
        insert_schema(con, 2, "001")
        insert_record(con, "raw0", "DelsysRawFile", 1)
        insert_record(con, "raw1", "DelsysRawFile", 2)
        insert_record(con, "proc1", "DelsysProcessed", 2)

    ledger = build_processing_ledger(ledger_db, study="R2")

    assert list(ledger["participant"]) == ["R2_000", "R2_001"]
    assert ledger.iloc[0]["raw_delsys"] == 1
    assert ledger.iloc[0]["processed_delsys"] == 0
    assert ledger.iloc[0]["ledger_status"] == "attention"
    assert ledger.iloc[1]["ledger_status"] == "complete"


def test_gaitrite_loaded_without_cycle_is_attention():
    status = classify_ledger_row(
        {
            "raw_gaitrite": 1,
            "processed_gaitrite_loaded": 1,
            "processed_gaitrite_cycle": 0,
            "raw_xsens": 0,
            "raw_delsys": 0,
            "raw_cosmed": 0,
            "raw_afo": 0,
        }
    )

    assert status.label == "attention"
    assert "cycle has not run" in status.reason


def test_stage_map_loads_from_config():
    stage_map = get_ledger_stage_map(study="R2")

    assert stage_map[0]["key"] == "gaitrite"
    assert stage_map[0]["stages"][-1]["table"] == "GAITRiteCycle"
    assert stage_map[1]["stages"][-1]["column"] == "processed_xsens"


def test_r1_stage_map_uses_r1_table_namespace():
    stage_map = get_ledger_stage_map(study="R1")

    assert stage_map[0]["stages"][0]["table"] == "R1GAITRiteRawFile"
    assert stage_map[0]["stages"][-1]["table"] == "R1GAITRiteCycle"
    assert stage_map[2]["stages"][0]["table"] == "R1DelsysRawFile"


def test_new_analysis_stage_can_be_added_by_stage_map(ledger_db: Path):
    stage_map = [
        {
            "key": "xsens",
            "label": "Xsens",
            "stages": [
                {"key": "raw", "label": "RawFile", "table": "XsensRawFile", "column": "raw_xsens", "role": "raw"},
                {"key": "processed", "label": "Processed", "table": "XsensProcessed", "column": "processed_xsens"},
                {
                    "key": "events",
                    "label": "Gait events",
                    "table": "XsensGaitEvents",
                    "column": "analysis_xsens_gait_events",
                    "role": "analysis",
                },
            ],
        }
    ]
    with duckdb.connect(str(ledger_db)) as con:
        insert_schema(con, 1, "000")
        insert_record(con, "raw", "XsensRawFile", 1)
        insert_record(con, "processed", "XsensProcessed", 1)

    ledger = build_processing_ledger(ledger_db, stage_map=stage_map, study="R2")

    assert "analysis_xsens_gait_events" in ledger.columns
    assert ledger.iloc[0]["analysis_xsens_gait_events"] == 0
    assert ledger.iloc[0]["ledger_status"] == "attention"
    assert "gait events has not run" in ledger.iloc[0]["ledger_reason"]


def test_unknown_modality_runner_raises_clear_error():
    with pytest.raises(KeyError, match="Unknown or unsupported modality"):
        run_modality_processing("afo")


def test_stage_map_display_flattens_stage_objects_for_status_table():
    from Modality_Pipelines.control_panel.app import _stage_map_display

    display = _stage_map_display(
        [
            {
                "key": "delsys",
                "label": "Delsys",
                "stages": [
                    {"label": "RawFile", "table": "R1DelsysRawFile"},
                    {"label": "Processed", "table": "R1DelsysProcessed"},
                ],
            }
        ]
    )

    assert list(display.columns) == ["key", "label", "stage flow", "tables"]
    assert display.iloc[0]["stage flow"] == "RawFile -> Processed"
    assert display.iloc[0]["tables"] == "R1DelsysRawFile, R1DelsysProcessed"


def test_control_panel_nav_icons_are_valid_streamlit_material_icons():
    from streamlit.string_util import validate_icon_or_emoji

    from Modality_Pipelines.control_panel.app import NAV_ICONS

    assert all(validate_icon_or_emoji(icon) == icon for icon in NAV_ICONS.values())


def test_apply_study_selection_updates_selected_study_and_clears_study_state():
    import streamlit as st

    from Modality_Pipelines.control_panel.app import apply_study_selection

    original = dict(st.session_state)
    st.session_state.clear()
    try:
        st.session_state["selected_study"] = "R2"
        st.session_state["study_segment"] = "R2"
        st.session_state["manifest"] = object()
        st.session_state["registration_result"] = {"registered": 1}
        st.session_state["cache_warm_key"] = "R2:0"

        assert apply_study_selection("R1") is True
        assert st.session_state["selected_study"] == "R1"
        assert st.session_state["study_segment"] == "R2"
        assert "manifest" not in st.session_state
        assert "registration_result" not in st.session_state
        assert st.session_state["cache_warm_key"] is None
        assert apply_study_selection("R1") is False
    finally:
        st.session_state.clear()
        st.session_state.update(original)


def test_study_segment_callback_updates_selected_study_before_render():
    import streamlit as st

    from Modality_Pipelines.control_panel.app import on_study_segment_change

    original = dict(st.session_state)
    st.session_state.clear()
    try:
        st.session_state["selected_study"] = "R2"
        st.session_state["study_segment"] = "R1"
        st.session_state["workflow_result"] = {"old": "state"}
        st.session_state["cache_warm_key"] = "R2:0"

        on_study_segment_change()

        assert st.session_state["selected_study"] == "R1"
        assert "workflow_result" not in st.session_state
        assert st.session_state["cache_warm_key"] is None
    finally:
        st.session_state.clear()
        st.session_state.update(original)
def test_render_stat_row_uses_native_metrics(monkeypatch):
    from Modality_Pipelines.control_panel import app

    class FakeColumn:
        def __init__(self, streamlit):
            self.streamlit = streamlit

        def __enter__(self):
            return self.streamlit

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeStreamlit:
        def __init__(self):
            self.metrics = []
            self.captions = []
            self.markdown_calls = []

        def columns(self, count):
            return [FakeColumn(self) for _ in range(count)]

        def metric(self, label, value):
            self.metrics.append((label, value))

        def caption(self, value):
            self.captions.append(value)

        def markdown(self, *args, **kwargs):
            self.markdown_calls.append((args, kwargs))

    fake_st = FakeStreamlit()
    monkeypatch.setattr(app, "st", fake_st)

    app._render_stat_row([("Valid", 3, "default"), ("Review", 2, "attention")])

    assert fake_st.metrics == [("Valid", 3), ("Review", 2)]
    assert fake_st.captions == ["Needs attention"]
    assert fake_st.markdown_calls == []

def test_arrow_safe_dataframe_coerces_mixed_object_columns():
    import pandas as pd

    from Modality_Pipelines.control_panel.app import _arrow_safe_dataframe

    raw = pd.DataFrame(
        {
            "field": ["registered", "skipped", "details"],
            "value": [12, "review", {"bad_file": "R1_001_BL_xsens_SSV0_noAFO.mvnx"}],
            "count": [1, 2, 3],
        }
    )

    display = _arrow_safe_dataframe(raw)

    assert display["value"].tolist() == ["12", "review", "1 field(s)"]
    assert display["field"].tolist() == ["registered", "skipped", "details"]
    assert display["count"].tolist() == [1, 2, 3]


def test_lineage_export_filename_includes_date():
    from datetime import date

    from Modality_Pipelines.control_panel.app import _lineage_export_filename

    assert _lineage_export_filename(date(2026, 7, 15)) == "2026-07-15_bacpacs_lineage.xlsx"



def test_lineage_export_bytes_round_trip_to_xlsx():
    from io import BytesIO

    import pandas as pd

    from Modality_Pipelines.control_panel.app import _lineage_export_bytes

    lineage = pd.DataFrame(
        {
            "record_id": ["abc123"],
            "type": ["R1XsensProcessed"],
            "value": [{"file": "R1_001_BL_xsens_SSV1_noAFO.mvnx"}],
        }
    )

    exported = _lineage_export_bytes(lineage)
    workbook = pd.read_excel(BytesIO(exported), sheet_name="lineage")

    assert workbook.to_dict(orient="records") == [
        {
            "record_id": "abc123",
            "type": "R1XsensProcessed",
            "value": "1 field(s)",
        }
    ]
