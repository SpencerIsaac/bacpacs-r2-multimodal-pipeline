# Adding analysis methods

Researchers may add downstream analysis methods after first-pass modality processing is complete. The fixed multimodal table layer in `Modality_Pipelines/common/downstream_analysis.py` owns `TrialAnalysis`, `CycleUnmatched`, `VisitSummary`, `CycleMatched`, and `AnalysisIssue`. Registry-defined methods are for additional analyses beyond that core table layer. Examples include Delsys coactivation, Xsens gait-event detection, GAITRite variability metrics, or cross-modal symmetry measures.

Analysis methods should be added through the pipeline registry rather than run as disconnected scripts. This allows the CLI and GUI to discover the method, run it in batch, write results to the correct study table, and preserve provenance through the database.

## Developer workflow

```text
New analysis method workflow

1. Write analysis code
   modality-specific folder
   example:
   Modality_Pipelines/Delsys_Pipeline/analyses/coactivation.py

        |
        v

2. Add database output table
   study-specific SciDB table file
   examples:
   Modality_Pipelines/common/r1_scidb_tables.py
   Modality_Pipelines/common/r2_scidb_tables.py

        |
        v

3. Register analysis with CLI and GUI
   runtime analysis registry
   file:
   Modality_Pipelines/common/analysis_registry.json

        |
        v

4. Test discovery and dry run
   .\bacpacs.cmd analyses --study R2
   .\bacpacs.cmd analyze --study R2 --analysis coactivation --dry-run

        |
        v

5. Run analysis
   .\bacpacs.cmd analyze --study R2 --analysis coactivation
```

## Step 1. Add the analysis code

Place the Python analysis file in the folder for the modality it analyzes.

```text
Modality_Pipelines/Delsys_Pipeline/analyses/coactivation.py
```

The function should operate on processed records, not raw files.

```python
def run_analysis(processed_record, config=None):
    return {
        "coactivation_index": value,
        "muscle_pair": muscle_pair,
        "method": "overlap_index",
        "window": window,
    }
```

## Step 2. Add the output table

Add the output table class to the study-specific SciDB table file.

```text
Modality_Pipelines/common/r1_scidb_tables.py
Modality_Pipelines/common/r2_scidb_tables.py
```

The output table defines where the analysis results will be saved.

## Step 3. Register the analysis

Add one entry to:

```text
Modality_Pipelines/common/analysis_registry.json
```

Example:

```json
{
  "analyses": {
    "coactivation": {
      "modality": "delsys",
      "input_stage": "processed",
      "output_table": {
        "R1": "R1DelsysCoactivation",
        "R2": "DelsysCoactivation"
      },
      "module": "Modality_Pipelines.Delsys_Pipeline.analyses.coactivation",
      "function": "run_analysis",
      "input_name": "processed_record",
      "batch_enabled": true,
      "description": "Delsys muscle coactivation metrics from processed EMG."
    }
  }
}
```

## Step 4. Confirm discovery

```powershell
.\bacpacs.cmd analyses --study R2
.\bacpacs.cmd analyze --study R2 --analysis coactivation --dry-run
```

## Step 5. Run the analysis

```powershell
.\bacpacs.cmd analyze --study R2 --analysis coactivation
```

## Rule

Analysis processors must read from processed tables only. If a method opens raw acquisition files directly, it belongs in first-pass modality processing, not downstream analysis processing.

## Fixed multimodal table layer

Do not register `TrialAnalysis`, `CycleUnmatched`, `VisitSummary`, `CycleMatched`, or `AnalysisIssue` in `analysis_registry.json`. Those tables are built by the guarded `bacpacs analyze build-*` commands and have dependency rules documented in the downstream analysis guide.

Use the registry workflow on this page for optional future analyses that consume processed tables or derived downstream tables and produce a separate output table.