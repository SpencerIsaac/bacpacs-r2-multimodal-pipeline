"""SciStack wrappers for Delsys processing stages."""

from __future__ import annotations

import sys

from Modality_Pipelines.common.manifest import register_raw_files
from Modality_Pipelines.common.scistack_runner import run_scistack_stage, split_stage_kwargs
from Modality_Pipelines.common.table_registry import get_processed_tables, get_raw_file_table
from Modality_Pipelines.Delsys_Pipeline.process_delsys import process_delsys_raw_file


def run_delsys_processing(**schema_filters):
    """Run Delsys raw-file processing through SciDB-owned looping."""
    study = schema_filters.pop("study", "R2")
    schema_filters, stage_options = split_stage_kwargs(schema_filters)
    return run_scistack_stage(
        process_delsys_raw_file,
        inputs={"raw_file_record": get_raw_file_table(study, "delsys")},
        outputs=get_processed_tables(study, "delsys"),
        schema_filters=schema_filters,
        study=study,
        **stage_options,
    )


def main():
    """Register valid Delsys files and run Delsys processing with R2 defaults."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    counts = register_raw_files(modality_keys=["delsys"], study="R2")
    print(f"Delsys raw-file registration: {counts}")
    return run_delsys_processing(study="R2")


if __name__ == "__main__":
    main()
