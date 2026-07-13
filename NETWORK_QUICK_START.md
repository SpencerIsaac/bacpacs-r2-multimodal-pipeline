# BACPACS network quick start

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

This checks the repo-local Python environment, R1 subject-data root, R2 subject-data root, shared database path, and database folder.

## Launch the GUI

```powershell
.\bacpacs.cmd gui
```

You can also double-click:

```text
launch_bacpacs_gui.cmd
```

The GUI mirrors the CLI workflow and calls the same backend functions.

## Run CLI commands

The `.cmd` launcher supports the same commands as the installed `bacpacs` executable, but it does not require the environment `Scripts` folder to be on PATH.

```powershell
.\bacpacs.cmd studies
.\bacpacs.cmd status --study R2
.\bacpacs.cmd validate --study R2 --modality xsens
.\bacpacs.cmd register --study R2 --dry-run
.\bacpacs.cmd process --study R2 --modality delsys --dry-run
```

Operational commands require `--study R1` or `--study R2`. The commands intended before choosing a study are `studies`, `doctor`, `gui`, and help.

## Documentation

MkDocs pages live under:

```text
docs/
```

Run the docs freshness check after changing config, CLI behavior, table names, or study conventions:

```powershell
python scripts\check_docs_freshness.py
```

