# GUI control panel

The Streamlit control panel is the visual control layer for the same backend used by the CLI.

Launch it with:

```powershell
.\bacpacs.cmd gui
```

## Design rule

The GUI does not own processing logic. It calls the same backend functions as the CLI.

```text
Backend pipeline API
  validate_study_files()
  register_raw_files()
  run_modality_processing()
  list_available_analyses()
  run_registered_analysis()

        |                         |
        v                         v
      CLI                       GUI
```

## Main pages

| Page | Mirrors CLI command(s) |
| --- | --- |
| Pipeline workflow | `doctor`, `validate`, `register`, `process`, `analyses`, `analyze`, `status` |
| Processing ledger | `status` plus live table counts |
| Raw file review | validation and RawFile registration review |
| Configuration | selected study config and processing config visibility |
| Lineage / records | SciStack/SciDB lineage and record metadata |

Write actions in the GUI require explicit confirmation. Preview and dry-run actions are read-only.
