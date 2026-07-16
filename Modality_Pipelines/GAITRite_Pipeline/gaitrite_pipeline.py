"""SciStack wrappers for GAITRite processing stages."""

from __future__ import annotations

import sys

from Modality_Pipelines.common.manifest import register_raw_files
from Modality_Pipelines.common.scistack_runner import run_scistack_stage, split_stage_kwargs
from Modality_Pipelines.common.table_registry import get_processed_tables, get_raw_file_table
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
        inputs={"raw_file_record": get_raw_file_table(study, "gaitrite")},
        outputs=[gaitrite_loaded],
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
        inputs={"gaitrite_loaded": gaitrite_loaded},
        outputs=[gaitrite_cycle],
        schema_filters=schema_filters,
        study=study,
        **stage_options,
    )


def run_gaitrite_processing(**schema_filters):
    """Run the full GAITRite first-pass path."""
    loaded_result = run_gaitrite_loading(**schema_filters)
    cycle_result = run_gaitrite_cycle_distribution(**schema_filters)
    return {"loaded": loaded_result, "cycle": cycle_result}


def run_gaitrite_pipeline(**schema_filters):
    """Backward-compatible alias for run_gaitrite_processing."""
    return run_gaitrite_processing(**schema_filters)


def main():
    """Register valid GAITRite files and run both GAITRite stages with R2 defaults."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    counts = register_raw_files(modality_keys=["gaitrite"], study="R2")
    print(f"GAITRite raw-file registration: {counts}")
    return run_gaitrite_processing(study="R2")


if __name__ == "__main__":
    main()
