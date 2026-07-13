# Running the pipeline

This section describes how operators use the BACPACS CLI or GUI to move session files from filesystem review into registered and processed study data.

Validation and dry-run commands are review steps and do not write to the database. Registration writes RawFile records for valid new files. Processing writes processed outputs when eligible records have not already been processed, unless overwrite behavior is requested.

## Data flow

```text
Raw files
  validated, registered once
        |
        v
Processed table
  cleaned, structured first-pass output
        |
        v
Analysis table(s)
  any number of derived downstream results
```

Analysis processors only read from processed tables. They do not read raw files, RawFile tables, or filesystem paths directly.

## Step 1. Validate files

```powershell
.\bacpacs.cmd validate --study R2
```

Validation checks whether discovered primary raw files follow the required naming convention and whether file metadata agree with the participant, visit, and modality folder where the file is stored.

## Step 2. Preview registration

```powershell
.\bacpacs.cmd register --study R2 --dry-run
```

Dry-run registration previews what registration would do without writing to the database.

## Step 3. Register valid files

```powershell
.\bacpacs.cmd register --study R2
```

Registration creates typed RawFile records in the study database for each valid file that has not already been registered. Files already registered are skipped automatically. Raw data files remain in the filesystem.

## Step 4. Run first-pass modality processing

```powershell
.\bacpacs.cmd process --study R2 --modality all
```

To run one modality:

```powershell
.\bacpacs.cmd process --study R2 --modality delsys
.\bacpacs.cmd process --study R2 --modality xsens
.\bacpacs.cmd process --study R2 --modality gaitrite
```

## Step 5. Run downstream analyses

```powershell
.\bacpacs.cmd analyses --study R2
.\bacpacs.cmd analyze --study R2 --analysis coactivation
```

Downstream analyses are discovered from `Modality_Pipelines/common/analysis_registry.json`.

## Step 6. Check status

```powershell
.\bacpacs.cmd status --study R2
```

The GUI can also be opened to review the same state visually:

```powershell
.\bacpacs.cmd gui
```
