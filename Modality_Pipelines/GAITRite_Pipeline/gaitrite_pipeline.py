"""
SciStack wrappers for GAITRite processing stages.

@author shensley01
@version 0.1.0
@last_updated 2026-07-06
@change_log
    - 2026-07-06 v0.1.0: Added GAITRite RawFile -> GAITRiteLoaded and
      GAITRiteLoaded -> GAITRiteCycle SciDB for_each wrappers.
"""

from __future__ import annotations

import scidb

from Modality_Pipelines.common.common_config import SCHEMA_KEYS, configure_scistack_database
from Modality_Pipelines.common.scidb_tables import GAITRiteCycle, GAITRiteLoaded, GAITRiteRawFile
from Modality_Pipelines.GAITRite_Pipeline.load_gaitrite import (
    distribute_gaitrite_loaded,
    process_gaitrite_raw_file,
)


def run_gaitrite_loading(**schema_filters):
    """Load registered GAITRite raw files through SciDB.

    Pass schema filters such as participant_number=["001"] or visit=["BL"]
    to limit the run. Empty lists mean bulk processing across all identities.
    """
    configure_scistack_database()
    filters = {key: schema_filters.get(key, []) for key in SCHEMA_KEYS}

    return scidb.for_each(
        process_gaitrite_raw_file,
        inputs={
            "raw_file_record": GAITRiteRawFile,
        },
        outputs=[
            GAITRiteLoaded,
        ],
        distribute=True,
        skip_computed=True,
        **filters,
    )


def run_gaitrite_cycle_distribution(**schema_filters):
    """Split loaded GAITRite trial rows into GAITRite row/cycle records."""
    configure_scistack_database()
    filters = {key: schema_filters.get(key, []) for key in SCHEMA_KEYS}

    return scidb.for_each(
        distribute_gaitrite_loaded,
        inputs={
            "gaitrite_loaded": GAITRiteLoaded,
        },
        outputs=[
            GAITRiteCycle,
        ],
        distribute=True,
        skip_computed=True,
        **filters,
    )
