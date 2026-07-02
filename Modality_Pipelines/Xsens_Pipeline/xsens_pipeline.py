"""
SciStack wrappers for Xsens processing stages.

@author shensley01
@version 0.1.0
@last_updated 2026-07-02
@change_log
    - 2026-07-02 v0.1.0: Added Xsens SciDB for_each wrapper scaffold.
"""

from __future__ import annotations

import scidb

from Modality_Pipelines.common.common_config import SCHEMA_KEYS, configure_scistack_database
from Modality_Pipelines.common.scidb_tables import XsensProcessed, XsensRawFile
from Modality_Pipelines.Xsens_Pipeline.process_xsens import process_xsens_raw_file


def run_xsens_processing(**schema_filters):
    """Run Xsens raw-file processing through SciDB.

    Pass schema filters such as participant_number=["001"] or visit=["BL"]
    to limit the run. Empty lists mean bulk processing across all identities.
    """
    configure_scistack_database()
    filters = {key: schema_filters.get(key, []) for key in SCHEMA_KEYS}

    return scidb.for_each(
        process_xsens_raw_file,
        inputs={
            "raw_file_record": XsensRawFile,
        },
        outputs=[
            XsensProcessed,
        ],
        distribute=True,
        skip_computed=True,
        **filters,
    )
