# MATLAB-Native R2 Multimodal Pipeline Migration Plan

@author shensley01
@version 0.1.0
@last_updated 2026-07-06
@status planning

## Executive Summary

The R2 Spinal Stim multimodal pipeline should be migrated from the current Python-first scaffold into a MATLAB-native project pipeline that uses the existing data_analytics MATLAB library as the processing engine. The migration is feasible because the core modality algorithms already exist in MATLAB under the shared data analytics code library, and the SciStack MATLAB interface provides `scidb`, `scifor`, and `scihist` functionality for database-backed processing, lineage, and `for_each` orchestration.

The target architecture keeps `config.json` as the shared study configuration source, ports project-specific manifest and table-class glue into MATLAB, and wraps existing modality loaders/processors in MATLAB `scidb.for_each` runners. The project should not carry forward the unused `ProcessingLog` artifact. Processing audit/log table classes are explicitly deprecated and removed from scope for this migration.

## TPM Framing

### Objective

Deliver a MATLAB-native R2 pipeline that can discover, validate, register, process, and organize multimodal ambulation raw files using the established lab MATLAB analytics libraries and the existing SciStack database backend.

### Business / Lab Value

- Aligns pipeline execution with the lab's existing MATLAB analytics ecosystem.
- Reduces duplicate Python translations of algorithms that already exist and are maintained in MATLAB.
- Keeps project-specific SOP validation and SciDB orchestration explicit, reusable, and testable.
- Preserves the current DuckDB/SciStack storage model while making MATLAB the primary user-facing pipeline layer.
- Improves maintainability for lab users who are more comfortable validating and extending MATLAB code.

### Non-Goals

- Do not rewrite the data_analytics modality algorithms unless validation shows an R2-specific gap.
- Do not build a new database engine or replace SciStack/DuckDB during this migration.
- Do not introduce a processing-log table or audit artifact. `ProcessingLog` is deprecated and removed from the planned table surface.
- Do not solve downstream statistical analysis or visualization workflows in the initial migration.
- Do not change the SOP file naming convention unless the study team changes the protocol.

## Current State

### Existing R2 Python Scaffold

The current scaffold lives in:

```text
Y:\BACPACS R2 - Spinal Stim\Pipeline_development\Modality_Pipelines
```

Important files:

```text
config.json
common/common_config.py
common/manifest.py
common/scidb_tables.py
GAITRite_Pipeline/gaitrite_pipeline.py
GAITRite_Pipeline/load_gaitrite.py
Xsens_Pipeline/xsens_pipeline.py
Delsys_Pipeline/delsys_pipeline.py
Cosmed_Pipeline/cosmed_pipeline.py
```

The scaffold already defines the major project concepts:

- Shared study vocabulary in `config.json`
- SOP file naming pattern: `R2_{participant_number}_{visit}_{modality}_{outcome}`
- Analysis schema keys: `participant_number`, `visit`, `test`, `condition`, `speed`, `trial`, `cycle`
- Raw-file registration by modality
- Processed output tables by modality
- GAITRite load and cycle-distribution wrappers

### Existing MATLAB Dependencies

The reusable MATLAB analytics library is located at:

```text
Y:\LabMembers\S Hensley\data_analytics_code+library\data-analytics-code-libraries\libraries
```

Key modality libraries already present:

```text
load-gaitrite/matlab/loadGaitRiteOneFile.m
load-gaitrite/matlab/preprocessGaitRiteOneTrial.m
load-gaitrite/matlab/distributeGaitRiteDataToSeparateTable.m
load-xsens/matlab/loadXSENSOneFile.m
load-delsys-emg/matlab/loadDelsysEMGOneFile.m
cosmed/matlab/loadCosmedData.m
filter-emg/
filter-imu/
time-sync-hardware-modalities/
segment-gait-cycles/
match-cycles/
merge-gaitrite-and-sensor-tables/
```

The MATLAB SciStack layer is available through:

```text
Y:\BACPACS R2 - Spinal Stim\Pipeline_development\BAKPACS_env\Lib\site-packages\scimatlab\matlab
```

Key SciStack MATLAB APIs:

```text
+scidb/configure_database.m
+scidb/BaseVariable.m
+scidb/for_each.m
+scifor/for_each.m
+scihist/configure_database.m
```

## Target State

The target is a MATLAB-native pipeline folder alongside or replacing the Python scaffold after validation:

