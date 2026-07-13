# Runtime analysis registry

Downstream analysis stages are discovered from:

```text
Modality_Pipelines/common/analysis_registry.json
```

The CLI and GUI read this registry instead of hardcoding every analysis command.

## Add an analysis in this order

```text
1. Write analysis code in a modality-specific folder
   example: Modality_Pipelines/Delsys_Pipeline/analyses/coactivation.py

2. Add a study-specific output table
   Modality_Pipelines/common/r1_scidb_tables.py
   Modality_Pipelines/common/r2_scidb_tables.py

3. Register the analysis in JSON
   Modality_Pipelines/common/analysis_registry.json

4. Test discovery and dry run
   .\bacpacs.cmd analyses --study R2
   .\bacpacs.cmd analyze --study R2 --analysis coactivation --dry-run
```

A batch analysis needs three pieces:

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

Backend entry points:

```python
from Modality_Pipelines.common.analysis_registry import (
    list_available_analyses,
    run_registered_analysis,
)

list_available_analyses(study="R2")
run_registered_analysis(study="R2", analysis="coactivation", participant_number="001")
```

Analyses consume processed tables, not raw files. Raw files should only enter the system through registration and first-pass modality processing.
