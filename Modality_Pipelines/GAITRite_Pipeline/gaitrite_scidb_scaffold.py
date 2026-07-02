"""
GAITRite SciDB scaffold for raw-file discovery and early processing flow.

@author shensley01
@version 0.1.6
@last_updated 2026-07-02
@change_log
    - 2026-07-02 v0.1.6: Updated scaffold to use analysis schema keys instead of file-name keys for SciDB configuration.
    - 2026-07-01 v0.1.5: Updated project path references for explicit subject_data_root and database_path config keys.
    - 2026-07-01 v0.1.4: Moved into GAITRite_Pipeline and updated package-relative paths/imports.
    - 2026-07-01 v0.1.3: Renamed from main.py to gaitrite_scidb_scaffold.py to reflect the file's current purpose.
    - 2026-07-01 v0.1.2: Replaced vars import with scidb_tables import.
    - 2026-07-01 v0.1.1: Pointed the scidb GAITRite load scaffold at the shared SOP config keys.
    - 2026-07-01 v0.1.0: Wired the GAITRite raw-file discovery block to
      Modality_Pipelines/config.json and the SOP file naming convention.
"""

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import scifor
# from scifor import for_each
from scidb import for_each

import scidb
from Modality_Pipelines.common.scidb_tables import *

import load_gaitrite, distribute_gr_table_into_cycles

PIPELINE_DEVELOPMENT_ROOT = Path(__file__).resolve().parents[2]
MODALITY_PIPELINES_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PIPELINE_DEVELOPMENT_ROOT
CONFIG_PATH = MODALITY_PIPELINES_ROOT / "config.json"

with CONFIG_PATH.open("r", encoding="utf-8-sig") as f:
    config = json.load(f)

FILE_NAME_KEYS = config["file_naming"]["file_name_keys"]
SCHEMA_KEYS = config["file_naming"]["schema_keys"]

# Discover GAITRite raw files using the shared SOP config.
# Note: standalone scifor.for_each is a pure loop and does not load PathInput.
# This block is for discovery/manifest planning. Valid discovered files should
# be registered in SciDB as GAITRiteRawFile before downstream scidb.for_each parsing.
gaitrite_config = config["modalities"]["gaitrite"]
root_folder = config["project"]["subject_data_root"]
path_template = (
    "R2_{participant_number}/"
    "{visit_folder}/"
    f"{gaitrite_config['folder']}/"
    f"{config['file_naming']['pattern']}.{{extension}}"
)
gr_path_template = scifor.PathInput(path_template, root_folder=root_folder)
gaitrite_discovered_files = [
    combo for combo in gr_path_template.discover()
    if combo.get("modality") == gaitrite_config["file_code"]
]

# Load GAITRite with scidb
# Output: one loaded GAITRite record per discovered raw file/test.
db_path = Path(config["project"]["database_path"])
scidb.configure_database(db_path, dataset_schema_keys=SCHEMA_KEYS)
gr_scidb_path_template = scidb.PathInput(path_template, root_folder=root_folder)

# TODO: after GAITRiteRawFile registration exists, register gaitrite_discovered_files first.
# Then use scidb.for_each on registered records so skip_computed/lineage tracking
# can prevent duplicate downstream loads.
gr_df = scidb.for_each(
    load_gaitrite,
    inputs={
        "gaitRitePath": gr_scidb_path_template,
        "gaitRiteConfig": gaitrite_config,
    },
    outputs=[
        GAITRiteLoaded,
    ],
    participant_number=[],
    visit=[],
    test=[],
    condition=[],
    speed=[],
    trial=[],
    cycle=[],
    distribute=True,
    skip_computed=True,
)

# Break GAITRiteLoaded into cycles
# Input: GAITRiteLoaded table, where each row is one trial.
# Output: GAITRiteCycle table, where each row is one cycle.
gr_cycle_df = scidb.for_each(distribute_gr_table_into_cycles,
                             inputs = {
                                 "gaitRiteLoaded": GAITRiteLoaded,
                             },
                             outputs = [
                                    GAITRiteCycle,
                             ],
                             participant_number=[], visit=[], test=[], condition=[], speed=[], trial=[], cycle=[]
)









