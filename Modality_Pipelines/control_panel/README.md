# BACPACS control panel

This package contains the local Streamlit control panel for the BACPACS SciStack pipeline.

Run from `Pipeline_development`:

```powershell
.\bacpacs.cmd gui
```

The control panel is a visual control layer over the same backend API used by the CLI. It does not own separate processing logic.

## Pages

| Page | Purpose |
| --- | --- |
| Pipeline workflow | Mirrors CLI actions for setup check, validation, registration, processing, analysis, and status. |
| Processing ledger | Shows participant/modality RawFile and processed-table counts. |
| Raw file review | Scans files and reviews validation/registration readiness. |
| Configuration | Shows selected study config and processing config state. |
| Lineage / records | Shows SciStack/SciDB lineage and record metadata. |

Write actions require explicit confirmation. Preview and dry-run actions are read-only.

## Backend contract

The GUI calls backend functions such as:

```python
validate_study_files(...)
register_raw_files(...)
run_modality_processing(...)
list_available_analyses(...)
run_registered_analysis(...)
```

CLI and GUI behavior should stay synchronized. Update `docs/user-guide/gui-control-panel.md` and rerun `scripts/check_docs_freshness.py` when this surface changes.
