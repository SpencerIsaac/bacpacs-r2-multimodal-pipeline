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

from collections.abc import Callable, Mapping, Sequence
from typing import Any

import scidb

from Modality_Pipelines.common.common_config import SCHEMA_KEYS, configure_scistack_database


def build_schema_filter(schema_filters: Mapping[str, Any]) -> dict[str, list[Any]]:
    """Normalize user filter kwargs for SciDB schema_filter.

    Omitted keys are intentionally left out so SciDB can discover available
    values from the database. Passing participant_number=["001"] limits that
    axis; passing no filters lets SciDB enumerate the full registered dataset.
    """
    normalized: dict[str, list[Any]] = {}
    for key in SCHEMA_KEYS:
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


def run_scistack_stage(
    fn: Callable,
    inputs: Mapping[str, Any],
    outputs: Sequence[type],
    schema_filters: Mapping[str, Any] | None = None,
    *,
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
    configure_scistack_database()
    schema_filter = build_schema_filter(schema_filters or {})

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
        schema_level=list(SCHEMA_KEYS),
    )
