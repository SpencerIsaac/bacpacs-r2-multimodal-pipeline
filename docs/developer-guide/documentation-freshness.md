# Documentation freshness

The documentation freshness system prevents the SOP, MkDocs pages, tests, and executable configuration from drifting silently.

## Files involved

```text
docs/source_of_truth.json
scripts/check_docs_freshness.py
tests/test_docs_freshness.py
```

## What the check validates

The freshness script checks that docs and source metadata still agree with executable pipeline facts:

- supported studies: `R1`, `R2`
- one shared database path
- study project names
- subject-data roots
- resolved filename patterns
- visit folders and visit file codes
- modality folders, file codes, and primary extensions
- RawFile and processed table names
- public CLI commands
- required documentation pages

## Run the check

```powershell
python scripts\check_docs_freshness.py
```

Or through tests:

```powershell
pytest tests\test_docs_freshness.py
```

## Update rule

When changing config, CLI commands, table names, folder names, or registry behavior, update docs in the same change and rerun the freshness check.

