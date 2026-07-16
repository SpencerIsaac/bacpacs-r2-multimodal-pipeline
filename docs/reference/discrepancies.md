# Discrepancy log

Use this page to record places where the SOP, code, docs, or implementation status do not fully agree yet.

| Area | Current observation | Action |
| --- | --- | --- |
| SOP PDF extraction | The attached SOP PDF is treated as the human source of truth, but text extraction was not available in the project environment without adding a PDF dependency. | Keep this page updated manually during SOP review; avoid installing PDF-only tooling into the pipeline env. |
| `config.json` filename pattern | `Modality_Pipelines/config.json` stores the R2 default pattern `R2_{participant_number}_{visit}_{modality}_{outcome}`. | This is intentional. Runtime study selection resolves R1/R2 patterns through `study_config.py`. |
| `config.json` metadata description | The base config still describes the R2 pipeline. | Acceptable while `study_config.py` overlays R1; update if/when config becomes a fully generic study-suite config. |
| Analysis registry | No downstream analyses are currently registered in `analysis_registry.json`. | The registry structure exists and should be populated when the first analysis method, such as coactivation, is ready. |
| AFO processing | AFO has table/config scaffolding, but first-pass processing maturity should be verified before production use. | Confirm processor status before listing AFO as fully runnable. |
| Cosmed processing | Cosmed has table/config scaffolding and a processor module, but production readiness should be verified with representative files. | Confirm processor status before listing Cosmed as fully runnable. |
| GAITRite second stage | The pipeline currently includes `GAITRiteLoaded` and `GAITRiteCycle`. | SOP should define whether the canonical second stage is footfall-row data, gait-cycle data, or both. |

A discrepancy is not automatically a bug. It is a tracked decision point that must be resolved before production release.
