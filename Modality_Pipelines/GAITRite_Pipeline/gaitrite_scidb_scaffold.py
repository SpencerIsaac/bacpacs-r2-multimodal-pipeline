"""
Deprecated GAITRite SciDB scaffold.

@author shensley01
@version 0.2.0
@last_updated 2026-07-06
@change_log
    - 2026-07-06 v0.2.0: Deprecated exploratory scaffold and re-exported the
      implemented GAITRite SciDB wrappers from gaitrite_pipeline.py.
    - 2026-07-02 v0.1.6: Updated scaffold to use analysis schema keys instead of file-name keys for SciDB configuration.
    - 2026-07-01 v0.1.5: Updated project path references for explicit subject_data_root and database_path config keys.
    - 2026-07-01 v0.1.4: Moved into GAITRite_Pipeline and updated package-relative paths/imports.
    - 2026-07-01 v0.1.3: Renamed from main.py to gaitrite_scidb_scaffold.py to reflect the file's current purpose.
    - 2026-07-01 v0.1.2: Replaced vars import with scidb_tables import.
    - 2026-07-01 v0.1.1: Pointed the scidb GAITRite load scaffold at the shared SOP config keys.
    - 2026-07-01 v0.1.0: Wired the GAITRite raw-file discovery block to
      Modality_Pipelines/config.json and the SOP file naming convention.

This file is kept so older notes/imports do not break. New code should import
from Modality_Pipelines.GAITRite_Pipeline.gaitrite_pipeline instead.
"""

from __future__ import annotations

from Modality_Pipelines.GAITRite_Pipeline.gaitrite_pipeline import (
    run_gaitrite_cycle_distribution,
    run_gaitrite_loading,
)

__all__ = ["run_gaitrite_loading", "run_gaitrite_cycle_distribution"]
