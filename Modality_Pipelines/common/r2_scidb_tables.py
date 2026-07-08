"""
SciDB table definitions for the R2 Spinal Stim multimodal pipeline.

Each class is a SciDB/SciStack storage target. In practice, each class acts
like a table-like collection keyed by the configured analysis schema metadata:
participant_number, visit, test, condition, speed, trial, and cycle.

@author shensley01
@version 0.3.1
@last_updated 2026-07-06
@change_log
    - 2026-07-06 v0.3.1: Deprecated and removed ProcessingLog; processing audit records are out of scope for the current pipeline.
    - 2026-07-02 v0.3.0: Added AFO raw/processed table classes and kept modality-specific RawFile design.
    - 2026-07-02 v0.2.1: Replaced generic RawFileRecord with modality-specific raw-file table classes.
    - 2026-07-02 v0.2.0: Added modality-specific raw-file tables and run/artifact tracking table scaffolds.
    - 2026-07-01 v0.1.1: Moved from Pipeline_development root into Modality_Pipelines/common.
    - 2026-07-01 v0.1.0: Renamed vars.py to scidb_tables.py and added initial
      table classes for raw files and modality outputs.
"""

from scidb import BaseVariable

#---------------------------------------------------------------------------
# Raw file records for each modality, after SOP validation and registration in the SciDB database.

class GAITRiteRawFile(BaseVariable):
    """Registered GAITRite raw-file record after SOP validation."""

    schema_version = 1


class XsensRawFile(BaseVariable):
    """Registered Xsens raw-file record after SOP validation."""

    schema_version = 1


class DelsysRawFile(BaseVariable):
    """Registered Delsys raw-file record after SOP validation."""

    schema_version = 1


class CosmedRawFile(BaseVariable):
    """Registered Cosmed raw-file record after SOP validation."""

    schema_version = 1


class AfoRawFile(BaseVariable):
    """Registered AFO raw-file record after SOP validation."""

    schema_version = 1

#---------------------------------------------------------------------------
# Processed output tables for each modality, after cleaning and alignment to the project trial schema.
# Gaitrite has two output tables: one for trial-level data and one for gait-cycle-level data. No filtering needed?
class GAITRiteLoaded(BaseVariable):
    """Loaded GAITRite trial-level data, one input file/test at a time."""

    schema_version = 1


class GAITRiteCycle(BaseVariable):
    """GAITRite data split into gait-cycle-level records."""

    schema_version = 1


class XsensProcessed(BaseVariable):
    """Processed Xsens kinematic output aligned to the project trial schema."""

    schema_version = 1


class DelsysProcessed(BaseVariable):
    """Processed Delsys EMG output after modality-specific cleaning."""

    schema_version = 1


class CosmedProcessed(BaseVariable):
    """Processed Cosmed metabolic output aligned to the project trial schema."""

    schema_version = 1


class AfoProcessed(BaseVariable):
    """Processed AFO output aligned to the project trial schema."""

    schema_version = 1


