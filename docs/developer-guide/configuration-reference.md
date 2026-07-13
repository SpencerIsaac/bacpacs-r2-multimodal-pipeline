# Configuration reference

The pipeline has a small set of configuration files that should remain synchronized with the SOP, CLI, GUI, tests, and docs.

| File | Purpose |
| --- | --- |
| `Modality_Pipelines/config.json` | Base pipeline vocabulary and R2 defaults, including schema keys, visits, modalities, file codes, primary extensions, conditions, tasks, and shared database path. |
| `Modality_Pipelines/common/study_config.py` | Resolves R1/R2 study-specific configuration, including subject-data roots, participant prefixes, visit folders, filename patterns, and database path. |
| `Modality_Pipelines/common/table_registry.py` | Routes each study and modality to the correct RawFile and processed SciDB table classes. |
| `Modality_Pipelines/common/lightweight_registry.py` | Provides fast table-name metadata for startup, help, status, and control-panel routing. |
| `Modality_Pipelines/common/analysis_registry.json` | Lists downstream analysis processors discoverable by CLI and GUI. |
| `Modality_Pipelines/cli.py` | Defines CLI command syntax and dispatch to backend functions. |
| `Modality_Pipelines/control_panel/app.py` | Defines Streamlit GUI pages that mirror CLI/backend actions. |
| `docs/source_of_truth.json` | Records documentation freshness expectations and source files. |

## Study configuration

| Study | Project | Subject-data root | Participant prefix |
| --- | --- | --- | --- |
| R1 | BACPACS R1 Smart AFO | `Y:\BACPACS R1 - Smart AFO\Subject Data` | `R1` |
| R2 | BACPACS R2 Spinal Stim | `Y:\BACPACS R2 - Spinal Stim\Subject Data` | `R2` |

Both studies use:

```text
Y:\BACPACS R2 - Spinal Stim\Pipeline_development\r2_pipeline.duckdb
```

## Filename patterns

Resolved runtime patterns are:

```text
R1_{participant_number}_{visit}_{modality}_{outcome}
R2_{participant_number}_{visit}_{modality}_{outcome}
```

The SOP-level general pattern is:

```text
{study}_{participant_number}_{visit}_{modality}_{outcome}
```

