# BACPACS data pipeline

The BACPACS data pipeline organizes, validates, registers, processes, and reviews multimodal ambulation data for the BACPACS R1 Smart AFO and BACPACS R2 Spinal Stim studies.

This documentation mirrors the current BACPACS pipeline SOP and the executable pipeline configuration. If this site conflicts with the approved SOP, the SOP is authoritative unless the discrepancy log identifies an intentional implementation change awaiting SOP revision.

## What this system does

- Validates raw-file names and folder locations against study-specific rules.
- Registers valid primary raw files as RawFile records in SciStack/SciDB tables.
- Runs first-pass modality processing from registered RawFile records into processed tables.
- Runs downstream analysis processors from processed tables into analysis tables.
- Provides both a CLI and Streamlit control panel that call the same backend API.
- Keeps R1 and R2 data in one shared DuckDB database with separate table namespaces.

## Current shared database

```text
Y:\BACPACS R2 - Spinal Stim\Pipeline_development\r2_pipeline.duckdb
```

R1 and R2 share this database. Study separation is handled by configuration and table namespaces, not by separate database files.

## Main entry points

```powershell
.\bacpacs.cmd --help
.\bacpacs.cmd doctor
.\bacpacs.cmd gui
.\bacpacs.cmd validate --study R2
.\bacpacs.cmd register --study R2 --dry-run
.\bacpacs.cmd process --study R2 --modality all
.\bacpacs.cmd status --study R2
```

Replace `R2` with `R1` when operating on R1 data.

## Documentation contract

- SOP: human source of truth.
- `Modality_Pipelines/config.json`: base pipeline vocabulary and R2 defaults.
- `Modality_Pipelines/common/study_config.py`: study-specific R1/R2 overlays.
- `Modality_Pipelines/common/table_registry.py`: runtime table routing.
- `Modality_Pipelines/common/analysis_registry.json`: downstream analysis discovery.
- `docs/source_of_truth.json`: documentation freshness metadata.
- `scripts/check_docs_freshness.py`: automated drift check.
