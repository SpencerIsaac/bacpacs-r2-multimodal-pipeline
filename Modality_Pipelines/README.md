# BACPACS Modality Pipelines

[![tests](https://github.com/SpencerIsaac/bacpacs-r2-multimodal-pipeline/actions/workflows/tests.yml/badge.svg)](https://github.com/SpencerIsaac/bacpacs-r2-multimodal-pipeline/actions/workflows/tests.yml)

@author shensley01
@version 0.6.0
@last_updated 2026-07-08
@change_log
- 2026-07-08 v0.6.0: Added R1/R2 study namespace routing, GUI study selection, and runtime analysis registry for downstream processed-table analyses.
- 2026-07-07 v0.5.0: Added early control panel visibility layer for participant/modality processing state.
- 2026-07-06 v0.4.0: Added centralized SciStack stage execution, Xsens/Delsys/GAITRite/Cosmed processing wrappers, and backend manifest registration flow.
- 2026-07-06 v0.3.1: Deprecated the unused `ProcessingLog` artifact and aligned documented table classes with the current pipeline surface.
- 2026-07-02 v0.3.0: Documented separate file_name_keys and analysis schema_keys.
- 2026-07-01 v0.2.1: Clarified project path config keys: project_root, subject_data_root, pipeline_root, and database_path.
- 2026-07-01 v0.2.0: Updated documented hierarchy after moving shared SciDB tables into common and GAITRite scaffold files into GAITRite_Pipeline.
- 2026-07-01 v0.1.0: Added initial pipeline configuration structure and guidance.

This folder contains the BACPACS multimodal ambulation pipeline scaffolding. The current backend supports R2 Spinal Stim and has an R1 Smart AFO namespace ready for shared registration/processing flow. The pipeline is organized around the SOP file naming convention:

```text
R2_{participant_number}_{visit}_{modality}_{outcome}
```

Those four fields describe raw-file identity and discovery. They are stored as `file_name_keys`. Downstream SciDB tables use separate analysis `schema_keys`: `participant_number`, `visit`, `test`, `condition`, `speed`, `trial`, and `cycle`.

## Configuration Layout

Shared study vocabulary lives in the root `config.json` file. This includes explicit project paths (`project_root`, `subject_data_root`, `pipeline_root`, `database_path`), the file naming pattern, current schema keys, visit folder names/codes, modality folder names/codes, condition codes, and task/outcome codes.

Python code should access shared configuration through:

```text
common/common_config.py
```

Do not duplicate visit codes, modality codes, folder names, or file naming patterns inside modality-specific scripts.

## Shared Code

Use `common/` for code that is genuinely shared across modalities:

```text
common/common_config.py
common/r2_scidb_tables.py
```

`common_config.py` loads the shared JSON config and provides small path/name helpers.

`r1_scidb_tables.py` and `r2_scidb_tables.py` define study-specific SciDB table classes for modality-specific raw-file records and processed outputs, including `GAITRiteRawFile`, `XsensRawFile`, `DelsysRawFile`, `CosmedRawFile`, `AfoRawFile`, `GAITRiteLoaded`, `GAITRiteCycle`, `XsensProcessed`, `DelsysProcessed`, `CosmedProcessed`, and `AfoProcessed`.

## Modality-Specific Code

Use each modality folder for acquisition-system-specific logic. GAITRite files live in:

```text
GAITRite_Pipeline/
  gaitrite_columns.py
  gaitrite_scidb_scaffold.py
```

`gaitrite_columns.py` holds GAITRite export column definitions.

`gaitrite_scidb_scaffold.py` is a temporary scaffold for GAITRite raw-file discovery and early SciDB processing flow. It should eventually be split into manifest registration and real GAITRite preprocessing functions.

Use modality-specific config files only for facts that belong to one acquisition system or parser. Examples may include:

```text
GAITRite_Pipeline/gaitrite_config.json
Xsens_Pipeline/xsens_config.json
Delsys_Pipeline/delsys_config.json
```

Good candidates for modality-specific config:

```text
export column names
sheet names
verified file extensions
sampling rates, once confirmed
parser options
modality-specific QC thresholds
```

Do not put shared SOP vocabulary in modality-specific config files.

## Current Structure

```text
Pipeline_development/
  r2_pipeline.duckdb
  update_scistack.ps1
  GAITRite_processing-CH.py        # legacy/reference script, not current pipeline entry point
  Modality_Pipelines/
    README.md
    config.json
    common/
      common_config.py
      study_config.py
      table_registry.py
      analysis_registry.py
      r1_scidb_tables.py
      r2_scidb_tables.py
    GAITRite_Pipeline/
      gaitrite_columns.py
      gaitrite_scidb_scaffold.py
    docs/
      R2_SciStack_Manifest_Planning.docx
```

## Recommended Next Step

Build the manifest/registration layer before preprocessing. The first goal should be to find files that already exist, parse their SOP file names, validate that their folder location agrees with the file name, and register valid raw files in SciDB as modality-specific raw-file entries such as `GAITRiteRawFile`, `XsensRawFile`, `DelsysRawFile`, or `CosmedRawFile`.

Preprocessing should come after the manifest layer can answer:

```text
What files exist?
Which files match the SOP naming convention?
Which files are in the wrong folder?
Which participant/visit/modality/outcome combinations are ready to process?
```

