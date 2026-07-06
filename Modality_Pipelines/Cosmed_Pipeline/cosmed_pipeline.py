"""
SciStack wrappers for COSMED processing stages.

@author shensley01
@version 0.1.0
@last_updated 2026-07-06
@change_log
    - 2026-07-06 v0.1.0: Added COSMED RawFile -> CosmedProcessed SciDB
      for_each wrapper.
"""

from __future__ import annotations

import scidb

from Modality_Pipelines.common.common_config import SCHEMA_KEYS, configure_scistack_database
from Modality_Pipelines.common.scidb_tables import CosmedProcessed, CosmedRawFile
from Modality_Pipelines.Cosmed_Pipeline.process_cosmed import process_cosmed_raw_file


def run_cosmed_processing(**schema_filters):
    """Load registered COSMED raw files through SciDB.

    Pass schema filters such as participant_number=["001"] or visit=["BL"]
    to limit the run. Empty lists mean bulk processing across all identities.
    """
    configure_scistack_database()
    filters = {key: schema_filters.get(key, []) for key in SCHEMA_KEYS}

    return scidb.for_each(
        process_cosmed_raw_file,
        inputs={
            "raw_file_record": CosmedRawFile,
        },
        outputs=[
            CosmedProcessed,
        ],
        distribute=True,
        skip_computed=True,
        **filters,
    )
