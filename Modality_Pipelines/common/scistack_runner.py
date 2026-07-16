"""
Shared SciStack execution helpers for modality pipeline stages.

@author shensley01
@version 0.2.0
@last_updated 2026-07-06
@change_log
    - 2026-07-06 v0.1.0: Added centralized scidb.for_each wrapper using
      schema_filter/schema_level, track_lineage=True, and skip_computed=True.
"""

from __future__ import annotations

import builtins
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
import os
from pathlib import Path
from typing import Any

import pandas as pd

import scidb

from Modality_Pipelines.common.common_config import SCHEMA_KEYS, configure_scistack_database
from Modality_Pipelines.common.study_config import load_study_config


def build_schema_filter(schema_filters: Mapping[str, Any]) -> dict[str, list[Any]]:
    """Normalize user filter kwargs for SciDB schema_filter.

    Omitted keys are intentionally left out so SciDB can discover available
    values from the database. Passing participant_number=["001"] limits that
    axis; passing no filters lets SciDB enumerate the full registered dataset.
    """
    normalized: dict[str, list[Any]] = {}
    schema_keys = schema_filters.get("_schema_keys", SCHEMA_KEYS)
    for key in schema_keys:
        if key not in schema_filters:
            continue
        value = schema_filters[key]
        if value is None:
            continue
        if isinstance(value, str):
            normalized[key] = [value]
        else:
            try:
                values = list(value)
            except TypeError:
                values = [value]
            if values:
                normalized[key] = values
    return normalized


STAGE_OPTION_KEYS = {
    "as_table",
    "database_path",
    "distribute",
    "dry_run",
    "save",
    "skip_computed",
    "track_lineage",
    "where",
}


def split_stage_kwargs(kwargs: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split schema filters from SciStack execution options."""
    schema_filters: dict[str, Any] = {}
    stage_options: dict[str, Any] = {}
    for key, value in kwargs.items():
        if key in STAGE_OPTION_KEYS:
            stage_options[key] = value
        else:
            schema_filters[key] = value
    return schema_filters, stage_options


@contextmanager
def _redirect_scifor_diag_log():
    """Patch SciStack diagnostic log paths/encodings during stage execution.

    Some scifor builds append to /tmp/scihist_diag.log, which can be missing or
    unwritable on Windows. SciDB also opens scidb.log without an explicit
    encoding, so Windows may choose cp1252 and fail on Unicode log separators.
    """
    log_dir = Path(__file__).resolve().parents[2] / ".scistack_logs"
    log_dir.mkdir(exist_ok=True)
    redirected_path = log_dir / "scihist_diag.log"
    original_open = builtins.open

    def redirected_open(file, *args, **kwargs):
        target = file
        if isinstance(file, (str, os.PathLike)) and os.fspath(file).replace("\\", "/") == "/tmp/scihist_diag.log":
            target = redirected_path

        mode = args[0] if args else kwargs.get("mode", "r")
        is_text_write = "b" not in mode and any(flag in mode for flag in ("a", "w", "x"))
        if is_text_write and "encoding" not in kwargs:
            kwargs["encoding"] = "utf-8"
            kwargs.setdefault("errors", "replace")

        return original_open(target, *args, **kwargs)

    builtins.open = redirected_open
    try:
        yield
    finally:
        builtins.open = original_open


def run_scistack_stage(
    fn: Callable,
    inputs: Mapping[str, Any],
    outputs: Sequence[type],
    schema_filters: Mapping[str, Any] | None = None,
    *,
    study: str = "R2",
    database_path=None,
    distribute: bool = False,
    skip_computed: bool = True,
    track_lineage: bool = True,
    dry_run: bool = False,
    save: bool = True,
    as_table: list[str] | bool | None = None,
    where=None,
):
    """Run one pipeline stage through SciDB-owned iteration and lineage.

    This is the preferred wrapper for modality processing stages. It keeps the
    actual loader/filter function plain Python, but delegates dataset iteration,
    input loading, output saving, duplicate skipping, and provenance tracking to
    ``scidb.for_each``.
    """
    study_config = load_study_config(study)
    database = configure_scistack_database(database_path, study_config=study_config)
    resolved_schema_filters = dict(schema_filters or {})
    resolved_schema_filters["_schema_keys"] = study_config.schema_keys
    schema_filter = build_schema_filter(resolved_schema_filters)

    if _inputs_are_empty(database, inputs):
        return pd.DataFrame()

    with _redirect_scifor_diag_log():
        return scidb.for_each(
            fn,
            inputs=dict(inputs),
            outputs=list(outputs),
            dry_run=dry_run,
            save=save,
            as_table=as_table,
            distribute=distribute,
            where=where,
            track_lineage=track_lineage,
            skip_computed=skip_computed,
            schema_filter=schema_filter,
            schema_level=list(study_config.schema_keys),
        )

def _inputs_are_empty(database, inputs: Mapping[str, Any]) -> bool:
    """Return True when every SciDB table input has no registered rows."""
    if not inputs:
        return False
    checked = False
    for input_source in inputs.values():
        if not isinstance(input_source, type):
            continue
        checked = True
        try:
            rows = database.load_all_as_df(input_source, include_rid=True)
        except Exception as exc:
            if _looks_like_missing_table(exc):
                return True
            raise
        if not rows.empty:
            return False
    return checked


def _looks_like_missing_table(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}"
    return "CatalogException" in text or "does not exist" in text or "not found" in text
