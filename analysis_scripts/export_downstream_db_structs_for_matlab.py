"""Export downstream SciDB records as structured JSON for MATLAB table creation.

This is an intermediate helper used by export_downstream_db_structs_to_mat.m.
It reads the derived analysis tables directly from SciDB and writes one JSON
file per table. The JSON keeps one row per DB analysis object and preserves
nested structs/arrays instead of flattening signals into point rows.
"""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from Modality_Pipelines.common import downstream_analysis as da

TABLES = {
    "trial": "bacpacs_trial_structured.json",
    "cycle_unmatched": "bacpacs_cycle_unmatched_structured.json",
    "cycle_matched": "bacpacs_cycle_matched_structured.json",
    "visit": "bacpacs_visit_structured.json",
    "issue": "bacpacs_analysis_issues_structured.json",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", default="R1", choices=["R1", "R2"])
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--database-path")
    for key in da.SCHEMA_KEYS:
        parser.add_argument(f"--{key.replace('_', '-')}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    filters = {
        key: getattr(args, key)
        for key in da.SCHEMA_KEYS
        if getattr(args, key) not in (None, "")
    }
    if args.database_path:
        filters["database_path"] = args.database_path
    ctx = da._context(args.study, filters)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "study": args.study,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "filters": filters,
        "tables": {},
    }
    for table_key, filename in TABLES.items():
        frame = da._load_table(ctx, table_key)
        rows = [_record_to_structured_row(row) for _, row in frame.iterrows()]
        path = args.output_dir / filename
        path.write_text(json.dumps(rows, allow_nan=False), encoding="utf-8")
        manifest["tables"][table_key] = {
            "json_path": str(path),
            "rows": len(rows),
            "filename": filename,
        }

    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


def _record_to_structured_row(row: pd.Series) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in da.SCHEMA_KEYS:
        if key in row.index:
            out[key] = _json_safe(da._clean_schema_value(row.get(key)))
    if "__record_id" in row.index:
        out["source_record_id"] = _json_safe(row.get("__record_id"))
    data = da._row_value(row, "data")
    if isinstance(data, Mapping):
        for key, value in data.items():
            out[_matlab_name(key)] = _json_safe(value)
    return out


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                return _json_safe(json.loads(stripped))
            except json.JSONDecodeError:
                return value
        return value
    if isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        val = float(value)
        return None if not math.isfinite(val) else val
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.isoformat()
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.reshape(-1).tolist()]
    if isinstance(value, pd.Series):
        return {_matlab_name(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, pd.DataFrame):
        return [_json_safe(record) for record in value.to_dict(orient="records")]
    if isinstance(value, Mapping):
        return {_matlab_name(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_safe(item) for item in value]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def _matlab_name(name: Any) -> str:
    text = str(name)
    cleaned = []
    for char in text:
        cleaned.append(char if char.isalnum() or char == "_" else "_")
    out = "".join(cleaned).strip("_") or "field"
    if out[0].isdigit():
        out = "x" + out
    return out


if __name__ == "__main__":
    raise SystemExit(main())