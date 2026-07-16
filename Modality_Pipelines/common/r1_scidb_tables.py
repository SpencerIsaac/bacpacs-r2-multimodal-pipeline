"""
SciDB table definitions for the BACPACS R1 Smart AFO pipeline namespace.

These classes intentionally mirror the R2 table shape while using separate
class names so R1 and R2 can live as parallel flows in the same database.
"""

from scidb import BaseVariable


class R1GAITRiteRawFile(BaseVariable):
    """Registered R1 GAITRite raw-file record after SOP validation."""

    schema_version = 1


class R1XsensRawFile(BaseVariable):
    """Registered R1 Xsens raw-file record after SOP validation."""

    schema_version = 1


class R1DelsysRawFile(BaseVariable):
    """Registered R1 Delsys raw-file record after SOP validation."""

    schema_version = 1


class R1CosmedRawFile(BaseVariable):
    """Registered R1 Cosmed raw-file record after SOP validation."""

    schema_version = 1


class R1AfoRawFile(BaseVariable):
    """Registered R1 AFO raw-file record after SOP validation."""

    schema_version = 1


class R1GAITRiteLoaded(BaseVariable):
    """Loaded R1 GAITRite trial-level data, one input file/test at a time."""

    schema_version = 1


class R1GAITRiteCycle(BaseVariable):
    """R1 GAITRite data split into gait-cycle-level records."""

    schema_version = 1


class R1XsensProcessed(BaseVariable):
    """Processed R1 Xsens kinematic output aligned to the project trial schema."""

    schema_version = 1


class R1DelsysProcessed(BaseVariable):
    """Processed R1 Delsys EMG output after modality-specific cleaning."""

    schema_version = 1


class R1CosmedProcessed(BaseVariable):
    """Processed R1 Cosmed metabolic output aligned to the project trial schema."""

    schema_version = 1


class R1AfoProcessed(BaseVariable):
    """Processed R1 AFO output aligned to the project trial schema."""

    schema_version = 1

class R1TrialAnalysis(BaseVariable):
    """Derived R1 trial-level multimodal analysis row."""

    schema_version = 1


class R1CycleUnmatched(BaseVariable):
    """Derived R1 side-specific gait-cycle analysis row before L/R matching."""

    schema_version = 1


class R1CycleMatched(BaseVariable):
    """Derived R1 matched left/right gait-cycle pair for symmetry analysis."""

    schema_version = 1


class R1VisitSummary(BaseVariable):
    """Derived R1 finalized visit-level normalization summary."""

    schema_version = 1


class R1AnalysisIssue(BaseVariable):
    """Structured R1 downstream analysis issue log."""

    schema_version = 1
