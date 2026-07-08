r"""Streamlit control panel for the BACPACS SciStack pipeline.

Run from the Pipeline_development folder:
    .\BACPACS_env\python.exe -m streamlit run Modality_Pipelines\control_panel\app.py
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from Modality_Pipelines.common.study_config import load_study_config
from Modality_Pipelines.control_panel.db_service import (
    build_processing_ledger,
    get_ledger_stage_map,
    get_config_state,
    get_lineage_records,
)
from Modality_Pipelines.control_panel.pipeline_api import (
    preview_raw_file_manifest,
    register_all_raw_files,
)


st.set_page_config(page_title="BACPACS control", layout="wide")

STATUS_COLORS = {
    "complete": "#248A3D",
    "partial": "#B5820A",
    "attention": "#D14343",
    "empty": "#6E6E73",
}

PAGES = [
    "Processing ledger",
    "Raw file review",
    "Configuration",
    "Lineage / records",
]

MODALITIES = ["gaitrite", "xsens", "delsys", "cosmed", "afo"]
DISPLAY_MODALITIES = {
    "gaitrite": "Gaitrite",
    "xsens": "Xsens",
    "delsys": "Delsys",
    "cosmed": "Cosmed",
    "afo": "AFO",
}


def main() -> None:
    _inject_css()
    if "page" not in st.session_state:
        st.session_state["page"] = PAGES[0]
    if "selected_modalities" not in st.session_state:
        st.session_state["selected_modalities"] = list(MODALITIES)
    if "selected_study" not in st.session_state:
        st.session_state["selected_study"] = None

    render_top_bar()
    if not st.session_state.get("selected_study"):
        render_study_gate()
        return
    render_sidebar()

    page = st.session_state["page"]
    if page == "Processing ledger":
        render_ledger()
    elif page == "Raw file review":
        render_raw_file_review()
    elif page == "Configuration":
        render_configuration()
    elif page == "Lineage / records":
        render_lineage()


def selected_study() -> str:
    """Return the selected study key."""
    return st.session_state.get("selected_study") or "R2"


def render_top_bar() -> None:
    study = st.session_state.get("selected_study")
    if study:
        cfg = load_study_config(study)
        brand = cfg.project_name
        db_path = str(cfg.database_path)
        path_text = _truncate_path(db_path, 62)
    else:
        brand = "BACPACS control"
        db_path = "Select a study to load pipeline state"
        path_text = db_path
    st.markdown(
        f"""
        <div class="top-bar">
            <div class="top-bar__brand">{brand}</div>
            <div class="top-bar__path" title="{db_path}">{path_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_study_gate() -> None:
    st.header("Select study")
    cols = st.columns(2)
    studies = [("R1", load_study_config("R1")), ("R2", load_study_config("R2"))]
    for col, (study_key, cfg) in zip(cols, studies):
        with col:
            st.markdown(
                f"""
                <section class="study-card">
                    <div class="study-card__key">{study_key}</div>
                    <div class="study-card__title">{cfg.project_name}</div>
                    <div class="study-card__path">{_truncate_path(str(cfg.subject_data_root), 80)}</div>
                </section>
                """,
                unsafe_allow_html=True,
            )
            if st.button(f"Open {study_key}", key=f"open_{study_key}", type="primary", use_container_width=True):
                st.session_state["selected_study"] = study_key
                st.rerun()


def render_sidebar() -> None:
    with st.sidebar:
        cfg = load_study_config(selected_study())
        st.markdown("<div class='sidebar-title'>BACPACS control</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='sidebar-caption'>{cfg.project_name}</div>", unsafe_allow_html=True)
        study_choice = st.radio(
            "Study",
            options=["R1", "R2"],
            index=["R1", "R2"].index(selected_study()),
            horizontal=True,
        )
        if study_choice != selected_study():
            st.session_state["selected_study"] = study_choice
            st.session_state.pop("manifest", None)
            st.session_state.pop("registration_result", None)
            st.rerun()
        for page in PAGES:
            active = st.session_state.get("page") == page
            button_type = "primary" if active else "secondary"
            if st.button(page, key=f"nav_{page}", use_container_width=True, type=button_type):
                st.session_state["page"] = page
                st.rerun()


def render_ledger() -> None:
    st.header("Processing ledger")
    stage_map = get_ledger_stage_map(study=selected_study())
    ledger = build_processing_ledger(stage_map=stage_map, study=selected_study())
    st.caption(f"Database query as of {datetime.now().strftime('%H:%M:%S')}")

    if ledger.empty:
        _empty_state("No registered raw or processed records were found in the SciDB database.")
        return

    _render_participant_flow(ledger, stage_map)

    with st.expander("Raw table counts"):
        status_filter = st.radio(
            "View",
            options=["Counts", "Status"],
            horizontal=True,
        )
        if status_filter == "Status":
            display = ledger[["participant", "ledger_status", "ledger_reason"]]
        else:
            display = ledger
        st.dataframe(_style_status(display), use_container_width=True, hide_index=True)


def render_raw_file_review() -> None:
    st.header("Raw file review")
    st.caption("Scan first. Review rows. Register valid rows from this page into RawFile tables.")

    selected_modalities = _modality_selector()
    actions = st.columns([0.9, 0.9, 5])
    with actions[0]:
        scan = st.button("Scan", type="primary", use_container_width=True)
    with actions[1]:
        clear = st.button("Clear", use_container_width=True)

    if clear:
        st.session_state.pop("manifest", None)
        st.session_state.pop("registration_result", None)
        st.rerun()

    if scan:
        st.session_state["manifest"] = preview_raw_file_manifest(
            modality_keys=selected_modalities,
            study=selected_study(),
        )
        st.session_state.pop("registration_result", None)

    manifest = st.session_state.get("manifest")
    if not isinstance(manifest, pd.DataFrame):
        _empty_state("No scan results yet.")
        return

    valid_count = int((manifest["status"] == "valid").sum()) if "status" in manifest else 0
    review_count = int((manifest["status"] != "valid").sum()) if "status" in manifest else 0
    _render_stat_row(
        [
            ("Discovered", len(manifest), "default"),
            ("Ready to register", valid_count, "default"),
            ("Needs review", review_count, "attention" if review_count else "default"),
        ]
    )

    if valid_count:
        if st.button("Register valid files", type="primary"):
            counts = register_all_raw_files(
                manifest_df=manifest,
                only_valid=True,
                study=selected_study(),
            )
            st.session_state["registration_result"] = counts
            st.success(f"Registered {counts.get('registered', 0)} files; skipped {counts.get('skipped', 0)}.")
    else:
        st.button("Register valid files", disabled=True)

    result = st.session_state.get("registration_result")
    if result:
        st.success(f"Last registration: {result.get('registered', 0)} registered, {result.get('skipped', 0)} skipped.")

    filter_status = st.radio("Rows", ["All", "Valid", "Needs review"], horizontal=True)
    display = manifest
    if filter_status == "Valid" and "status" in manifest:
        display = manifest[manifest["status"] == "valid"]
    elif filter_status == "Needs review" and "status" in manifest:
        display = manifest[manifest["status"] != "valid"]

    display = _manifest_display(display)
    st.dataframe(display, use_container_width=True, hide_index=True)
    with st.expander("Full paths"):
        path_cols = [col for col in ["file_name", "file_path"] if col in manifest.columns]
        st.dataframe(manifest[path_cols], use_container_width=True, hide_index=True)


def render_configuration() -> None:
    st.header("Configuration")
    config = get_config_state(study=selected_study())
    if config.empty:
        _empty_state("No configuration rows were found.")
        return

    overview_tab, vocabulary_tab, processing_tab, raw_tab = st.tabs(
        ["Overview", "Study vocabulary", "Processing configs", "Raw key/value"]
    )
    shared = config[config["config"] == "Selected Study Config"].copy()

    with overview_tab:
        st.caption(f"Source: `{_truncate_path(_source_path(shared))}`")
        overview_keys = [
            "metadata.project_name",
            "metadata.version",
            "metadata.last_updated",
            "project.project_root",
            "project.subject_data_root",
            "project.pipeline_root",
            "project.database_path",
            "file_naming.pattern",
            "file_naming.schema_keys",
        ]
        _render_config_table(shared[shared["key"].isin(overview_keys)])

    with vocabulary_tab:
        st.markdown("#### Visits")
        _render_config_table(_prefix_rows(shared, ["visits."]))
        st.markdown("#### Modalities")
        _render_config_table(_prefix_rows(shared, ["modalities."]))
        st.markdown("#### Conditions")
        _render_config_table(_prefix_rows(shared, ["conditions."]))
        st.markdown("#### Tasks")
        _render_config_table(_prefix_rows(shared, ["tasks.", "speed_outcome_codes."]))

    with processing_tab:
        for config_name in ["Delsys Config", "Xsens Config", "GAITRite Config", "Cosmed Config"]:
            rows = config[config["config"] == config_name].copy()
            if rows.empty:
                continue
            with st.expander(_sentence_config_name(config_name), expanded=config_name in {"Delsys Config", "Xsens Config"}):
                st.caption(f"Source: `{_truncate_path(_source_path(rows))}`")
                metadata = _prefix_rows(rows, ["metadata."])
                settings = rows[~rows["key"].str.startswith("metadata.", na=False)]
                if not metadata.empty:
                    _render_config_table(metadata)
                _render_config_table(settings)

    with raw_tab:
        st.caption("Flattened JSON audit table")
        raw = config.copy()
        raw["source_path"] = raw["source_path"].map(_truncate_path)
        st.dataframe(raw, use_container_width=True, hide_index=True)


def render_lineage() -> None:
    st.header("Lineage / records")
    lineage = get_lineage_records(study=selected_study())
    if lineage.empty:
        _empty_state("No lineage records were found.")
        return
    st.dataframe(lineage, use_container_width=True, hide_index=True)


def _render_participant_flow(ledger: pd.DataFrame, stage_map: list[dict]) -> None:
    for _, row in ledger.iterrows():
        status = str(row.get("ledger_status", "empty"))
        reason = str(row.get("ledger_reason", ""))
        lanes = "".join(_modality_lane(row, modality) for modality in stage_map)
        st.markdown(
            f"""
            <section class="participant-flow participant-flow--{status}">
                <div class="participant-flow__header">
                    <div>
                        <div class="participant-flow__label">Participant</div>
                        <div class="participant-flow__title">{row['participant']}</div>
                    </div>
                    <div class="participant-flow__state participant-flow__state--{status}">{status.title()}</div>
                </div>
                <div class="participant-flow__reason">{reason}</div>
                <div class="modality-lanes">{lanes}</div>
            </section>
            """,
            unsafe_allow_html=True,
        )


def _modality_lane(row: pd.Series, modality: dict) -> str:
    stages = modality["stages"]
    analysis_stage = _analysis_stage(modality)
    stage_html = "".join(_stage_chip(stage["label"], _count(row, stage["column"])) for stage in stages)
    stage_html += _analysis_chip(row, stages[0]["column"], analysis_stage["column"])
    lane_status = _lane_status(row, stages[0]["column"], analysis_stage["column"])
    return f"""
        <div class="modality-lane modality-lane--{lane_status}">
            <div class="modality-lane__title">{modality['label']}</div>
            <div class="stage-stack">{stage_html}</div>
        </div>
    """


def _stage_chip(label: str, count: int) -> str:
    state = "complete" if count > 0 else "empty"
    return f"""
        <div class="stage-chip stage-chip--{state}">
            <span class="stage-chip__name">{label}</span>
            <span class="stage-chip__value">{count}</span>
        </div>
    """


def _analysis_chip(row: pd.Series, raw_column: str, analysis_column: str) -> str:
    raw = _count(row, raw_column)
    processed = _count(row, analysis_column)
    if processed > 0:
        state = "complete"
        value = "Ready"
    elif raw > 0:
        state = "attention"
        value = "Blocked"
    else:
        state = "empty"
        value = "No data"
    return f"""
        <div class="stage-chip stage-chip--{state}">
            <span class="stage-chip__name">Analysis</span>
            <span class="stage-chip__value">{value}</span>
        </div>
    """


def _analysis_stage(modality: dict) -> dict:
    for stage in reversed(modality["stages"]):
        if stage.get("role") == "analysis":
            return stage
    return modality["stages"][-1]


def _lane_status(row: pd.Series, raw_column: str, analysis_column: str) -> str:
    raw = _count(row, raw_column)
    processed = _count(row, analysis_column)
    if raw > 0 and processed == 0:
        return "attention"
    if raw > 0 and processed < raw:
        return "partial"
    if processed > 0:
        return "complete"
    return "empty"


def _count(row: pd.Series, column: str) -> int:
    value = row.get(column, 0)
    if pd.isna(value):
        return 0
    return int(value)


def _modality_selector() -> list[str]:
    st.markdown("#### Modalities")
    selected = list(st.session_state["selected_modalities"])
    cols = st.columns(len(MODALITIES))
    for col, modality in zip(cols, MODALITIES):
        active = modality in selected
        label = DISPLAY_MODALITIES[modality]
        button_type = "primary" if active else "secondary"
        with col:
            if st.button(label, key=f"modality_{modality}", type=button_type, use_container_width=True):
                if active:
                    selected = [item for item in selected if item != modality]
                else:
                    selected.append(modality)
                st.session_state["selected_modalities"] = selected
                st.rerun()
    if not selected:
        st.warning("Select at least one modality to scan.")
        return list(MODALITIES)
    return selected


def _manifest_display(df: pd.DataFrame) -> pd.DataFrame:
    display = df.copy()
    if "file_name" not in display and "file_path" in display:
        display["file_name"] = display["file_path"].map(lambda value: str(value).split("\\")[-1])
    preferred = [
        "participant_number",
        "visit",
        "test",
        "condition",
        "speed",
        "trial",
        "modality",
        "status",
        "issues",
        "file_name",
        "extension",
    ]
    cols = [col for col in preferred if col in display.columns]
    remaining = [col for col in display.columns if col not in cols and col != "file_path"]
    display = display[cols + remaining]
    return display.rename(columns={col: col.lower() for col in display.columns})


def _prefix_rows(df: pd.DataFrame, prefixes: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    mask = False
    for prefix in prefixes:
        mask = mask | df["key"].str.startswith(prefix, na=False)
    return df[mask].copy()


def _source_path(df: pd.DataFrame) -> str:
    if df.empty or "source_path" not in df:
        return "unknown"
    return str(df["source_path"].iloc[0])


def _render_config_table(rows: pd.DataFrame) -> None:
    if rows.empty:
        st.caption("No values found.")
        return
    display = rows[["key", "value"]].copy()
    display = display.rename(columns={"key": "setting", "value": "value"})
    st.dataframe(display, use_container_width=True, hide_index=True)


def _render_stat_row(stats: list[tuple[str, int, str]]) -> None:
    items = []
    for label, value, tone in stats:
        tone_class = " stat-pair__value--attention" if tone == "attention" else ""
        items.append(
            f"""
            <div class="stat-pair">
                <div class="stat-pair__label">{label}</div>
                <div class="stat-pair__value{tone_class}">{value}</div>
            </div>
            """
        )
    st.markdown(f"<div class='stat-row'>{''.join(items)}</div>", unsafe_allow_html=True)


def _empty_state(message: str) -> None:
    st.markdown(f"<div class='empty-state'>{message}</div>", unsafe_allow_html=True)


def _truncate_path(path: str, max_chars: int = 72) -> str:
    if len(path) <= max_chars:
        return path
    return "..." + path[-(max_chars - 3):]


def _sentence_config_name(name: str) -> str:
    return name.replace(" Config", " config")


def _style_status(df: pd.DataFrame):
    if "ledger_status" not in df.columns:
        return df

    def color_row(row):
        color = STATUS_COLORS.get(row.get("ledger_status"), "#6E6E73")
        return [f"border-left: 4px solid {color}" if col == "participant" else "" for col in row.index]

    return df.style.apply(color_row, axis=1)


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400&display=swap');

        :root {
            --ink: #1C1C1E;
            --ink-secondary: #6E6E73;
            --canvas: #F5F5F7;
            --surface: #FFFFFF;
            --hairline: #E5E5EA;
            --accent: #4F5BD5;
            --accent-soft: #EEF0FC;
            --status-complete: #248A3D;
            --status-partial: #B5820A;
            --status-attention: #D14343;
            --status-missing: #AEAEB2;
            --status-notexp: #D1D1D6;
            --shadow-1: 0 1px 2px rgba(0, 0, 0, 0.04);
            --shadow-2: 0 8px 24px rgba(0, 0, 0, 0.06);
        }

        html, body, [class*="css"], [data-testid="stAppViewContainer"] {
            font-family: "Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            color: var(--ink);
            background: var(--canvas);
        }

        [data-testid="stAppViewContainer"] > .main {
            background: var(--canvas);
        }

        .block-container {
            max-width: 1440px;
            padding-top: 4.25rem;
            padding-bottom: 3rem;
        }

        .top-bar {
            align-items: center;
            background: rgba(255, 255, 255, 0.88);
            border-bottom: 1px solid var(--hairline);
            box-shadow: var(--shadow-1);
            backdrop-filter: blur(20px);
            display: flex;
            height: 46px;
            justify-content: space-between;
            left: 0;
            padding: 0 1.25rem;
            position: fixed;
            right: 0;
            top: 0;
            z-index: 9999;
        }

        .top-bar__brand {
            color: var(--ink);
            font-size: 0.875rem;
            font-weight: 500;
        }

        .top-bar__path {
            color: var(--ink-secondary);
            font-family: "JetBrains Mono", Consolas, monospace;
            font-size: 0.8125rem;
            max-width: 58vw;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        h1, h2, h3, h4, h5, h6 {
            font-family: "Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            color: var(--ink);
            font-weight: 600;
            letter-spacing: 0;
        }

        h1 {
            font-size: 1.5rem;
            line-height: 1.3;
        }

        h2, h3 {
            font-size: 1.125rem;
            line-height: 1.3;
        }

        p, label, span, div {
            letter-spacing: 0;
        }

        code, pre, kbd, [data-testid="stCodeBlock"], .mono {
            font-family: "JetBrains Mono", Consolas, "SFMono-Regular", monospace;
            font-weight: 400;
        }

        [data-testid="stSidebar"] {
            background: rgba(255, 255, 255, 0.82);
            border-right: 1px solid var(--hairline);
            box-shadow: none;
            backdrop-filter: blur(20px);
            padding-top: 2.6rem;
        }

        .sidebar-title {
            color: var(--ink);
            font-size: 0.875rem;
            font-weight: 600;
            margin: 0 0 0.1rem 0;
        }

        .sidebar-caption,
        [data-testid="stCaptionContainer"] {
            color: var(--ink-secondary);
            font-size: 0.8125rem;
        }

        .stButton > button {
            border-radius: 10px;
            border: 1px solid var(--hairline);
            background: transparent;
            color: var(--ink-secondary);
            box-shadow: none;
            font-family: "Inter", system-ui, sans-serif;
            font-weight: 500;
            min-height: 2.35rem;
            transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
        }

        .stButton > button:hover {
            border-color: var(--hairline);
            background: var(--accent-soft);
            color: var(--ink);
        }

        .stButton > button[kind="primary"],
        .stButton > button[data-testid="baseButton-primary"] {
            background: var(--accent-soft);
            border-color: transparent;
            color: var(--ink);
            box-shadow: none;
        }

        [data-testid="stSidebar"] .stButton > button {
            background: transparent;
            border: none;
            border-left: 3px solid transparent;
            border-radius: 0;
            box-shadow: none;
            color: var(--ink);
            justify-content: flex-start;
            min-height: 2.25rem;
            padding-left: 0.7rem;
        }

        [data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"] {
            background: var(--accent-soft);
            border-left-color: var(--accent);
            color: var(--ink);
        }

        .stat-row {
            display: flex;
            gap: 4rem;
            margin: 1.25rem 0 1rem 0;
        }

        .stat-pair__label {
            color: var(--ink-secondary);
            font-size: 0.8125rem;
            font-weight: 500;
            line-height: 1.3;
            margin-bottom: 0.2rem;
        }

        .stat-pair__value {
            color: var(--ink);
            font-size: 1.625rem;
            font-weight: 600;
            line-height: 1.15;
        }

        .stat-pair__value--attention {
            color: var(--status-attention);
        }

        [data-testid="stMetric"] {
            background: transparent;
            border: none;
            border-radius: 0;
            box-shadow: none;
            padding: 0;
        }

        [data-testid="stDataFrame"],
        [data-testid="stTable"] {
            background: transparent;
            border: none;
            border-radius: 0;
            box-shadow: none;
            overflow: hidden;
        }

        div[data-baseweb="radio"] {
            background: transparent;
            border: 1px solid var(--hairline);
            border-radius: 999px;
            box-shadow: none;
            display: inline-flex;
            padding: 3px;
        }

        div[data-baseweb="radio"] label {
            border-radius: 999px;
            padding: 0.2rem 0.6rem;
        }

        div[data-baseweb="radio"] label:has(input:checked) {
            background: var(--accent-soft);
            color: var(--accent);
        }

        input, textarea, [data-baseweb="input"] {
            font-family: "JetBrains Mono", Consolas, monospace;
        }

        [data-testid="stAlert"] {
            border-radius: 14px;
            border: 1px solid var(--hairline);
            box-shadow: var(--shadow-1);
        }

        .empty-state {
            color: var(--ink-secondary);
            font-size: 0.875rem;
            padding: 3.25rem 0;
            text-align: center;
        }

        .study-card {
            background: var(--surface);
            border: 1px solid var(--hairline);
            border-radius: 14px;
            box-shadow: var(--shadow-1);
            min-height: 9rem;
            padding: 1rem;
        }

        .study-card__key {
            color: var(--accent);
            font-family: "JetBrains Mono", Consolas, monospace;
            font-size: 0.8125rem;
            margin-bottom: 0.35rem;
        }

        .study-card__title {
            color: var(--ink);
            font-size: 1.05rem;
            font-weight: 600;
            line-height: 1.3;
            margin-bottom: 0.75rem;
        }

        .study-card__path {
            color: var(--ink-secondary);
            font-family: "JetBrains Mono", Consolas, monospace;
            font-size: 0.78rem;
            line-height: 1.45;
        }

        hr {
            border-color: var(--hairline);
        }

        .participant-flow {
            background: var(--surface);
            border: 1px solid var(--hairline);
            border-left: 4px solid var(--status-missing);
            border-radius: 14px;
            box-shadow: var(--shadow-1);
            margin: 0 0 1rem 0;
            padding: 1rem;
        }

        .participant-flow--complete {
            border-left-color: var(--status-complete);
        }

        .participant-flow--partial {
            border-left-color: var(--status-partial);
        }

        .participant-flow--attention {
            border-left-color: var(--status-attention);
        }

        .participant-flow__header {
            align-items: flex-start;
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 0.35rem;
        }

        .participant-flow__label {
            color: var(--ink-secondary);
            font-size: 0.8125rem;
            font-weight: 500;
            line-height: 1.3;
        }

        .participant-flow__title {
            color: var(--ink);
            font-family: "JetBrains Mono", Consolas, monospace;
            font-size: 1.125rem;
            font-weight: 400;
            line-height: 1.3;
        }

        .participant-flow__state {
            border-radius: 999px;
            font-size: 0.8125rem;
            font-weight: 600;
            padding: 0.25rem 0.65rem;
            white-space: nowrap;
        }

        .participant-flow__state--complete {
            background: rgba(36, 138, 61, 0.1);
            color: var(--status-complete);
        }

        .participant-flow__state--partial {
            background: rgba(181, 130, 10, 0.12);
            color: var(--status-partial);
        }

        .participant-flow__state--attention {
            background: rgba(209, 67, 67, 0.1);
            color: var(--status-attention);
        }

        .participant-flow__state--empty {
            background: var(--canvas);
            color: var(--ink-secondary);
        }

        .participant-flow__reason {
            color: var(--ink-secondary);
            font-size: 0.8125rem;
            line-height: 1.45;
            margin-bottom: 0.85rem;
            min-height: 1rem;
        }

        .modality-lanes {
            display: grid;
            gap: 0.75rem;
            grid-template-columns: repeat(5, minmax(0, 1fr));
        }

        .modality-lane {
            background: #FAFAFB;
            border: 1px solid var(--hairline);
            border-top: 3px solid var(--status-missing);
            border-radius: 14px;
            min-width: 0;
            padding: 0.75rem;
        }

        .modality-lane--complete {
            border-top-color: var(--status-complete);
        }

        .modality-lane--partial {
            border-top-color: var(--status-partial);
        }

        .modality-lane--attention {
            border-top-color: var(--status-attention);
        }

        .modality-lane__title {
            color: var(--ink);
            font-size: 0.875rem;
            font-weight: 600;
            line-height: 1.3;
            margin-bottom: 0.55rem;
        }

        .stage-stack {
            display: flex;
            flex-direction: column;
            gap: 0.4rem;
        }

        .stage-chip {
            align-items: center;
            background: var(--surface);
            border: 1px solid var(--hairline);
            border-radius: 10px;
            display: flex;
            gap: 0.5rem;
            justify-content: space-between;
            min-height: 2rem;
            padding: 0.35rem 0.5rem;
        }

        .stage-chip--complete {
            border-color: rgba(36, 138, 61, 0.28);
            background: rgba(36, 138, 61, 0.06);
        }

        .stage-chip--attention {
            border-color: rgba(209, 67, 67, 0.28);
            background: rgba(209, 67, 67, 0.06);
        }

        .stage-chip--empty {
            color: var(--ink-secondary);
        }

        .stage-chip__name {
            color: var(--ink-secondary);
            font-size: 0.8125rem;
            font-weight: 500;
        }

        .stage-chip__value {
            color: var(--ink);
            font-family: "JetBrains Mono", Consolas, monospace;
            font-size: 0.8125rem;
            font-weight: 400;
            white-space: nowrap;
        }

        .stage-chip--attention .stage-chip__value {
            color: var(--status-attention);
            font-family: "Inter", system-ui, sans-serif;
            font-weight: 600;
        }

        .stage-chip--complete .stage-chip__value {
            color: var(--status-complete);
        }

        @media (max-width: 1200px) {
            .modality-lanes {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }

        @media (max-width: 760px) {
            .modality-lanes {
                grid-template-columns: 1fr;
            }
            .top-bar__path {
                display: none;
            }
            .stat-row {
                gap: 1.5rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()