```text
Pipeline_development/
  Modality_Pipelines/
    config.json
    README.md
    docs/
      MATLAB_Native_Pipeline_Migration_Plan.md
    matlab/
      setup_r2_matlab_pipeline.m
      run_r2_pipeline.m
      common/
        loadR2Config.m
        configureR2Database.m
        formatR2ParticipantNumber.m
        formatR2Participant.m
        buildR2FileName.m
        parseR2FileName.m
        parseR2Outcome.m
        buildRawFileManifest.m
        validateRawFile.m
        registerRawFiles.m
      vars/
        GAITRiteRawFile.m
        XsensRawFile.m
        DelsysRawFile.m
        CosmedRawFile.m
        AfoRawFile.m
        GAITRiteLoaded.m
        GAITRiteCycle.m
        XsensProcessed.m
        DelsysProcessed.m
        CosmedProcessed.m
        AfoProcessed.m
      GAITRite_Pipeline/
        processGaitRiteRawFile.m
        distributeGaitRiteLoaded.m
        runGaitRiteLoading.m
        runGaitRiteCycleDistribution.m
      Xsens_Pipeline/
        processXsensRawFile.m
        runXsensProcessing.m
      Delsys_Pipeline/
        processDelsysRawFile.m
        runDelsysProcessing.m
      Cosmed_Pipeline/
        processCosmedRawFile.m
        runCosmedProcessing.m
```

`ProcessingLog.m` should not be created. If an old local class exists, it should be deleted or moved to an explicit archive outside the active MATLAB path.

## Architecture Principles

### 1. MATLAB owns orchestration

Pipeline entry points, wrappers, manifest building, and modality runners should be MATLAB `.m` files. Users should be able to run the pipeline from MATLAB without directly invoking Python scripts.

### 2. SciStack owns storage

MATLAB table classes should inherit from `scidb.BaseVariable`. `scidb.configure_database` should connect to `r2_pipeline.duckdb` using the configured schema keys.

### 3. data_analytics owns modality algorithms

Existing loaders and processing functions should be reused directly. Project code should not duplicate `loadGaitRiteOneFile`, `loadXSENSOneFile`, `loadDelsysEMGOneFile`, or `loadCosmedData` logic.

### 4. config.json remains source of truth

Visit folders, modality folders, file codes, condition codes, and schema keys should stay in `config.json`. MATLAB helpers should read this JSON rather than re-declaring the vocabulary in code.

### 5. Manifest before processing

Raw files must be discovered, parsed, validated, and registered before modality processing starts. Processing should operate on registered raw-file records, not ad hoc folder searches.

### 6. No active processing-log artifact

The migration will not include a `ProcessingLog` table. Operational visibility should come from command-window output, returned result tables, SciStack record metadata, and future QC tables if needed.

## Workstreams

### Workstream A: Project Setup and Path Management

Deliverables:

- `setup_r2_matlab_pipeline.m`
- MATLAB path setup for data_analytics libraries
- MATLAB path setup for SciStack MATLAB bridge
- MATLAB path setup for R2 pipeline code

Acceptance Criteria:

- Running `setup_r2_matlab_pipeline` adds all required library folders.
- MATLAB can resolve `loadGaitRiteOneFile`, `loadXSENSOneFile`, `loadDelsysEMGOneFile`, `loadCosmedData`, `scidb.configure_database`, and `scidb.for_each`.
- Setup does not rely on the user manually adding folders.

Risks:

- Network path mapping may differ across machines.
- MATLAB Python environment may not point at `BAKPACS_env` by default.

Mitigations:

- Use explicit absolute paths initially.
- Add a setup validation block that checks `exist(functionName, 'file')` and reports missing dependencies.
- Document expected MATLAB `pyenv` setup if SciStack bridge fails.

### Workstream B: Config Port

Deliverables:

- `loadR2Config.m`
- `configureR2Database.m`
- Path and naming helpers equivalent to `common_config.py`

Acceptance Criteria:

- MATLAB can parse `config.json` with `jsondecode`.
- MATLAB helper output matches Python helper output for representative participants, visits, modalities, and outcomes.
- `configureR2Database` calls `scidb.configure_database` with `r2_pipeline.duckdb` and the configured schema keys.

Test Cases:

