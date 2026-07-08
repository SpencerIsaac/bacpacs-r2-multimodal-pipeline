# Runtime Analysis Registry

Downstream analysis stages are discovered from `Modality_Pipelines/common/analysis_registry.json`.
The CLI should read this registry instead of hardcoding every analysis command.

A new batch analysis needs three pieces:

1. A Python analysis function that operates on processed records.
2. A study-specific output table class in `r1_scidb_tables.py` and/or `r2_scidb_tables.py`.
3. One registry entry in `analysis_registry.json`.

Example registry entry:

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

The function should accept the configured input name as a keyword argument:

```python
def run_analysis(processed_record, config=None):
    ...
```

The backend entry point for CLI integration is:

```python
from Modality_Pipelines.common.analysis_registry import (
    list_available_analyses,
    run_registered_analysis,
)

list_available_analyses(study="R2")
run_registered_analysis(study="R2", analysis="coactivation", participant_number="001")
```

Analyses consume processed tables, not raw files. Raw files should only enter the system through registration and first-pass modality processing.
