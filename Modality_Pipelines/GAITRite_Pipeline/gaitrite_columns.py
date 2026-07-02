"""
GAITRite column definitions for the R2 Spinal Stim pipeline.

Created on June 30th 2026
Last updated on July 1st 2026
@author shensley01
@version 0.1.2
@last_updated 2026-07-01
@change_log
    - 2026-07-01 v0.1.2: Renamed from gaitrite_globals.py to gaitrite_columns.py to match the file contents.
    - 2026-07-01 v0.1.1: Updated shared schema import after common_globals.py
      was renamed to common_config.py.
    - 2026-06-30 v0.1.0: Initial GAITRite column scaffold.

File Purpose:
This file houses GAITRite-specific export column definitions. Shared
SOP vocabulary belongs in the root config.json and common/common_config.py.
"""

from Modality_Pipelines.common.common_config import SCHEMA_KEYS

# ---------------------------------------------------------------------------
# GAITRite export columns
# ---------------------------------------------------------------------------

GAITRITE_SUMMARY_COLUMNS = [
    "test_record_id",
    "pt_record_id",
    "date_time_of_test",
    "distance",
    "ambulation_time",
    "velocity",
    "step_count",
    "cadence",
    "number_of_passes",
    "footfalls",
    "type_of_test",
    "research_reference",
]

GAITRITE_FOOTFALL_COLUMNS = {
    "record_id": "Record #",
    "test_record_id": "Test Record #",
    "pt_record_id": "Pt Record #",
    "footfall_object_id": "FootFall Object #",
    "timestamp": "Date / Time Stamp",
    "foot": "Left/Right Foot",
    "pass_number": "Pass Number",
    "first_contact_time": "First Contact Time",
    "last_contact_time": "Last Contact Time",
    "begin_time": "Begin Time",
    "end_time": "End Time",
    "heel_on": "Heel On",
    "heel_off": "Heel Off",
    "toe_on": "Toe On",
    "toe_off": "Toe Off",
    "step_length": "Step Length",
    "stride_length": "Stride Length",
    "base_of_support": "Base of Support",
    "step_time": "Step Time",
    "stride_time": "Stride Time",
    "swing_time": "Swing Time",
    "stance_time": "Stance Time",
    "single_support_time": "Single Support Time (sec)",
    "double_support_time": "Double Support Time (sec)",
    "stride_velocity": "Stride Velocity",
    "step_width": "Step Width",
    "stride_width": "Stride Width",
}