- `formatR2ParticipantNumber(1)` returns `"001"`.
- `formatR2Participant("001")` returns `"R2_001"`.
- `buildR2FileName("001", "baseline", "gaitrite", "SSV1_noAFO")` returns `"R2_001_BL_GR_SSV1_noAFO"`.
- `parseR2FileName("R2_001_BL_GR_SSV1_noAFO.xlsx")` returns participant `001`, visit `BL`, modality `GR`, outcome `SSV1_noAFO`.

### Workstream C: MATLAB SciDB Variable Classes

Deliverables:

- MATLAB class files under `matlab/vars/`
- Active variable class set:
  - Raw: `GAITRiteRawFile`, `XsensRawFile`, `DelsysRawFile`, `CosmedRawFile`, `AfoRawFile`
  - Processed: `GAITRiteLoaded`, `GAITRiteCycle`, `XsensProcessed`, `DelsysProcessed`, `CosmedProcessed`, `AfoProcessed`

Acceptance Criteria:

- Each class is an empty subclass of `scidb.BaseVariable`.
- Classes are visible on the MATLAB path.
- A smoke test can save and load a simple record for a test variable using the configured schema keys.
- No `ProcessingLog` class exists in the active pipeline path.

Example Class Pattern:

```matlab
classdef GAITRiteRawFile < scidb.BaseVariable
end
```

### Workstream D: Manifest and Registration

Deliverables:

- `buildRawFileManifest.m`
- `validateRawFile.m`
- `parseR2Outcome.m`
- `registerRawFiles.m`

Responsibilities:

- Crawl participant folders under `subject_data_root`.
- Only include configured primary extensions by modality.
- Parse SOP file names.
- Validate participant folder, visit folder, modality folder, and outcome tokens.
- Flag review rows without writing them as valid raw-file records.
- Register valid rows into modality-specific raw-file SciDB tables.

Acceptance Criteria:

- Manifest returns a MATLAB table with one row per discovered primary raw file.
- Manifest includes status and issues columns.
- Invalid filenames are flagged as `review` and are not registered by default.
- Duplicate schema identities are flagged for review.
- Valid files are saved to the correct raw-file table with schema metadata.

Suggested Manifest Columns:

```text
file_path
file_name
extension
participant_number
visit
modality
outcome
test
condition
speed
trial
cycle
status
issues
```

### Workstream E: GAITRite Vertical Slice

Deliverables:

- `processGaitRiteRawFile.m`
- `distributeGaitRiteLoaded.m`
- `runGaitRiteLoading.m`
- `runGaitRiteCycleDistribution.m`

Processing Flow:

1. `GAITRiteRawFile` records contain path payloads.
2. `runGaitRiteLoading` uses `scidb.for_each` to call `processGaitRiteRawFile`.
3. `processGaitRiteRawFile` calls `loadGaitRiteOneFile` from the data_analytics library.
4. Output is saved as `GAITRiteLoaded`.
5. `runGaitRiteCycleDistribution` calls `distributeGaitRiteLoaded`.
6. `distributeGaitRiteLoaded` calls `distributeGaitRiteDataToSeparateTable`.
7. Output is saved as `GAITRiteCycle`.

Acceptance Criteria:

- One registered GAITRite raw file can be processed end-to-end.
- Trial-level `GAITRiteLoaded` output matches the existing MATLAB loader output.
- Cycle/row-level `GAITRiteCycle` output matches `distributeGaitRiteDataToSeparateTable`.
- `skip_computed=true` avoids reprocessing already-computed records.
- Filtered runs by participant and visit work.

### Workstream F: Remaining Modality Wrappers

Deliverables:

- Xsens processing wrapper and runner
- Delsys processing wrapper and runner
- Cosmed processing wrapper and runner
- AFO placeholder or explicit deferral decision

Acceptance Criteria:

- Each modality runner processes one registered valid raw-file record.
- Each runner saves output to the correct processed table.
- Each runner supports schema filters and `skip_computed`.
- Each runner returns a result table suitable for review.

Open Design Questions:

- Should Xsens raw `.mvnx` outputs be saved as wide tables, structs, or normalized event/timeseries tables?
- Should Delsys filtering happen inside the first processing pass or as a separate derived variable stage?
- Should Cosmed output be raw loaded data only, or should the first pass include domain metrics such as VO2 summaries?
- Should AFO be included in the first MATLAB migration milestone or deferred until the primary four modalities are stable?

### Workstream G: Validation and Cutover

Deliverables:

