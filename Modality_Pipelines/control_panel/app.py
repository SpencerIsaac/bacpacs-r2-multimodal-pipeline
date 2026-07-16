r"""Streamlit control panel for the BACPACS SciStack pipeline.

Run from the Pipeline_development folder:
    .\BACPACS_env\python.exe -m streamlit run Modality_Pipelines\control_panel\app.py
"""

from __future__ import annotations

from datetime import date, datetime
import html
from io import BytesIO
import math

import streamlit as st

from Modality_Pipelines.common.study_config import load_study_config

st.set_page_config(page_title="BACPACS control", layout="wide")

STATUS_COLORS = {
    "complete": "#248A3D",
    "partial": "#B5820A",
    "attention": "#D14343",
    "empty": "#6E6E73",
}

PAGES = [
    "Pipeline workflow",
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

NAV_ICONS = {
    "Pipeline workflow": ":material/play_circle:",
    "Processing ledger": ":material/checklist:",
    "Raw file review": ":material/search:",
    "Configuration": ":material/tune:",
    "Lineage / records": ":material/account_tree:",
}


@st.cache_data(show_spinner=False)
def cached_study_summary(study: str) -> dict[str, str]:
    cfg = load_study_config(study)
    return {
        "study": cfg.study,
        "project_name": cfg.project_name,
        "subject_data_root": str(cfg.subject_data_root),
        "database_path": str(cfg.database_path),
    }


@st.cache_data(ttl=10, show_spinner="Loading stage map...")
def cached_ledger_stage_map(study: str) -> list[dict]:
    from Modality_Pipelines.control_panel.db_service import get_ledger_stage_map

    return get_ledger_stage_map(study=study)


@st.cache_data(ttl=10, show_spinner="Loading processing ledger...")
def cached_processing_ledger(study: str, refresh_token: int):
    from Modality_Pipelines.control_panel.db_service import build_processing_ledger

    stage_map = cached_ledger_stage_map(study)
    return build_processing_ledger(stage_map=stage_map, study=study)


@st.cache_data(ttl=30, show_spinner="Loading configuration...")
def cached_config_state(study: str, refresh_token: int):
    from Modality_Pipelines.control_panel.db_service import get_config_state

    return get_config_state(study=study)


@st.cache_data(ttl=10, show_spinner="Loading lineage records...")
def cached_lineage_records(study: str, refresh_token: int):
    from Modality_Pipelines.control_panel.db_service import get_lineage_records

    return get_lineage_records(study=study)



def _stage_map_display(stage_map: list[dict]) -> "pd.DataFrame":
    import pandas as pd

    rows = []
    for modality in stage_map:
        stages = modality.get("stages", [])
        rows.append(
            {
                "key": modality.get("key", ""),
                "label": modality.get("label", ""),
                "stage flow": " -> ".join(stage.get("label", "") for stage in stages),
                "tables": ", ".join(stage.get("table", "") for stage in stages),
            }
        )
    return pd.DataFrame(rows)


def warm_selected_study_caches() -> None:
    """Preload page-level data after a study is selected."""
    study = selected_study()
    refresh_token = st.session_state["refresh_token"]
    warm_key = f"{study}:{refresh_token}"
    if st.session_state.get("cache_warm_key") == warm_key:
        return

    cached_ledger_stage_map(study)
    cached_processing_ledger(study, refresh_token)
    cached_config_state(study, refresh_token)
    cached_lineage_records(study, refresh_token)
    st.session_state["cache_warm_key"] = warm_key


def main() -> None:
    _inject_css()
    if "page" not in st.session_state:
        st.session_state["page"] = PAGES[0]
    if "selected_modalities" not in st.session_state:
        st.session_state["selected_modalities"] = list(MODALITIES)
    if "selected_study" not in st.session_state:
        st.session_state["selected_study"] = None
    if "refresh_token" not in st.session_state:
        st.session_state["refresh_token"] = 0
    if "cache_warm_key" not in st.session_state:
        st.session_state["cache_warm_key"] = None

    render_top_bar()
    if not st.session_state.get("selected_study"):
        render_study_gate()
        return
    render_sidebar()

    page = st.session_state["page"]
    if page == "Pipeline workflow":
        render_pipeline_workflow()
    elif page == "Processing ledger":
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


def apply_study_selection(study_choice: str | None) -> bool:
    """Apply a study change and clear study-scoped UI state."""
    if not study_choice or study_choice == selected_study():
        return False
    st.session_state["selected_study"] = study_choice
    _clear_study_scoped_state()
    return True


def _clear_study_scoped_state() -> None:
    st.session_state.pop("manifest", None)
    st.session_state.pop("registration_result", None)
    st.session_state.pop("workflow_result", None)
    st.session_state.pop("workflow_manifest", None)
    st.session_state["cache_warm_key"] = None


def on_study_segment_change() -> None:
    """Mirror the sidebar study widget into app state before page rendering."""
    apply_study_selection(st.session_state.get("study_segment"))


def render_top_bar() -> None:
    study = st.session_state.get("selected_study")
    if study:
        cfg = cached_study_summary(study)
        brand = cfg["project_name"]
        db_path = cfg["database_path"]
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
    studies = [("R1", cached_study_summary("R1")), ("R2", cached_study_summary("R2"))]
    for col, (study_key, cfg) in zip(cols, studies):
        with col:
            st.markdown(
                f"""
                <section class="study-card">
                    <div class="study-card__key">{study_key}</div>
                    <div class="study-card__title">{cfg["project_name"]}</div>
                    <div class="study-card__path">{_truncate_path(cfg["subject_data_root"], 80)}</div>
                </section>
                """,
                unsafe_allow_html=True,
            )
            if st.button(f"Open {study_key}", key=f"open_{study_key}", type="primary", width="stretch"):
                st.session_state["selected_study"] = study_key
                st.session_state["study_segment"] = study_key
                st.rerun()


def render_sidebar() -> None:
    with st.sidebar:
        if st.session_state.get("study_segment") != selected_study():
            st.session_state["study_segment"] = selected_study()
        cfg = cached_study_summary(selected_study())

        st.markdown(
            f"""
            <section class="drawer-card">
                <div class="drawer-title">BACPACS control</div>
                <div class="drawer-subtitle">{cfg['project_name']}</div>
            </section>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<div class='drawer-label'>BACPACS study</div>", unsafe_allow_html=True)
        st.segmented_control(
            "BACPACS study",
            options=["R1", "R2"],
            key="study_segment",
            label_visibility="collapsed",
            width="stretch",
            on_change=on_study_segment_change,
        )

        st.markdown("<div class='drawer-nav'>", unsafe_allow_html=True)
        for page in PAGES:
            active = st.session_state.get("page") == page
            button_type = "primary" if active else "tertiary"
            if st.button(
                page,
                key=f"nav_{page}",
                width="stretch",
                type=button_type,
                icon=NAV_ICONS.get(page),
            ):
                st.session_state["page"] = page
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)



def render_pipeline_workflow() -> None:
    st.header("Pipeline workflow")
    st.caption("Run the same backend actions exposed by the BACPACS CLI. Preview steps are read-only; write steps are available directly.")

    filters = _workflow_filters()
    _render_filter_summary(filters)

    setup_tab, validate_tab, register_tab, process_tab, analysis_tab, status_tab = st.tabs(
        ["Setup check", "Validate", "Register", "Process", "Analyze", "Status"]
    )

    with setup_tab:
        st.markdown("#### Setup check")
        st.caption("Mirrors `bacpacs doctor` for the selected study and shared repository environment.")
        if st.button("Run setup check", type="primary", key="workflow_doctor"):
            st.session_state["workflow_result"] = ("Setup check", _doctor_rows(selected_study()))
        result = st.session_state.get("workflow_result")
        if result and result[0] == "Setup check":
            import pandas as pd

            _render_dataframe(pd.DataFrame(result[1]), width="stretch", hide_index=True)

    with validate_tab:
        st.markdown("#### Dry-run validation")
        st.caption("Mirrors `bacpacs validate`. This scans filenames and folder locations without writing to the database.")
        if st.button("Validate files", type="primary", key="workflow_validate"):
            from Modality_Pipelines.common.manifest import validate_study_files

            with st.spinner("Validating raw files..."):
                manifest = validate_study_files(study=selected_study(), **filters)
            st.session_state["workflow_manifest"] = manifest
            st.session_state["workflow_result"] = ("Validate", _status_counts(manifest))
        manifest = st.session_state.get("workflow_manifest")
        if manifest is not None:
            _render_validation_manifest(manifest)

    with register_tab:
        st.markdown("#### RawFile registration")
        st.caption("Mirrors `bacpacs register`. Dry-run previews are read-only; registration writes RawFile records for valid new files.")
        cols = st.columns([1, 3])
        with cols[0]:
            preview = st.button("Preview registration", key="workflow_register_preview", width="stretch")
        with cols[1]:
            write = st.button(
                "Register valid files",
                type="primary",
                key="workflow_register_write",
                width="content",
            )
        if preview or write:
            from Modality_Pipelines.common.manifest import register_raw_files

            with st.spinner("Preparing registration..." if preview else "Registering raw files..."):
                counts = register_raw_files(study=selected_study(), dry_run=preview, **filters)
            mode = "Registration preview" if preview else "Registration write"
            st.session_state["workflow_result"] = (mode, counts)
            if write:
                _refresh_database_caches()
        _render_workflow_result(["Registration preview", "Registration write"])

    with process_tab:
        st.markdown("#### First-pass modality processing")
        st.caption("Mirrors `bacpacs process`. Processors read registered RawFile records and write processed tables.")
        process_cols = st.columns([1.2, 1, 2])
        with process_cols[0]:
            process_modality = st.selectbox("Modality", ["all", *MODALITIES], key="workflow_process_modality")
        with process_cols[1]:
            overwrite = st.checkbox("Overwrite", key="workflow_process_overwrite")
        with process_cols[2]:
            preview_process = st.button("Preview processing", key="workflow_process_preview")
            run_process = st.button("Run processing", type="primary", key="workflow_process_run")
        if preview_process or run_process:
            from Modality_Pipelines.common.processing import run_modality_processing

            with st.spinner("Planning processing..." if preview_process else "Running processing..."):
                result = run_modality_processing(
                    study=selected_study(),
                    modality=process_modality,
                    dry_run=preview_process,
                    overwrite=overwrite,
                    **_filters_without_modality(filters),
                )
            mode = "Processing preview" if preview_process else "Processing write"
            st.session_state["workflow_result"] = (mode, result)
            if run_process:
                _refresh_database_caches()
        _render_workflow_result(["Processing preview", "Processing write"])

    with analysis_tab:
        st.markdown("#### Derived analysis tables")
        st.caption("Builds TrialAnalysis, CycleUnmatched, VisitSummary, CycleMatched, and AnalysisIssue from processed Xsens, Delsys, and GAITRite tables.")
        analysis_filters = _filters_without_modality(filters)
        table_counts = _downstream_table_counts(selected_study(), analysis_filters)
        _render_dataframe(table_counts, width="stretch", hide_index=True)

        stage_labels = {
            "build-all": "Build all and export",
            "build-trial": "Build trial table",
            "build-cycles": "Build unmatched cycles",
            "finalize-visit": "Finalize visit summary",
            "normalize-cycles": "Normalize cycles to visit",
            "build-matched": "Build matched cycles",
            "export": "Export existing tables",
        }
        stage_functions = {
            "build-all": "build_all",
            "build-trial": "build_trial_analysis",
            "build-cycles": "build_cycle_unmatched",
            "finalize-visit": "finalize_visit_summary",
            "normalize-cycles": "normalize_cycles_to_visit",
            "build-matched": "build_cycle_matched",
            "export": "export_analysis_tables",
        }
        derived_cols = st.columns([1.6, 1, 2.4])
        with derived_cols[0]:
            derived_stage = st.selectbox(
                "Stage",
                options=list(stage_labels),
                format_func=lambda value: stage_labels[value],
                key="workflow_derived_stage",
            )
        with derived_cols[1]:
            refresh_counts = st.button("Refresh counts", key="workflow_derived_refresh", width="stretch")
        with derived_cols[2]:
            run_derived = st.button(
                stage_labels[derived_stage],
                type="primary" if derived_stage == "build-all" else "secondary",
                key="workflow_derived_run",
                width="stretch",
            )
        if refresh_counts:
            _refresh_database_caches()
            st.rerun()
        if run_derived:
            from Modality_Pipelines.common import downstream_analysis

            fn = getattr(downstream_analysis, stage_functions[derived_stage])
            kwargs = {"study": selected_study(), **analysis_filters}
            if derived_stage in {"build-all", "export"}:
                kwargs["output_dir"] = None
            try:
                with st.spinner(f"Running {stage_labels[derived_stage].lower()}..."):
                    result = fn(**kwargs)
            except downstream_analysis.AnalysisPreconditionError as exc:
                st.error(f"Analysis precondition failed: {exc}")
            else:
                st.session_state["workflow_result"] = ("Derived analysis", result)
                _refresh_database_caches()
                st.success("Derived analysis stage completed.")
        _render_workflow_result(["Derived analysis"])

        st.divider()
        st.markdown("#### Registry analyses")
        st.caption("Optional ad hoc analyses discovered from the runtime registry. These are separate from the fixed downstream table layer above.")
        from Modality_Pipelines.common.analysis_registry import list_available_analyses

        analyses = list_available_analyses(study=selected_study())
        if not analyses:
            _empty_state("No registry analyses are registered for this study.")
        else:
            _render_analysis_table(analyses)
            analysis_names = [row["name"] for row in analyses]
            analysis_cols = st.columns([1.4, 1, 2])
            with analysis_cols[0]:
                analysis = st.selectbox("Analysis", analysis_names, key="workflow_analysis_name")
            with analysis_cols[1]:
                overwrite_analysis = st.checkbox("Overwrite", key="workflow_analysis_overwrite")
            with analysis_cols[2]:
                preview_analysis = st.button("Preview analysis", key="workflow_analysis_preview")
                run_analysis = st.button("Run analysis", type="primary", key="workflow_analysis_run")
            if preview_analysis or run_analysis:
                from Modality_Pipelines.common.analysis_registry import run_registered_analysis

                with st.spinner("Planning analysis..." if preview_analysis else "Running analysis..."):
                    result = run_registered_analysis(
                        study=selected_study(),
                        analysis=analysis,
                        dry_run=preview_analysis,
                        overwrite=overwrite_analysis,
                        **analysis_filters,
                    )
                mode = "Analysis preview" if preview_analysis else "Analysis write"
                st.session_state["workflow_result"] = (mode, result)
                if run_analysis:
                    _refresh_database_caches()
            _render_workflow_result(["Analysis preview", "Analysis write"])

    with status_tab:
        st.markdown("#### Pipeline status")
        st.caption("Mirrors `bacpacs status` and the processing ledger.")
        if st.button("Refresh status", type="primary", key="workflow_status_refresh"):
            _refresh_database_caches()
        cfg = cached_study_summary(selected_study())
        st.write(f"Study: `{cfg['study']}`")
        st.write(f"Database: `{cfg['database_path']}`")
        stage_map = cached_ledger_stage_map(selected_study())
        _render_dataframe(_stage_map_display(stage_map), width="stretch", hide_index=True)
        ledger = cached_processing_ledger(selected_study(), st.session_state["refresh_token"])
        if ledger.empty:
            _empty_state("No registered raw or processed records were found in the SciDB database.")
        else:
            _render_dataframe(ledger, width="stretch", hide_index=True)
def render_ledger() -> None:
    st.header("Processing ledger")
    cols = st.columns([1, 5])
    with cols[0]:
        if st.button("Refresh", width="stretch"):
            st.session_state["refresh_token"] += 1
            cached_processing_ledger.clear()
            cached_config_state.clear()
            cached_lineage_records.clear()
            cached_ledger_stage_map.clear()
            st.session_state["cache_warm_key"] = None
            st.rerun()
    stage_map = cached_ledger_stage_map(selected_study())
    ledger = cached_processing_ledger(selected_study(), st.session_state["refresh_token"])
    st.caption(f"Cached database view as of {datetime.now().strftime('%H:%M:%S')}. Refresh after running pipeline commands.")

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
        _render_dataframe(_style_status(display), width="stretch", hide_index=True)


def render_raw_file_review() -> None:
    st.header("Raw file review")
    st.caption("Scan first. Review rows. Register valid rows from this page into RawFile tables.")

    selected_modalities = _modality_selector()
    actions = st.columns([0.9, 0.9, 5])
    with actions[0]:
        scan = st.button("Scan", type="primary", width="stretch")
    with actions[1]:
        clear = st.button("Clear", width="stretch")

    if clear:
        st.session_state.pop("manifest", None)
        st.session_state.pop("registration_result", None)
        st.rerun()

    if scan:
        from Modality_Pipelines.control_panel.pipeline_api import preview_raw_file_manifest

        with st.spinner("Scanning raw-file folders..."):
            st.session_state["manifest"] = preview_raw_file_manifest(
                modality_keys=selected_modalities,
                study=selected_study(),
            )
        st.session_state.pop("registration_result", None)

    manifest = st.session_state.get("manifest")
    import pandas as pd

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
            from Modality_Pipelines.control_panel.pipeline_api import register_all_raw_files

            counts = register_all_raw_files(
                manifest_df=manifest,
                only_valid=True,
                study=selected_study(),
            )
            st.session_state["refresh_token"] += 1
            cached_processing_ledger.clear()
            cached_config_state.clear()
            cached_lineage_records.clear()
            st.session_state["cache_warm_key"] = None
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
    _render_dataframe(display, width="stretch", hide_index=True)
    with st.expander("Full paths"):
        path_cols = [col for col in ["file_name", "file_path"] if col in manifest.columns]
        _render_dataframe(manifest[path_cols], width="stretch", hide_index=True)


def render_configuration() -> None:
    st.header("Configuration")
    config = cached_config_state(selected_study(), st.session_state["refresh_token"])
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
        _render_dataframe(raw, width="stretch", hide_index=True)


def render_lineage() -> None:
    st.header("Lineage / records")
    lineage = cached_lineage_records(selected_study(), st.session_state["refresh_token"])
    if lineage.empty:
        _empty_state("No lineage records were found.")
        return

    st.download_button(
        "Export XLSX",
        data=_lineage_export_bytes(lineage),
        file_name=_lineage_export_filename(),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="content",
    )
    _render_dataframe(lineage, width="stretch", hide_index=True)



def _lineage_export_filename(today: date | None = None) -> str:
    export_date = today or date.today()
    return f"{export_date:%Y-%m-%d}_bacpacs_lineage.xlsx"



def _lineage_export_bytes(lineage) -> bytes:
    import pandas as pd

    output = BytesIO()
    export = _arrow_safe_dataframe(lineage)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        export.to_excel(writer, sheet_name="lineage", index=False)
    return output.getvalue()



def _workflow_filters() -> dict[str, str]:
    with st.expander("Filters", expanded=True):
        cols = st.columns(4)
        with cols[0]:
            participant_number = st.text_input("Participant", placeholder="001", key="workflow_filter_participant")
            visit = st.text_input("Visit", placeholder="BL", key="workflow_filter_visit")
        with cols[1]:
            modality = st.selectbox("Modality filter", ["", *MODALITIES], key="workflow_filter_modality")
            test = st.text_input("Test", placeholder="10MWT", key="workflow_filter_test")
        with cols[2]:
            condition = st.text_input("Condition", placeholder="noAFO", key="workflow_filter_condition")
            speed = st.text_input("Speed", placeholder="SSV", key="workflow_filter_speed")
        with cols[3]:
            trial = st.text_input("Trial", placeholder="1", key="workflow_filter_trial")
    return _clean_filter_values(
        {
            "participant_number": participant_number,
            "visit": visit,
            "modality": modality,
            "test": test,
            "condition": condition,
            "speed": speed,
            "trial": trial,
        }
    )


def _clean_filter_values(filters: dict[str, str]) -> dict[str, str]:
    return {key: str(value).strip() for key, value in filters.items() if str(value).strip()}


def _filters_without_modality(filters: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in filters.items() if key != "modality"}


def _render_filter_summary(filters: dict[str, str]) -> None:
    if not filters:
        st.info("No filters selected. Actions will run on the selected study scope.")
        return
    summary = "  ".join(f"`{key}={value}`" for key, value in filters.items())
    st.caption(f"Active filters: {summary}")


def _doctor_rows(study: str) -> list[dict[str, str]]:
    from pathlib import Path

    cfg = load_study_config(study)
    repo_root = Path(__file__).resolve().parents[2]
    env_candidates = [
        repo_root / "BACPACS_env" / "python.exe",
        repo_root / "BACPACS_env" / "Scripts" / "python.exe",
        repo_root / "BAKPACS_env" / "python.exe",
        repo_root / "BAKPACS_env" / "Scripts" / "python.exe",
    ]
    env_python = next((candidate for candidate in env_candidates if candidate.exists()), None)
    rows = [
        _path_status_row("repo_root", repo_root),
        _path_status_row("repo_env_python", env_python),
        _path_status_row(f"{study} subject_data_root", cfg.subject_data_root),
        _path_status_row(f"{study} database_path", cfg.database_path),
        _path_status_row("database_folder", cfg.database_path.parent),
    ]
    return rows


def _path_status_row(label: str, path) -> dict[str, str]:
    if path is None:
        return {"item": label, "status": "missing", "path": ""}
    return {"item": label, "status": "ok" if path.exists() else "missing", "path": str(path)}


def _status_counts(df) -> dict[str, int]:
    if df is None or df.empty or "status" not in df:
        return {}
    return {str(key): int(value) for key, value in df["status"].value_counts(dropna=False).to_dict().items()}


def _render_validation_manifest(manifest) -> None:
    counts = _status_counts(manifest)
    if counts:
        _render_stat_row([(key.title(), value, "attention" if key != "valid" else "default") for key, value in counts.items()])
    display = _manifest_display(manifest).head(200)
    _render_dataframe(display, width="stretch", hide_index=True)
    if len(manifest) > len(display):
        st.caption(f"Showing first {len(display)} of {len(manifest)} rows. Use the CLI `--output` option for a full CSV export.")


def _render_workflow_result(allowed_titles: list[str]) -> None:
    result = st.session_state.get("workflow_result")
    if not result or result[0] not in allowed_titles:
        return
    title, payload = result
    st.markdown(f"#### {title}")
    _render_result_payload(payload)


def _render_result_payload(payload, label: str | None = None) -> None:
    import pandas as pd

    if label:
        st.markdown(f"##### {label}")

    if isinstance(payload, pd.DataFrame):
        if payload.empty:
            st.info("No matching records were returned. Check that raw files are registered and that the selected filters match registered records.")
        else:
            _render_dataframe(payload, width="stretch", hide_index=True)
        return

    if isinstance(payload, dict):
        scalar_rows = []
        nested_items = []
        for key, value in payload.items():
            if _is_scalar_result(value):
                scalar_rows.append({"field": str(key), "value": _compact_value(value)})
            else:
                nested_items.append((str(key), value))
        if scalar_rows:
            _render_dataframe(pd.DataFrame(scalar_rows), width="stretch", hide_index=True)
        for nested_label, nested_value in nested_items:
            _render_result_payload(nested_value, nested_label)
        if not scalar_rows and not nested_items:
            st.info("No result details were returned.")
        return

    st.json(_json_safe(payload))


def _is_scalar_result(value) -> bool:
    return isinstance(value, (str, int, float, bool)) or value is None


def _render_analysis_table(analyses: list[dict]) -> None:
    import pandas as pd

    rows = []
    for row in analyses:
        rows.append(
            {
                "analysis": row.get("name"),
                "modality": row.get("modality"),
                "input_table": row.get("input_table", ""),
                "output_tables": ", ".join(row.get("output_tables", [])),
                "description": row.get("description", ""),
            }
        )
    _render_dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)



def _downstream_table_counts(study: str, filters: dict[str, str]):
    import pandas as pd

    from Modality_Pipelines.common import downstream_analysis

    labels = {
        "trial": "TrialAnalysis",
        "cycle_unmatched": "CycleUnmatched",
        "visit": "VisitSummary",
        "cycle_matched": "CycleMatched",
        "issue": "AnalysisIssue",
    }
    try:
        ctx = downstream_analysis._context(study, filters)
    except Exception as exc:
        return pd.DataFrame([{"table": "database", "rows": 0, "status": f"unavailable: {exc}"}])

    rows = []
    for key, label in labels.items():
        table_name = downstream_analysis.ANALYSIS_TABLES[study][key]
        try:
            df = downstream_analysis._load_table(ctx, key)
            rows.append({"table": table_name, "role": label, "rows": int(len(df)), "status": "ok"})
        except Exception as exc:
            rows.append({"table": table_name, "role": label, "rows": 0, "status": f"error: {exc}"})
    return pd.DataFrame(rows)
def _compact_value(value) -> str:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return str(value)
    if isinstance(value, (list, tuple, set)):
        return f"{len(value)} item(s)"
    if isinstance(value, dict):
        return f"{len(value)} field(s)"
    return str(value)


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _refresh_database_caches() -> None:
    st.session_state["refresh_token"] += 1
    cached_processing_ledger.clear()
    cached_config_state.clear()
    cached_lineage_records.clear()
    cached_ledger_stage_map.clear()
    st.session_state["cache_warm_key"] = None
def _render_participant_flow(ledger: pd.DataFrame, stage_map: list[dict]) -> None:
    for _, row in ledger.iterrows():
        status = html.escape(str(row.get("ledger_status", "empty")))
        reason = html.escape(str(row.get("ledger_reason", "")))
        participant = html.escape(str(row["participant"]))
        lanes = "".join(_modality_lane(row, modality) for modality in stage_map)
        st.markdown(
            (
                f'<section class="participant-flow participant-flow--{status}">'
                '<div class="participant-flow__header"><div>'
                '<div class="participant-flow__label">Participant</div>'
                f'<div class="participant-flow__title">{participant}</div>'
                '</div>'
                f'<div class="participant-flow__state participant-flow__state--{status}">{status.title()}</div>'
                '</div>'
                f'<div class="participant-flow__reason">{reason}</div>'
                f'<div class="participant-flow__lanes-scroll"><div class="modality-lanes">{lanes}</div></div>'
                '</section>'
            ),
            unsafe_allow_html=True,
        )


def _modality_lane(row: pd.Series, modality: dict) -> str:
    stages = modality["stages"]
    analysis_stage = _analysis_stage(modality)
    stage_html = "".join(_stage_chip(stage["label"], _count(row, stage["column"])) for stage in stages)
    stage_html += _analysis_chip(row, stages[0]["column"], analysis_stage["column"])
    lane_status = html.escape(_lane_status(row, stages[0]["column"], analysis_stage["column"]))
    label = html.escape(str(modality["label"]))
    return (
        f'<div class="modality-lane modality-lane--{lane_status}">'
        f'<div class="modality-lane__title">{label}</div>'
        f'<div class="stage-stack">{stage_html}</div>'
        '</div>'
    )


def _stage_chip(label: str, count: int) -> str:
    state = "complete" if count > 0 else "empty"
    safe_label = html.escape(str(label))
    return (
        f'<div class="stage-chip stage-chip--{state}">'
        f'<span class="stage-chip__name">{safe_label}</span>'
        f'<span class="stage-chip__value">{count}</span>'
        '</div>'
    )


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
    return (
        f'<div class="stage-chip stage-chip--{state}">'
        '<span class="stage-chip__name">Analysis</span>'
        f'<span class="stage-chip__value">{value}</span>'
        '</div>'
    )


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
    if value is None or (isinstance(value, float) and math.isnan(value)):
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
            if st.button(label, key=f"modality_{modality}", type=button_type, width="stretch"):
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
    _render_dataframe(display, width="stretch", hide_index=True)


def _render_stat_row(stats: list[tuple[str, int, str]]) -> None:
    if not stats:
        return
    columns = st.columns(len(stats))
    for column, (label, value, tone) in zip(columns, stats):
        with column:
            st.metric(label, value)
            if tone == "attention" and value:
                st.caption("Needs attention")

def _empty_state(message: str) -> None:
    st.markdown(f"<div class='empty-state'>{message}</div>", unsafe_allow_html=True)


def _truncate_path(path: str, max_chars: int = 72) -> str:
    if len(path) <= max_chars:
        return path
    return "..." + path[-(max_chars - 3):]


def _sentence_config_name(name: str) -> str:
    return name.replace(" Config", " config")


def _render_dataframe(data, **kwargs) -> None:
    st.dataframe(_arrow_safe_dataframe(data), **kwargs)


def _arrow_safe_dataframe(data):
    import pandas as pd

    if not isinstance(data, pd.DataFrame):
        return data
    display = data.copy()
    for column in display.columns:
        if display[column].dtype == "object":
            display[column] = display[column].map(_display_cell_value)
    return display


def _display_cell_value(value) -> str:
    import pandas as pd

    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return _compact_value(value)

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
            background: var(--canvas);
            border-right: 1px solid var(--hairline);
            box-shadow: none;
            padding-top: 2.6rem;
        }

        [data-testid="stSidebar"] > div:first-child {
            padding: 1.35rem 1rem 1rem 1rem;
        }

        .drawer-card {
            background: var(--surface);
            border: 1px solid var(--hairline);
            border-radius: 9px;
            box-shadow: var(--shadow-1);
            margin: 0 0 1.05rem 0;
            padding: 1.1rem 1rem 1rem 1rem;
        }

        .drawer-title {
            color: var(--ink);
            font-size: 1rem;
            font-weight: 650;
            line-height: 1.2;
            margin: 0 0 0.25rem 0;
        }

        .drawer-subtitle,
        [data-testid="stCaptionContainer"] {
            color: var(--ink-secondary);
            font-size: 0.86rem;
            font-weight: 450;
            line-height: 1.25;
        }

        .drawer-label {
            color: var(--ink-secondary);
            font-size: 0.76rem;
            font-weight: 650;
            letter-spacing: 0;
            margin: 0 0 0.35rem 0.1rem;
            text-transform: uppercase;
        }

        .drawer-nav {
            margin-top: 1.25rem;
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
            align-items: center;
            background: transparent;
            border: 1px solid transparent;
            border-radius: 7px;
            box-shadow: none;
            color: var(--ink);
            font-size: 0.91rem;
            font-weight: 600;
            justify-content: flex-start;
            min-height: 2.36rem;
            padding: 0.45rem 0.7rem;
            text-align: left;
        }

        [data-testid="stSidebar"] .stButton > button:hover {
            background: #EEF4FF;
            border-color: transparent;
            color: #194F9A;
        }

        [data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"] {
            background: #D6E7FF;
            border-color: transparent;
            color: #194F9A;
        }

        [data-testid="stSidebar"] .stButton > button span[data-testid="stIconMaterial"] {
            color: currentColor;
            font-size: 1.05rem;
            margin-right: 0.2rem;
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

        [data-testid="stSidebar"] [data-testid="stSegmentedControl"] {
            margin-bottom: 1.15rem;
        }

        [data-testid="stSidebar"] [data-testid="stSegmentedControl"] div[role="radiogroup"] {
            background: var(--surface);
            border: 1px solid var(--hairline);
            border-radius: 7px;
            box-shadow: none;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0;
            padding: 0;
            width: 100%;
        }

        [data-testid="stSidebar"] [data-testid="stSegmentedControl"] label {
            border-radius: 6px;
            color: var(--ink-secondary);
            font-size: 0.88rem;
            font-weight: 650;
            justify-content: center;
            min-height: 2.1rem;
            padding: 0.35rem 0.7rem;
        }

        [data-testid="stSidebar"] [data-testid="stSegmentedControl"] label:has(input:checked) {
            background: #D6E7FF;
            color: #194F9A;
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

        .participant-flow__lanes-scroll {
            max-width: 100%;
            overflow-x: auto;
            overflow-y: hidden;
            padding-bottom: 0.35rem;
        }

        .participant-flow__lanes-scroll::-webkit-scrollbar {
            height: 0.5rem;
        }

        .participant-flow__lanes-scroll::-webkit-scrollbar-thumb {
            background: #D1D1D6;
            border-radius: 999px;
        }

        .modality-lanes {
            display: grid;
            gap: 0.75rem;
            grid-template-columns: repeat(5, minmax(175px, 1fr));
            min-width: 960px;
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


        @media (max-width: 760px) {
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
