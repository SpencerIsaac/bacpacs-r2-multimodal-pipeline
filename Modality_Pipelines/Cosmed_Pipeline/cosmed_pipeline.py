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

from Modality_Pipelines.common.table_registry import get_processed_tables, get_raw_file_table
from Modality_Pipelines.common.scistack_runner import run_scistack_stage, split_stage_kwargs
from Modality_Pipelines.Cosmed_Pipeline.process_cosmed import process_cosmed_raw_file


def run_cosmed_processing(**schema_filters):
    """Load registered COSMED raw files through SciDB-owned looping."""
    study = schema_filters.pop("study", "R2")
    schema_filters, stage_options = split_stage_kwargs(schema_filters)
    return run_scistack_stage(
        process_cosmed_raw_file,
        inputs={
            "raw_file_record": get_raw_file_table(study, "cosmed"),
        },
        outputs=get_processed_tables(study, "cosmed"),
        schema_filters=schema_filters,
        study=study,
        **stage_options,
    )
