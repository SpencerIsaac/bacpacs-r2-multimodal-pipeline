# R2 Control Panel

This package contains the local control panel for the R2 SciStack pipeline.

Run from `Pipeline_development`:

```powershell
& ".\BACPACS_env\python.exe" -m streamlit run Modality_Pipelines\control_panel\app.py
```

The home screen is the Processing Ledger. It reads the SciDB/DuckDB metadata
tables directly and shows, per participant, which RawFile and Processed records
exist right now.

Batch processing API used by the UI:

```python
from Modality_Pipelines.control_panel.pipeline_api import run_modality_processing

run_modality_processing("delsys", participant_number="000", visit="BL")
run_modality_processing("xsens")
run_modality_processing("gaitrite")
```

Direct single-file debugging API:

```python
from Modality_Pipelines.control_panel.pipeline_api import process_single_raw_file

result = process_single_raw_file("delsys", r"Y:\path\to\file.mat")
```

Single-file processing returns a local preview only. It does not write to SciDB.

