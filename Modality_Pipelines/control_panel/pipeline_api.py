"""Facade functions that give the UI one stable pipeline API."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

def register_all_raw_files(**kwargs) -> dict[str, int]:
    """Register all valid raw files discovered by the shared manifest."""
    from Modality_Pipelines.common.manifest import register_raw_files

    return register_raw_files(**kwargs)


def preview_raw_file_manifest(**kwargs):
    """Build the dry-run manifest used by Raw File Review."""
    from Modality_Pipelines.common.manifest import build_raw_file_manifest

    return build_raw_file_manifest(**kwargs)


def run_modality_processing(modality: str, **schema_filters):
    """Run one modality through the shared backend processing dispatcher."""
    from Modality_Pipelines.common.processing import run_modality_processing as run_backend_modality_processing

    return run_backend_modality_processing(modality=modality, **schema_filters)


def process_single_raw_file(modality: str, file_path: str | Path):
    """Run one direct file loader/processor without saving to SciDB."""
    processors: dict[str, Callable[..., Any]] = {
        "gaitrite": _load_runner("Modality_Pipelines.GAITRite_Pipeline.load_gaitrite", "process_gaitrite_raw_file"),
        "xsens": _load_runner("Modality_Pipelines.Xsens_Pipeline.process_xsens", "process_xsens_raw_file"),
        "delsys": _load_runner("Modality_Pipelines.Delsys_Pipeline.process_delsys", "process_delsys_raw_file"),
        "cosmed": _load_runner("Modality_Pipelines.Cosmed_Pipeline.process_cosmed", "process_cosmed_raw_file"),
    }
    key = modality.lower()
    if key not in processors:
        raise ValueError(f"No single-file processor is available for modality {modality!r}.")
    return processors[key](file_path)


def _load_runner(module_name: str, function_name: str) -> Callable[..., Any]:
    def runner(*args, **kwargs):
        module = __import__(module_name, fromlist=[function_name])
        return getattr(module, function_name)(*args, **kwargs)

    return runner

