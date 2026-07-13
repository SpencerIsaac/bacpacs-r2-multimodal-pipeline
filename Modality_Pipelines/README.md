# BACPACS modality pipelines

[![tests](https://github.com/SpencerIsaac/bacpacs-r2-multimodal-pipeline/actions/workflows/tests.yml/badge.svg)](https://github.com/SpencerIsaac/bacpacs-r2-multimodal-pipeline/actions/workflows/tests.yml)

@author shensley01
@version 0.7.0
@last_updated 2026-07-13

This folder contains the BACPACS multimodal ambulation pipeline backend. The current backend supports BACPACS R1 Smart AFO and BACPACS R2 Spinal Stim through one shared processing flow, one shared DuckDB database, and separate study-specific table namespaces.

The SOP-level filename pattern is:

```text
{study}_{participant_number}_{visit}_{modality}_{outcome}
```

Resolved runtime patterns are:

```text
R1_{participant_number}_{visit}_{modality}_{outcome}
R2_{participant_number}_{visit}_{modality}_{outcome}
```

Downstream SciDB tables use the shared schema keys: `participant_number`, `visit`, `test`, `condition`, `speed`, `trial`, and `cycle`.

## Documentation

The MkDocs documentation is the repo-readable mirror of the SOP:

```text
docs/
mkdocs.yml
docs/source_of_truth.json
scripts/check_docs_freshness.py
```

The SOP is the human source of truth. The executable config is the machine source of truth. Run the docs freshness check after changing study config, CLI commands, table names, folder names, or analysis registry behavior.

```powershell
python scripts\check_docs_freshness.py
```

## Shared database

Both R1 and R2 use:

```text
Y:\BACPACS R2 - Spinal Stim\Pipeline_development\r2_pipeline.duckdb
```

Study separation is handled by table namespaces rather than separate database files.

## Configuration layout

Use these files for canonical pipeline behavior:

```text
Modality_Pipelines/config.json
Modality_Pipelines/common/study_config.py
Modality_Pipelines/common/table_registry.py
Modality_Pipelines/common/lightweight_registry.py
Modality_Pipelines/common/analysis_registry.json
```

`config.json` contains base vocabulary and R2 defaults. `study_config.py` resolves selected-study values for R1 and R2. Do not duplicate visit codes, modality codes, folder names, or file naming patterns inside modality-specific scripts.

## Current flow

```text
filesystem -> validation -> RawFile tables -> first-pass processors -> processed tables -> analysis registry -> analysis tables
```

Raw files enter the system only through validation, registration, and first-pass modality processing. Downstream analyses read processed tables only.

## CLI and GUI

The CLI and GUI call the same backend API.

```powershell
.\bacpacs.cmd doctor
.\bacpacs.cmd validate --study R2
.\bacpacs.cmd register --study R2 --dry-run
.\bacpacs.cmd process --study R2 --modality all
.\bacpacs.cmd analyses --study R2
.\bacpacs.cmd gui
```

## Modality folders

Use modality folders for acquisition-system-specific processing and parsing logic:

```text
Cosmed_Pipeline/
Delsys_Pipeline/
GAITRite_Pipeline/
Xsens_Pipeline/
```

Future modality-specific analysis methods should live under the relevant modality folder, for example:

```text
Delsys_Pipeline/analyses/coactivation.py
```

Then register the output table in the study-specific table file and register the analysis in `common/analysis_registry.json`.

