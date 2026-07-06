"""
SciStack wrappers for Delsys processing stages.

@author shensley01
@version 0.2.0
@last_updated 2026-07-06
@change_log
    - 2026-07-06 v0.2.0: Routed Delsys stage through shared SciStack runner
      with schema_filter/schema_level, track_lineage=True, and skip_computed=True.
    - 2026-07-02 v0.1.0: Added Delsys SciDB for_each wrapper scaffold.
"""

from __future__ import annotations

from Modality_Pipelines.common.scidb_tables import DelsysProcessed, DelsysRawFile
from Modality_Pipelines.common.scistack_runner import run_scistack_stage
from Modality_Pipelines.Delsys_Pipeline.process_delsys import process_delsys_raw_file


def run_delsys_processing(**schema_filters):
    """Run Delsys raw-file processing through SciDB-owned looping."""
    return run_scistack_stage(
        process_delsys_raw_file,
        inputs={
            "raw_file_record": DelsysRawFile,
        },
        outputs=[
            DelsysProcessed,
        ],
        schema_filters=schema_filters,
    )
