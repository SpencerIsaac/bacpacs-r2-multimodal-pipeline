# CLI reference

The CLI syntax is:

```text
bacpacs <command> [options]
```

From the shared repo, prefer the launcher:

```powershell
.\bacpacs.cmd <command> [options]
```

## Commands

| Command | Purpose |
| --- | --- |
| `doctor` | Check that the machine can see required paths and the repo environment. |
| `studies` | List configured studies. |
| `gui` | Launch the Streamlit control panel. |
| `validate` | Dry-run validate raw-file names and folder locations. |
| `register` | Register valid raw files into study RawFile tables. |
| `process` | Run first-pass modality processing. |
| `status` | Show study paths and registered table stages. |
| `analyses` | List registry-defined downstream analyses. |
| `analyze` | Run a fixed downstream analysis stage or a registry-defined downstream analysis. |

## Common filters

| Filter | Purpose | Example |
| --- | --- | --- |
| `--study` | Selects `R1` or `R2`. | `--study R2` |
| `--participant` | Selects one participant. | `--participant 001` |
| `--visit` | Selects one visit code. | `--visit BL` |
| `--modality` | Selects one modality. | `--modality delsys` |
| `--test` | Selects one walking test. | `--test 10MWT` |
| `--condition` | Selects one condition. | `--condition noAFO` |
| `--speed` | Selects one speed. | `--speed SSV` |
| `--trial` | Selects one trial. | `--trial 1` |

Not every filter is meaningful for every command or modality. Filters narrow the selected record set; they do not change processing behavior.

## Dry run and overwrite behavior

| Command | Filters | Dry run | Overwrite | Export |
| --- | --- | --- | --- | --- |
| `doctor` | no | no | no | no |
| `validate` | yes | always read-only | no | `--output` |
| `register` | yes | `--dry-run` | no | no |
| `process` | yes | `--dry-run` | `--overwrite` | no |
| `analyses` | modality only | no | no | no |
| `analyze` | yes | `--dry-run` | `--overwrite` | no |
| `status` | study only | no | no | no |
| `gui` | no | no | no | no |

## Derived downstream stages

The fixed multimodal downstream table layer is run through positional `analyze` stages:

```powershell
.\bacpacs.cmd analyze build-trial --study R1 --participant 001 --visit BL
.\bacpacs.cmd analyze build-cycles --study R1 --participant 001 --visit BL
.\bacpacs.cmd analyze finalize-visit --study R1 --participant 001 --visit BL
.\bacpacs.cmd analyze normalize-cycles --study R1 --participant 001 --visit BL
.\bacpacs.cmd analyze build-matched --study R1 --participant 001 --visit BL
.\bacpacs.cmd analyze export --study R1 --participant 001 --visit BL
.\bacpacs.cmd analyze build-all --study R1 --participant 001 --visit BL
```

Registry-defined ad hoc analyses still use `--analysis`:

```powershell
.\bacpacs.cmd analyze --study R2 --analysis coactivation
```