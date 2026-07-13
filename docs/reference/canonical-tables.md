# Canonical tables

## Visit codes

### R1

| Canonical visit | Folder name | File code |
| --- | --- | --- |
| baseline | `1. Baseline` | `BL` |
| mid_test | `2. Mid-Test` | `MP` |
| post_test | `3. Post-Test` | `PT` |
| follow_up | `4. Follow-Up` | `FU` |

### R2

| Canonical visit | Folder name | File code |
| --- | --- | --- |
| baseline | `2. Baseline` | `BL` |
| pre_test | `3. Pre-Test` | `PR` |
| mid_test | `4. Mid-Test` | `MP` |
| post_test | `5. Post-Test` | `PT` |
| follow_up | `6. Follow-Up` | `FU` |

## Modality codes

| Canonical modality | Folder name | File code | Primary extension |
| --- | --- | --- | --- |
| gaitrite | `GAITRite` | `GR` | `.xlsx` |
| xsens | `Xsens` | `xsens` | `.mvnx` |
| delsys | `Delsys` | `delsys` | `.mat` |
| cosmed | `Cosmed` | `cosmed` | `.xlsx` |
| afo | `AFO` | `AFO` | `.csv` |

## Shared schema keys

```text
participant_number
visit
test
condition
speed
trial
cycle
```

## RawFile tables

| Study | GAITRite | Xsens | Delsys | Cosmed | AFO |
| --- | --- | --- | --- | --- | --- |
| R1 | `R1GAITRiteRawFile` | `R1XsensRawFile` | `R1DelsysRawFile` | `R1CosmedRawFile` | `R1AfoRawFile` |
| R2 | `GAITRiteRawFile` | `XsensRawFile` | `DelsysRawFile` | `CosmedRawFile` | `AfoRawFile` |

## Processed tables

| Study | GAITRite | Xsens | Delsys | Cosmed | AFO |
| --- | --- | --- | --- | --- | --- |
| R1 | `R1GAITRiteLoaded`, `R1GAITRiteCycle` | `R1XsensProcessed` | `R1DelsysProcessed` | `R1CosmedProcessed` | `R1AfoProcessed` |
| R2 | `GAITRiteLoaded`, `GAITRiteCycle` | `XsensProcessed` | `DelsysProcessed` | `CosmedProcessed` | `AfoProcessed` |

## Public function names

```text
validate_study_files(...)
register_raw_files(...)
run_modality_processing(...)
list_available_analyses(...)
run_registered_analysis(...)
process_delsys_raw_file(...)
process_xsens_raw_file(...)
process_gaitrite_raw_file(...)
```
