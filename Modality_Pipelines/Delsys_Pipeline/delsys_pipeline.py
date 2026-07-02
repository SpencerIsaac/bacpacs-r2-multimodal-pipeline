"""
SciStack wrappers for Delsys processing stages.

@author shensley01
@version 0.1.0
@last_updated 2026-07-02
@change_log
    - 2026-07-02 v0.1.0: Added Delsys SciDB for_each wrapper scaffold.
"""

from __future__ import annotations

import scidb

from Modality_Pipelines.common.common_config import SCHEMA_KEYS, configure_scistack_database
from Modality_Pipelines.common.scidb_tables import DelsysProcessed, DelsysRawFile
from Modality_Pipelines.Delsys_Pipeline.process_delsys import process_delsys_raw_file


def run_delsys_processing(**schema_filters):
    """Run Delsys raw-file processing through SciDB.

    Pass schema filters such as participant_number=["001"] or visit=["BL"]
    to limit the run. Empty lists mean bulk processing across all identities.
    """
    configure_scistack_database()
    filters = {key: schema_filters.get(key, []) for key in SCHEMA_KEYS}

    return scidb.for_each(
        process_delsys_raw_file,
        inputs={
            "raw_file_record": DelsysRawFile,
        },
        outputs=[
            DelsysProcessed,
        ],
        distribute=True,
        skip_computed=True,
        **filters,
    )
