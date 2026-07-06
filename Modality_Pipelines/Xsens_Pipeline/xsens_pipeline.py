"""
SciStack wrappers for Xsens processing stages.

@author shensley01
@version 0.2.0
@last_updated 2026-07-06
@change_log
    - 2026-07-06 v0.2.0: Routed Xsens stage through shared SciStack runner
      with schema_filter/schema_level, track_lineage=True, and skip_computed=True.
    - 2026-07-02 v0.1.0: Added Xsens SciDB for_each wrapper scaffold.
"""

from __future__ import annotations

from Modality_Pipelines.common.scidb_tables import XsensProcessed, XsensRawFile
from Modality_Pipelines.common.scistack_runner import run_scistack_stage, split_stage_kwargs
from Modality_Pipelines.Xsens_Pipeline.process_xsens import process_xsens_raw_file


def run_xsens_processing(**schema_filters):
    """Run Xsens raw-file processing through SciDB-owned looping."""
    schema_filters, stage_options = split_stage_kwargs(schema_filters)
    return run_scistack_stage(
        process_xsens_raw_file,
        inputs={
            "raw_file_record": XsensRawFile,
        },
        outputs=[
            XsensProcessed,
        ],
        schema_filters=schema_filters,
    )
