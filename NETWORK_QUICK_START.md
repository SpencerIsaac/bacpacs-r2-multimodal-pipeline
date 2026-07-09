# BACPACS Network Quick Start

Use this when working from any Windows computer that can access the shared RTO project folder.

## Open a terminal in the shared pipeline folder

```powershell
cd "Y:\BACPACS R2 - Spinal Stim\Pipeline_development"
```

If the computer uses the UNC path instead of the `Y:` drive, open the same `Pipeline_development` folder from the network share and run the commands from there.

## Check that this computer can see the pipeline

```powershell
.\bacpacs.cmd doctor
```

This checks the repo-local Python environment, study subject-data roots, and database paths.

## Launch the GUI

```powershell
.\bacpacs.cmd gui
```

You can also double-click:

```text
launch_bacpacs_gui.cmd
```

## Run CLI commands

The `.cmd` launcher supports the same commands as the installed `bacpacs` executable, but it does not require the env `Scripts` folder to be on PATH and avoids local PowerShell execution-policy issues.

```powershell
.\bacpacs.cmd studies
.\bacpacs.cmd status --study R2
.\bacpacs.cmd validate --study R2 --modality xsens
.\bacpacs.cmd register --study R2 --dry-run
.\bacpacs.cmd process --study R2 --modality delsys --dry-run
```

Operational commands still require `--study R1` or `--study R2`. The only commands intended before choosing a study are `studies`, `doctor`, `gui`, and help.

## Why use the launcher?

`bacpacs` only works directly when the active environment installed the package and its `Scripts` folder is on PATH. The repo launcher finds the shared repo-local environment automatically and runs:

```powershell
python -m Modality_Pipelines.cli
```

That makes it more reliable from lab computers where PATH and drive mappings differ.

