"""SciStack wrappers for Xsens processing stages."""

from __future__ import annotations

import sys

from Modality_Pipelines.common.manifest import register_raw_files
from Modality_Pipelines.common.scistack_runner import run_scistack_stage, split_stage_kwargs
from Modality_Pipelines.common.table_registry import get_processed_tables, get_raw_file_table
from Modality_Pipelines.Xsens_Pipeline.process_xsens import process_xsens_raw_file


def run_xsens_processing(**schema_filters):
    """Run Xsens raw-file processing through SciDB-owned looping."""
    study = schema_filters.pop("study", "R2")
    schema_filters, stage_options = split_stage_kwargs(schema_filters)
    return run_scistack_stage(
        process_xsens_raw_file,
        inputs={"raw_file_record": get_raw_file_table(study, "xsens")},
        outputs=get_processed_tables(study, "xsens"),
        schema_filters=schema_filters,
        study=study,
        **stage_options,
    )


def main():
    """Register valid Xsens files and run Xsens processing with R2 defaults."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    counts = register_raw_files(modality_keys=["xsens"], study="R2")
    print(f"Xsens raw-file registration: {counts}")
    return run_xsens_processing(study="R2")


if __name__ == "__main__":
    main()