- MATLAB smoke-test script
- Representative participant test run
- Comparison notes against current Python scaffold where equivalent
- README update for MATLAB usage

Acceptance Criteria:

- Setup script runs successfully on the target workstation.
- Manifest dry run completes and produces reviewable output.
- Raw-file registration writes expected records.
- GAITRite vertical slice completes for at least one participant/visit/test.
- No active code references `ProcessingLog`.
- README contains MATLAB usage instructions and current table surface.

## Milestone Plan

### Milestone 0: Cleanup and Planning

Status: In progress

Scope:

- Remove the active `ProcessingLog` table class and replace active table-surface documentation with deprecation notes.
- Create this TPM planning document.
- Confirm MATLAB dependency locations.

Exit Criteria:

- Active code contains no `ProcessingLog` class or processing-log table references. Documentation may retain explicit deprecation notes.
- Planning document is committed or otherwise saved in pipeline docs.

### Milestone 1: MATLAB Bootstrap

Scope:

- Create MATLAB folder structure.
- Add setup script.
- Add config/database helpers.
- Add variable classes.

Exit Criteria:

- MATLAB can configure the R2 database.
- MATLAB can instantiate all active table classes.
- Setup script validates all expected external library functions.

### Milestone 2: Manifest Registration

Scope:

- Port manifest discovery and validation.
- Register raw files into modality-specific tables.
- Add dry-run mode.

Exit Criteria:

- Manifest table output is reviewable by a human.
- Valid raw files register correctly.
- Invalid files are not registered by default.

### Milestone 3: GAITRite End-to-End

Scope:

- Implement GAITRite processing wrappers.
- Run trial-level loading.
- Run row/cycle distribution.
- Validate against known MATLAB library behavior.

Exit Criteria:

- GAITRite pipeline completes for representative files.
- Outputs are saved as `GAITRiteLoaded` and `GAITRiteCycle`.
- Re-runs skip computed records unless explicitly overridden.

### Milestone 4: Xsens, Delsys, and Cosmed

Scope:

- Implement remaining modality wrappers.
- Confirm output shape for each modality.
- Save processed outputs to SciDB tables.

Exit Criteria:

- Each primary modality has a successful one-file smoke test.
- Each modality supports participant/visit/test filtering.

### Milestone 5: Documentation and Handoff

Scope:

- Update README with MATLAB-native instructions.
- Document known limitations and expected folder structure.
- Provide common run commands.

Exit Criteria:

- A MATLAB user can set up and run the pipeline from documentation alone.
- Known gaps are listed explicitly.

## Suggested Implementation Details

### Setup Script Skeleton

```matlab
function setup_r2_matlab_pipeline()
    pipelineRoot = "Y:\BACPACS R2 - Spinal Stim\Pipeline_development\Modality_Pipelines";
    analyticsRoot = "Y:\LabMembers\S Hensley\data_analytics_code+library\data-analytics-code-libraries\libraries";
    scimatlabRoot = "Y:\BACPACS R2 - Spinal Stim\Pipeline_development\BAKPACS_env\Lib\site-packages\scimatlab\matlab";

    addpath(genpath(fullfile(pipelineRoot, "matlab")));
    addpath(genpath(analyticsRoot));
    addpath(genpath(scimatlabRoot));

    requiredFunctions = [
        "loadGaitRiteOneFile"
        "loadXSENSOneFile"
        "loadDelsysEMGOneFile"
        "loadCosmedData"
        "scidb.configure_database"
        "scidb.for_each"
    ];

    for i = 1:numel(requiredFunctions)
        assert(exist(requiredFunctions(i), "file") == 2, "Missing required function: %s", requiredFunctions(i));
    end
end
```

### Database Configuration Skeleton

```matlab
function db = configureR2Database(config)
    if nargin < 1
        config = loadR2Config();
    end

    databasePath = string(config.project.database_path);
    schemaKeys = string(config.file_naming.schema_keys);
    db = scidb.configure_database(databasePath, schemaKeys);
end
```

### GAITRite Runner Skeleton

```matlab
function result = runGaitRiteLoading(varargin)
    configureR2Database();

    inputs = struct();
    inputs.raw_file_record = GAITRiteRawFile();

    result = scidb.for_each( ...
        @processGaitRiteRawFile, ...
        inputs, ...
        {GAITRiteLoaded()}, ...
        "distribute", true, ...
        "skip_computed", true, ...
        varargin{:});
end
```

