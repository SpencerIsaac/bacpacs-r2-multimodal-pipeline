# SOP source of truth

The approved BACPACS Multimodal Ambulation Data Pipeline SOP is the human source of truth for operator workflow, file naming, folder organization, and study-specific conventions.

This MkDocs site is the web-readable mirror of that SOP plus implementation notes from the executable pipeline. It should not introduce new workflow rules that are absent from the SOP or executable configuration.

## Scope mirrored from the SOP

The documentation covers:

- Supported studies: BACPACS R1 Smart AFO and BACPACS R2 Spinal Stim.
- Study folder structure by participant, visit, and modality.
- File naming convention: `{study}_{participant_number}_{visit}_{modality}_{outcome}`.
- Raw-file validation and review.
- RawFile registration.
- First-pass modality processing.
- Downstream analysis processing from processed tables.
- CLI and GUI operation.
- Developer contract for adding new analysis methods.

## Authority order

When a fact appears in multiple places, use this order:

1. Approved SOP.
2. Executable configuration and tests.
3. MkDocs pages.
4. Supporting README or implementation notes.

If the SOP and code disagree, record the issue in the discrepancy log and resolve it before release.

## Known SOP-to-code implementation note

The SOP describes the general BACPACS filename pattern as:

```text
{study}_{participant_number}_{visit}_{modality}_{outcome}
```

The implementation stores R2 defaults in `Modality_Pipelines/config.json` and applies R1-specific overrides through `Modality_Pipelines/common/study_config.py`. This is intentional; the resolved study configuration is the runtime source used by validation, registration, processing, the CLI, and the GUI.
