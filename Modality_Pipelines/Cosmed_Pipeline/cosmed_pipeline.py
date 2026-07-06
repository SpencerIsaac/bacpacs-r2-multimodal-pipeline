"""
SciStack wrappers for COSMED processing stages.

@author shensley01
@version 0.2.0
@last_updated 2026-07-06
@change_log
    - 2026-07-06 v0.2.0: Routed COSMED stage through shared SciStack runner
      with schema_filter/schema_level, track_lineage=True, and skip_computed=True.
    - 2026-07-06 v0.1.0: Added COSMED RawFile -> CosmedProcessed SciDB
      for_each wrapper.
"""

from __future__ import annotations

from Modality_Pipelines.common.scidb_tables import CosmedProcessed, CosmedRawFile
from Modality_Pipelines.common.scistack_runner import run_scistack_stage
from Modality_Pipelines.Cosmed_Pipeline.process_cosmed import process_cosmed_raw_file


def run_cosmed_processing(**schema_filters):
    """Load registered COSMED raw files through SciDB-owned looping."""
    return run_scistack_stage(
        process_cosmed_raw_file,
        inputs={
            "raw_file_record": CosmedRawFile,
        },
        outputs=[
            CosmedProcessed,
        ],
        schema_filters=schema_filters,
    )