### GAITRite Processor Skeleton

```matlab
function out = processGaitRiteRawFile(rawFileRecord)
    if istable(rawFileRecord)
        filePath = string(rawFileRecord.file_path(1));
    elseif isstruct(rawFileRecord)
        filePath = string(rawFileRecord.file_path);
    else
        error("Unsupported GAITRite raw-file record type: %s", class(rawFileRecord));
    end

    out = loadGaitRiteOneFile(filePath);
end
```

## Dependency Matrix

| Dependency | Owner | Required By | Status |
| --- | --- | --- | --- |
| R2 `config.json` | R2 pipeline | Config, manifest, database setup | Available |
| MATLAB data_analytics libraries | Lab analytics library | Modality processing | Available |
| MATLAB SciStack bridge | SciStack/scimatlab | Database, `for_each`, variable classes | Available |
| DuckDB database file | R2 pipeline | Storage and lineage | Available |
| SOP-compliant raw files | Study data folders | Manifest and processing | Partial/ongoing |
| MATLAB Python environment | Local workstation | SciStack bridge | Needs validation |

## Risk Register

| Risk | Impact | Likelihood | Mitigation |
| --- | --- | --- | --- |
| MATLAB cannot resolve SciStack Python bridge | Blocks database-backed pipeline | Medium | Validate `pyenv`; document required Python executable; use existing `BAKPACS_env` |
| Existing MATLAB loaders return shapes that do not save cleanly into SciDB | Blocks processed table writes | Medium | Start with GAITRite vertical slice; normalize outputs only at wrapper boundary |
| Raw file names or folders diverge from SOP | Creates registration errors | High | Manifest dry run with `status` and `issues`; review before registration |
| Duplicate schema identities exist | Ambiguous processing records | Medium | Detect duplicates in manifest and require manual resolution |
| Network drive paths vary by machine | Setup failures | Medium | Centralize paths in setup/config; prefer config-driven paths after bootstrap |
| Python and MATLAB outputs diverge | Validation uncertainty | Low/Medium | Treat MATLAB library output as source of truth; use Python only as reference where helpful |
| Scope creep into sync/statistics | Delays core migration | Medium | Keep first release focused on raw registration and modality processing |

## Decision Log

| Date | Decision | Rationale |
| --- | --- | --- |
| 2026-07-06 | Build MATLAB-native pipeline wrappers | Core analytics libraries already exist in MATLAB |
| 2026-07-06 | Keep SciStack/DuckDB backend | Existing `scidb` MATLAB bridge supports table classes and `for_each` |
| 2026-07-06 | Keep `config.json` as source of truth | Avoid duplicated SOP vocabulary across Python and MATLAB |
| 2026-07-06 | Deprecate `ProcessingLog` | Artifact is unused and not needed for current pipeline scope |
| 2026-07-06 | Use GAITRite as first vertical slice | GAITRite MATLAB functions already map directly to current Python implementation |

## Acceptance Criteria for MATLAB-Native MVP

The MVP is complete when:

- A user can run one setup command in MATLAB.
- MATLAB can configure the R2 SciDB database.
- MATLAB can build a raw-file manifest from the configured subject data root.
- MATLAB can register valid GAITRite raw files.
- MATLAB can process at least one GAITRite raw file into `GAITRiteLoaded`.
- MATLAB can distribute `GAITRiteLoaded` into `GAITRiteCycle`.
- Documentation explains setup, manifest dry run, registration, and GAITRite processing.
- No active `ProcessingLog` class or migration deliverable remains, except explicit deprecation notes in planning/changelog documentation.

## Open Questions

- Should the MATLAB migration live under `Modality_Pipelines/matlab/` or a sibling `Modality_Pipelines_MATLAB/` folder?
- Should Python scaffold files remain as reference during migration, or be archived after MATLAB reaches parity?
- Should AFO be included in the MVP or deferred to the second pass?
- What is the preferred output shape for Xsens and Delsys: one record per file, one record per trial, or one record per gait cycle?
- Should sync be modeled as its own `SynchronizationMetadata`/sync output table later, or handled as a downstream analysis stage outside the MVP?

## Recommended Next Action

Start Milestone 1 by creating the MATLAB folder structure, setup script, config/database helpers, and active table classes. Then use Milestone 2 and Milestone 3 to prove the architecture through the GAITRite vertical slice before expanding to the remaining modalities.

