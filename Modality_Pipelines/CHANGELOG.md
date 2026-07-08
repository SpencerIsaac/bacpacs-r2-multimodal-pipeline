# BACPACS Pipeline Changelog

This file is the project-level changelog for pipeline infrastructure changes. Per-file headers may exist for older modules, but this file is the source of truth for repo-level history.

## 2026-07-08

- Added backend R1/R2 study namespace routing.
- Renamed the R2 SciDB table namespace to `r2_scidb_tables.py` and added parallel R1 table definitions in `r1_scidb_tables.py`.
- Added `study_config.py` for study-specific participant prefixes, visit maps, modality maps, subject-data roots, filename patterns, and database paths.
- Added study-aware table routing through `table_registry.py`.
- Updated manifest validation and raw-file registration so R1 and R2 use the same backend flow with different study configs and table namespaces.
- Added `run_modality_processing(...)` as the common first-pass processing dispatcher.
- Added GUI study selection and study-aware control-panel visibility on `control-panel-ledger-ui`.
- Added runtime downstream analysis discovery through `analysis_registry.py` and `analysis_registry.json`.
- Added `ANALYSIS_REGISTRY.md` documenting how future analyses such as Delsys coactivation should plug into the processed-table analysis layer.
- Added tests/smoke coverage for backend study routing, control-panel study selection, and runtime analysis registry resolution.

## 2026-07-07

- Added early control-panel scaffolding for ledger-style visibility across participants, modalities, and processing stages.
- Added control-panel config and service modules for reading study/pipeline state.
- Added Xsens single-file loading and processing integration work.

## 2026-07-06

- Added centralized SciStack stage execution helpers through `scistack_runner.py`.
- Added first-pass processing wrappers for Delsys, Xsens, GAITRite, and Cosmed.
- Added Cosmed processing scaffold.
- Added Python GAITRite loader integration and GAITRite processing scaffolding.
- Deprecated the unused `ProcessingLog` table concept.
- Updated project documentation around raw-file registration and processing flow.

## 2026-07-02

- Split SOP filename keys from SciDB analysis schema keys.
- Added modality-specific RawFile table definitions.
- Added AFO raw/processed table scaffolds.
- Updated shared R2 config vocabulary and path metadata.

## 2026-07-01

- Added the initial R2 multimodal pipeline scaffold.
- Moved shared configuration and SciDB table definitions under `Modality_Pipelines/common`.
- Added early modality folders and config structure.
