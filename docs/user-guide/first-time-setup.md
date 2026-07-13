# First-time setup

Use this page from any Windows computer that can access the shared RTO project folder and BACPACS subject-data folders.

## Open PowerShell

Open Windows PowerShell or Command Prompt.

## Navigate to the pipeline folder

```powershell
cd "Y:\BACPACS R2 - Spinal Stim\Pipeline_development"
```

## Open command help

```powershell
.\bacpacs.cmd --help
```

## Check this computer

```powershell
.\bacpacs.cmd doctor
```

The doctor command does not process data or write to the database. It checks that the computer can see the repository, repo-local Python environment, R1 subject data folder, R2 subject data folder, shared database path, and database folder.

Expected status pattern:

```text
repo_root [ok]
repo_env_python [ok]
R1 subject_data_root [ok]
R1 database_path [ok]
R2 subject_data_root [ok]
R2 database_path [ok]
database_folder [ok]
```

Actual output includes full file paths. If any item shows `missing`, confirm that the computer is connected to the shared drive and that mapped drive paths are available.

## Launch the GUI

```powershell
.\bacpacs.cmd gui
```

The GUI and CLI call the same backend API. Use the CLI for reproducible SOP runs and the GUI for visual review and button-driven control.
