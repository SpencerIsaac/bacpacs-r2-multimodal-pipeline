from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import duckdb

from Modality_Pipelines.control_panel.db_service import (
    build_processing_ledger,
    classify_ledger_row,
    get_ledger_stage_map,
)
from Modality_Pipelines.control_panel.pipeline_api import run_modality_processing


class ControlPanelLedgerTests(unittest.TestCase):
    def test_empty_database_returns_stable_empty_ledger(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "empty.duckdb"
            with duckdb.connect(str(db_path)) as con:
                con.execute("create table _record(record_id varchar, created_at varchar, type varchar, schema_id integer, content_hash varchar, schema_version integer, excluded boolean)")
                con.execute("create table _schema(schema_id integer, schema_level varchar, participant_number varchar, visit varchar, test varchar, condition varchar, speed varchar, trial varchar, cycle varchar)")

            ledger = build_processing_ledger(db_path)
            self.assertTrue(ledger.empty)
            self.assertIn("participant", ledger.columns)
            self.assertIn("raw_delsys", ledger.columns)
            self.assertIn("processed_delsys", ledger.columns)

    def test_ledger_counts_and_attention_sorting(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "ledger.duckdb"
            with duckdb.connect(str(db_path)) as con:
                con.execute("create table _schema(schema_id integer, schema_level varchar, participant_number varchar, visit varchar, test varchar, condition varchar, speed varchar, trial varchar, cycle varchar)")
                con.execute("create table _record(record_id varchar, created_at varchar, type varchar, schema_id integer, content_hash varchar, schema_version integer, excluded boolean)")
                con.execute("insert into _schema values (1, 'participant_number', '000', 'BL', '10MWT', 'noAFO', 'SSV', '1', NULL)")
                con.execute("insert into _schema values (2, 'participant_number', '001', 'BL', '10MWT', 'noAFO', 'SSV', '1', NULL)")
                con.execute("insert into _record values ('raw0', 'now', 'DelsysRawFile', 1, NULL, 1, false)")
                con.execute("insert into _record values ('raw1', 'now', 'DelsysRawFile', 2, NULL, 1, false)")
                con.execute("insert into _record values ('proc1', 'now', 'DelsysProcessed', 2, NULL, 1, false)")

            ledger = build_processing_ledger(db_path, study="R2")
            self.assertEqual(list(ledger["participant"]), ["R2_000", "R2_001"])
            first = ledger.iloc[0]
            self.assertEqual(first["raw_delsys"], 1)
            self.assertEqual(first["processed_delsys"], 0)
            self.assertEqual(first["ledger_status"], "attention")
            second = ledger.iloc[1]
            self.assertEqual(second["ledger_status"], "complete")

    def test_gaitrite_loaded_without_cycle_is_attention(self):
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
        self.assertEqual(status.label, "attention")
        self.assertIn("cycle has not run", status.reason)

    def test_stage_map_loads_from_config(self):
        stage_map = get_ledger_stage_map(study="R2")
        self.assertEqual(stage_map[0]["key"], "gaitrite")
        self.assertEqual(stage_map[0]["stages"][-1]["table"], "GAITRiteCycle")
        self.assertEqual(stage_map[1]["stages"][-1]["column"], "processed_xsens")

    def test_r1_stage_map_uses_r1_table_namespace(self):
        stage_map = get_ledger_stage_map(study="R1")
        self.assertEqual(stage_map[0]["stages"][0]["table"], "R1GAITRiteRawFile")
        self.assertEqual(stage_map[0]["stages"][-1]["table"], "R1GAITRiteCycle")
        self.assertEqual(stage_map[2]["stages"][0]["table"], "R1DelsysRawFile")

    def test_new_analysis_stage_can_be_added_by_stage_map(self):
        stage_map = [
            {
                "key": "xsens",
                "label": "Xsens",
                "stages": [
                    {"key": "raw", "label": "RawFile", "table": "XsensRawFile", "column": "raw_xsens", "role": "raw"},
                    {"key": "processed", "label": "Processed", "table": "XsensProcessed", "column": "processed_xsens"},
                    {"key": "events", "label": "Gait events", "table": "XsensGaitEvents", "column": "analysis_xsens_gait_events", "role": "analysis"},
                ],
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "ledger.duckdb"
            with duckdb.connect(str(db_path)) as con:
                con.execute("create table _schema(schema_id integer, schema_level varchar, participant_number varchar, visit varchar, test varchar, condition varchar, speed varchar, trial varchar, cycle varchar)")
                con.execute("create table _record(record_id varchar, created_at varchar, type varchar, schema_id integer, content_hash varchar, schema_version integer, excluded boolean)")
                con.execute("insert into _schema values (1, 'participant_number', '000', 'BL', '10MWT', 'noAFO', 'SSV', '1', NULL)")
                con.execute("insert into _record values ('raw', 'now', 'XsensRawFile', 1, NULL, 1, false)")
                con.execute("insert into _record values ('processed', 'now', 'XsensProcessed', 1, NULL, 1, false)")

            ledger = build_processing_ledger(db_path, stage_map=stage_map, study="R2")
            self.assertIn("analysis_xsens_gait_events", ledger.columns)
            self.assertEqual(ledger.iloc[0]["analysis_xsens_gait_events"], 0)
            self.assertEqual(ledger.iloc[0]["ledger_status"], "attention")
            self.assertIn("gait events has not run", ledger.iloc[0]["ledger_reason"])

    def test_unknown_modality_runner_raises_clear_error(self):
        with self.assertRaisesRegex(KeyError, "Unknown or unsupported modality"):
            run_modality_processing("afo")


if __name__ == "__main__":
    unittest.main()


def test_control_panel_nav_icons_are_valid_streamlit_material_icons():
    from streamlit.string_util import validate_icon_or_emoji

    from Modality_Pipelines.control_panel.app import NAV_ICONS

    for icon in NAV_ICONS.values():
        assert validate_icon_or_emoji(icon) == icon


def test_apply_study_selection_updates_segment_and_clears_study_state():
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
        assert st.session_state["study_segment"] == "R1"
        assert "manifest" not in st.session_state
        assert "registration_result" not in st.session_state
        assert st.session_state["cache_warm_key"] is None
        assert apply_study_selection("R1") is False
    finally:
        st.session_state.clear()
        st.session_state.update(original)
