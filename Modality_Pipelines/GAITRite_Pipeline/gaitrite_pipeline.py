"""
SciStack wrappers for GAITRite processing stages.

@author shensley01
@version 0.2.0
@last_updated 2026-07-06
@change_log
    - 2026-07-06 v0.2.0: Routed GAITRite stages through shared SciStack runner
      with schema_filter/schema_level, track_lineage=True, and skip_computed=True.
    - 2026-07-06 v0.1.0: Added GAITRite RawFile -> GAITRiteLoaded and
      GAITRiteLoaded -> GAITRiteCycle SciDB for_each wrappers.
"""

from __future__ import annotations

from Modality_Pipelines.common.table_registry import get_processed_tables, get_raw_file_table
from Modality_Pipelines.common.scistack_runner import run_scistack_stage, split_stage_kwargs
from Modality_Pipelines.GAITRite_Pipeline.load_gaitrite import (
    distribute_gaitrite_loaded,
    process_gaitrite_raw_file,
)


def run_gaitrite_loading(**schema_filters):
    """Load registered GAITRite raw files through SciDB-owned looping."""
    study = schema_filters.pop("study", "R2")
    schema_filters, stage_options = split_stage_kwargs(schema_filters)
    gaitrite_loaded = get_processed_tables(study, "gaitrite")[0]
    return run_scistack_stage(
        process_gaitrite_raw_file,
        inputs={
            "raw_file_record": get_raw_file_table(study, "gaitrite"),
        },
        outputs=[
            gaitrite_loaded,
        ],
        schema_filters=schema_filters,
        study=study,
        **stage_options,
    )


def run_gaitrite_cycle_distribution(**schema_filters):
    """Split loaded GAITRite trial rows into GAITRite row/cycle records."""
    study = schema_filters.pop("study", "R2")
    schema_filters, stage_options = split_stage_kwargs(schema_filters)
    gaitrite_loaded, gaitrite_cycle = get_processed_tables(study, "gaitrite")
    return run_scistack_stage(
        distribute_gaitrite_loaded,
        inputs={
            "gaitrite_loaded": gaitrite_loaded,
        },
        outputs=[
            gaitrite_cycle,
        ],
        schema_filters=schema_filters,
        study=study,
        **stage_options,
    )
