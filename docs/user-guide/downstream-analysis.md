# Downstream analysis tables

The downstream analysis table layer builds stable MATLAB/Python/R-friendly outputs above the first-pass modality tables. It does not replace first-pass processing. Xsens, Delsys, and GAITRite processed tables remain the source inputs.

## Outputs

| Output | Grain | Purpose |
| --- | --- | --- |
| `TrialAnalysis` | One row per complete multimodal trial | Joined Xsens, Delsys, and GAITRite processed trial payloads. |
| `CycleUnmatched` | One row per gait cycle/side | Side-specific cycles sliced by GAITRite gait events and resampled to 101 points. |
| `VisitSummary` | One row per participant visit | Finalized visit-level EMG max values for normalization. |
| `CycleMatched` | One row per adjacent alternating L/R cycle pair | Matched cycle pairs carrying normalized and unnormalized EMG plus Xsens and GAITRite metrics. |
| `AnalysisIssue` | One row per excluded/skipped issue | Structured issue log for incomplete trials, slice failures, normalization failures, matching skips, and export failures. |

Exact table names are study-specific and are not inferred from prefixes.

| Study | Trial | Unmatched cycles | Matched cycles | Visit summary | Issues |
| --- | --- | --- | --- | --- | --- |
| R1 | `R1TrialAnalysis` | `R1CycleUnmatched` | `R1CycleMatched` | `R1VisitSummary` | `R1AnalysisIssue` |
| R2 | `TrialAnalysis` | `CycleUnmatched` | `CycleMatched` | `VisitSummary` | `AnalysisIssue` |

## Build order

The guarded all-in-one path is:

```powershell
.\bacpacs.cmd analyze build-all --study R1 --participant 001 --visit BL
```

Individual stages are also supported:

```powershell
.\bacpacs.cmd analyze build-trial --study R1 --participant 001 --visit BL
.\bacpacs.cmd analyze build-cycles --study R1 --participant 001 --visit BL
.\bacpacs.cmd analyze finalize-visit --study R1 --participant 001 --visit BL
.\bacpacs.cmd analyze normalize-cycles --study R1 --participant 001 --visit BL
.\bacpacs.cmd analyze build-matched --study R1 --participant 001 --visit BL
.\bacpacs.cmd analyze export --study R1 --participant 001 --visit BL
```

Preconditions hard-fail with a clear message:

| Stage | Requires |
| --- | --- |
| `build-cycles` | `TrialAnalysis` rows. |
| `normalize-cycles` | `CycleUnmatched` rows and finalized `VisitSummary`. |
| `build-matched` | Normalized `CycleUnmatched` rows. |
| `export` | At least one derived analysis table. |

## Data rules

- Trial joins use `participant_number`, `visit`, `test`, `condition`, `speed`, and `trial`.
- `TrialAnalysis` includes only complete multimodal trials with Xsens, Delsys, and GAITRite processed records.
- Missing modalities are preserved as `AnalysisIssue` rows.
- `CycleUnmatched` is built only from rows already present in `TrialAnalysis`.
- GAITRite gait events are the gait-cycle boundary source of truth.
- Cycle signals are resampled to 101 points.
- EMG normalization is per `participant_number + visit`.
- `CycleMatched` skips non-alternating cycles instead of coercing them and writes one warning issue per skipped cycle.
- Staleness detection is metadata-only in this version. If late trials or cycles are added, rerun `finalize-visit`, `normalize-cycles`, `build-matched`, and `export`.

## Issue log

`AnalysisIssue` rows include:

```text
participant_number, visit, test, condition, speed, trial, cycle_index,
stage, issue_type, severity, modality, source_table, source_record_id,
related_record_ids, message, created_at
```

Default severities are:

| Issue type | Severity |
| --- | --- |
| `missing_modality` | error |
| `mismatched_trial` | error |
| `missing_gait_events` | error |
| `slice_failure` | error |
| `missing_visit_summary` | error |
| `missing_or_zero_visit_max` | error |
| `non_alternating_cycles` | warning |
| `export_failure` | error |

## Exports

Exports are written to `analysis_scripts/exports` unless `--output-dir` is supplied.

```text
YYYYMMDD_r1_bacpacs_trial.csv
YYYYMMDD_r1_bacpacs_cycle_unmatched.csv
YYYYMMDD_r1_bacpacs_cycle_matched.csv
YYYYMMDD_r1_bacpacs_visit.csv
YYYYMMDD_r1_bacpacs_analysis_issues.csv
```

The unmatched and matched cycle exports are written in long form for plotting. Each row is one signal value at one time-normalized point, with `signal_group`, `signal_name`, `point_index`, `percent_gait_cycle`, and `value` columns plus the trial/cycle metadata. For example, filter `signal_group == "delsys_normalized_time_normalized"` and `signal_name == "LTA"`, then plot `percent_gait_cycle` against `value`.

The issues export is written even when there are no issues, so downstream scripts can depend on the file existing after a successful export.

## Python cycle plots

Use `analysis_scripts/plot_bacpacs_cycle_matched.py` to make seaborn/matplotlib plots from the long-form matched-cycle export. The script writes `.png` and `.svg` figures for two plot families:

- `mean_by_condition`: one mean curve per condition, faceted by muscle/joint signal.
- `overlay`: faint individual matched gait-cycle traces, faceted by muscle/joint signal.

Install plotting dependencies in the repo environment if needed:

```powershell
.\BAKPACS_env\python.exe -m pip install matplotlib seaborn
```

Then run:

```powershell
.\BAKPACS_env\python.exe .\analysis_scripts\plot_bacpacs_cycle_matched.py `
  --input .\analysis_scripts\exports\20260717_r1_bacpacs_cycle_matched.csv `
  --participant 1 `
  --visit BL `
  --output-dir .\analysis_scripts\plots\r1_001_bl_cycle_matched
```

By default it plots `delsys_normalized_time_normalized` and `xsens_time_normalized` when those signal groups are present. Use `--signals LTA RTA` to restrict the panels or `--signal-group delsys_normalized_time_normalized` to restrict the signal group.

MATLAB/Python ad hoc exports should use exact table names, for example:

```matlab
tableName = "R1TrialAnalysis";
tableName = "R1CycleUnmatched";
tableName = "R1CycleMatched";
tableName = "R1VisitSummary";
tableName = "R1AnalysisIssue";
```
