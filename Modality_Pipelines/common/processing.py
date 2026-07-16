"""Study-aware backend dispatch for first-pass modality processing."""

from __future__ import annotations

from typing import Any

from Modality_Pipelines.Cosmed_Pipeline.cosmed_pipeline import run_cosmed_processing
from Modality_Pipelines.Delsys_Pipeline.delsys_pipeline import run_delsys_processing
from Modality_Pipelines.GAITRite_Pipeline.gaitrite_pipeline import (
    run_gaitrite_cycle_distribution,
    run_gaitrite_loading,
)
from Modality_Pipelines.Xsens_Pipeline.xsens_pipeline import run_xsens_processing
from Modality_Pipelines.common.study_config import load_study_config


MODALITY_PROCESSORS = {
    "cosmed": run_cosmed_processing,
    "delsys": run_delsys_processing,
    "xsens": run_xsens_processing,
}


def run_gaitrite_processing(**schema_filters):
    """Run the full GAITRite first-pass path."""
    loading_result = run_gaitrite_loading(**schema_filters)
    cycle_result = run_gaitrite_cycle_distribution(**schema_filters)
    return {
        "loaded": loading_result,
        "cycle": cycle_result,
    }


MODALITY_PROCESSORS["gaitrite"] = run_gaitrite_processing


def run_modality_processing(
    study: str = "R2",
    modality: str = "all",
    participant_number=None,
    visit=None,
    test=None,
    condition=None,
    speed=None,
    trial=None,
    unprocessed_only: bool = True,
    overwrite: bool = False,
    dry_run: bool = False,
    **extra_options: Any,
):
    """Run first-pass processing for one or all supported modalities."""
    study_config = load_study_config(study)
    selected_modalities = list(MODALITY_PROCESSORS) if modality == "all" else [modality]
    skip_computed = unprocessed_only and not overwrite

    schema_filters = {
        "study": study_config.study,
        "participant_number": participant_number,
        "visit": visit,
        "test": test,
        "condition": condition,
        "speed": speed,
        "trial": trial,
        "dry_run": dry_run,
        "skip_computed": skip_computed,
        **extra_options,
    }

    results = {}
    for modality_key in selected_modalities:
        try:
            processor = MODALITY_PROCESSORS[modality_key]
        except KeyError as exc:
            raise KeyError(f"Unknown or unsupported modality {modality_key!r}") from exc
        results[modality_key] = processor(**schema_filters)
    return results
