# Architecture

The BACPACS pipeline is organized as a shared backend engine with two front doors: the CLI and the Streamlit GUI. Both call the same backend functions.

## One-page architecture diagram

```text
BACPACS pipeline architecture

                       Shared study configuration
              Modality_Pipelines/config.json
              Modality_Pipelines/common/study_config.py
                                |
                                v
+-------------------+     +-------------------+     +-------------------+
| R1 subject data   |     | CLI / control UI   |     | R2 subject data   |
| folders           |     | bacpacs.cmd        |     | folders           |
+-------------------+     +-------------------+     +-------------------+
          |                         |                         |
          |                         v                         |
          |             validate / register / process          |
          |                         |                         |
          +-------------------------+-------------------------+
                                    |
                                    v
                         RawFile registration
                 Modality_Pipelines/common/manifest.py
                                    |
                                    v
+-----------------------------------------------------------------------+
| Shared database                                                       |
| Y:\BACPACS R2 - Spinal Stim\Pipeline_development\r2_pipeline.duckdb    |
|                                                                       |
| R1 table namespace                  R2 table namespace                 |
| ------------------                  ------------------                 |
| R1DelsysRawFile                     DelsysRawFile                      |
| R1XsensRawFile                      XsensRawFile                       |
| R1GAITRiteRawFile                   GAITRiteRawFile                    |
| R1DelsysProcessed                   DelsysProcessed                    |
| R1XsensProcessed                    XsensProcessed                     |
| R1GAITRiteCycle                     GAITRiteCycle                      |
+-----------------------------------------------------------------------+
                                    |
                                    v
                         First-pass processors
              raw-file record -> modality processor -> processed table

        +-----------------------------+-----------------------------+
        |                             |                             |
        v                             v                             v
Modality_Pipelines/          Modality_Pipelines/          Modality_Pipelines/
Delsys_Pipeline/             Xsens_Pipeline/              GAITRite_Pipeline/
process_delsys.py            process_xsens.py             load_gaitrite.py
analyses/                    analyses/                    analyses/

                                    |
                                    v
                         Runtime analysis registry
          Modality_Pipelines/common/analysis_registry.json
                                    |
                                    v
                         Analysis processors
              processed table -> analysis function -> analysis table
```

## Key design choices

| Decision | Current implementation |
| --- | --- |
| Database layout | One shared DuckDB database. |
| Active database | `Y:\BACPACS R2 - Spinal Stim\Pipeline_development\r2_pipeline.duckdb` |
| Study separation | R1 and R2 table namespaces in the same database. |
| Study selection | `--study R1` or `--study R2` in CLI; R1/R2 selector in GUI. |
| Raw file entry | Only validation, registration, and first-pass processing touch raw files. |
| Analysis entry | Fixed downstream stages read processed tables and write derived analysis tables; optional registry analyses read processed tables only. |
| Extension path | Add modality code, output table, and registry entry instead of editing CLI internals. |

## Backend API shape

```python
validate_study_files(study="R2", ...)
register_raw_files(study="R2", dry_run=False, ...)
run_modality_processing(study="R2", modality="all", ...)
list_available_analyses(study="R2")
run_registered_analysis(study="R2", analysis="coactivation", ...)
```

## Downstream analysis API shape

```python
build_trial_analysis(study="R2", ...)
build_cycle_unmatched(study="R2", ...)
finalize_visit_summary(study="R2", ...)
normalize_cycles_to_visit(study="R2", ...)
build_cycle_matched(study="R2", ...)
export_analysis_tables(study="R2", ...)
build_all(study="R2", ...)
```

The downstream layer uses exact table names from the R1/R2 SciDB table modules. It does not infer study prefixes.