"""Seaborn plots for BACPACS matched gait-cycle exports.

This reads a long-form ``*_bacpacs_cycle_matched.csv`` export and writes
PNG/SVG figures for normalized EMG and Xsens time-normalized signals.

Example
-------
python analysis_scripts/plot_bacpacs_cycle_matched.py ^
  --input analysis_scripts/exports/20260717_r1_bacpacs_cycle_matched.csv ^
  --participant 1 --visit BL
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd

try:
    import matplotlib.pyplot as plt
    import seaborn as sns
except ModuleNotFoundError as exc:  # pragma: no cover - environment guidance
    missing = exc.name
    raise SystemExit(
        f"Missing plotting dependency: {missing}. Install plotting extras with:\n"
        "  .\\BAKPACS_env\\python.exe -m pip install matplotlib seaborn\n"
        "Then rerun this script."
    ) from exc

DEFAULT_SIGNAL_GROUPS = (
    "delsys_normalized_time_normalized",
    "xsens_time_normalized",
)
KEY_COLUMNS = ["participant_number", "visit", "test", "condition", "speed"]
MEAN_GROUP_COLUMNS = ["participant_number", "visit", "test", "speed"]
CYCLE_COLUMNS = ["source_record_id", "matched_cycle_index"]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = args.input or newest_export(Path("analysis_scripts") / "exports", "*_bacpacs_cycle_matched.csv")
    if source is None or not source.exists():
        raise SystemExit("Could not find a matched-cycle export. Pass --input path/to/*_bacpacs_cycle_matched.csv")

    df = pd.read_csv(source)
    df = filter_frame(df, args)
    validate_frame(df)
    if df.empty:
        raise SystemExit("No rows matched the requested filters.")

    output_dir = args.output_dir or source.parent.parent / "plots" / source.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    sns.set_theme(style="whitegrid", context="talk")
    written: list[Path] = []
    signal_groups = args.signal_group or list(DEFAULT_SIGNAL_GROUPS)
    for signal_group in signal_groups:
        group_df = df[df["signal_group"] == signal_group].copy()
        if group_df.empty:
            continue
        written.extend(write_mean_by_condition_plots(group_df, signal_group, output_dir, args))
        written.extend(write_overlay_plots(group_df, signal_group, output_dir, args))

    if not written:
        raise SystemExit("No plot files were written. Check --signal-group and filters.")

    print(f"Wrote {len(written)} figure files")
    for path in written:
        print(path)
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate seaborn plots from BACPACS CycleMatched exports.")
    parser.add_argument("--input", type=Path, help="Path to YYYYMMDD_*_bacpacs_cycle_matched.csv")
    parser.add_argument("--output-dir", type=Path, help="Directory for PNG/SVG plot outputs")
    parser.add_argument("--signal-group", action="append", choices=DEFAULT_SIGNAL_GROUPS + ("delsys_time_normalized",), help="Signal group to plot; repeat for multiple groups")
    parser.add_argument("--participant", help="Filter participant_number. 1 and 001 are treated as equivalent.")
    parser.add_argument("--visit", help="Filter visit, e.g. BL")
    parser.add_argument("--test", help="Filter test, e.g. 10MWT")
    parser.add_argument("--condition", help="Filter condition, e.g. AFO or noAFO")
    parser.add_argument("--speed", help="Filter speed, e.g. FV or SSV")
    parser.add_argument("--signals", nargs="+", help="Optional signal_name values to plot, e.g. LTA RTA")
    parser.add_argument("--col-wrap", type=int, default=4, help="Facet columns before wrapping")
    parser.add_argument("--formats", nargs="+", default=["png", "svg"], choices=["png", "svg", "pdf"], help="Figure formats to save")
    parser.add_argument("--no-overlay", action="store_true", help="Skip individual-cycle overlay plots")
    parser.add_argument("--no-mean", action="store_true", help="Skip mean-by-condition plots")
    return parser.parse_args(argv)


def newest_export(root: Path, pattern: str) -> Path | None:
    files = sorted(root.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    return files[0] if files else None


def filter_frame(df: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    out = df.copy()
    filters = {
        "participant_number": args.participant,
        "visit": args.visit,
        "test": args.test,
        "condition": args.condition,
        "speed": args.speed,
    }
    for column, value in filters.items():
        if value is None or column not in out.columns:
            continue
        if column == "participant_number":
            out = out[out[column].map(normalize_participant) == normalize_participant(value)]
        else:
            out = out[out[column].astype(str) == str(value)]
    if args.signals:
        keep = {str(signal) for signal in args.signals}
        out = out[out["signal_name"].astype(str).isin(keep)]
    return out


def validate_frame(df: pd.DataFrame) -> None:
    required = set(KEY_COLUMNS + ["signal_group", "signal_name", "percent_gait_cycle", "value"])
    missing = sorted(required.difference(df.columns))
    if missing:
        raise SystemExit(f"Input is missing required columns: {', '.join(missing)}")


def write_mean_by_condition_plots(df: pd.DataFrame, signal_group: str, output_dir: Path, args: argparse.Namespace) -> list[Path]:
    if args.no_mean:
        return []
    written: list[Path] = []
    for key, subset in df.groupby(MEAN_GROUP_COLUMNS, dropna=False, sort=True):
        if subset.empty:
            continue
        title_values = dict(zip(MEAN_GROUP_COLUMNS, key))
        title = title_text(title_values, signal_group, "condition mean")
        grid = sns.relplot(
            data=subset,
            x="percent_gait_cycle",
            y="value",
            hue="condition",
            col="signal_name",
            col_wrap=args.col_wrap,
            kind="line",
            estimator="mean",
            errorbar=("ci", 95),
            facet_kws={"sharey": False, "sharex": True},
            linewidth=2.2,
            height=3.0,
            aspect=1.3,
        )
        finish_grid(grid, title, y_label_for(signal_group))
        stem = "mean_by_condition_" + safe_join(title_values.values()) + "_" + safe_token(signal_group)
        written.extend(save_grid(grid, output_dir / "mean_by_condition", stem, args.formats))
    return written


def write_overlay_plots(df: pd.DataFrame, signal_group: str, output_dir: Path, args: argparse.Namespace) -> list[Path]:
    if args.no_overlay:
        return []
    written: list[Path] = []
    cycle_cols = [column for column in CYCLE_COLUMNS if column in df.columns]
    if not cycle_cols:
        cycle_cols = ["matched_cycle_index"]
        df = df.copy()
        df["matched_cycle_index"] = df.groupby(KEY_COLUMNS + ["signal_name"]).cumcount()

    for key, subset in df.groupby(KEY_COLUMNS, dropna=False, sort=True):
        if subset.empty:
            continue
        title_values = dict(zip(KEY_COLUMNS, key))
        title = title_text(title_values, signal_group, "individual cycles")
        grid = sns.relplot(
            data=subset,
            x="percent_gait_cycle",
            y="value",
            hue="condition",
            units=cycle_cols[0],
            col="signal_name",
            col_wrap=args.col_wrap,
            kind="line",
            estimator=None,
            facet_kws={"sharey": False, "sharex": True},
            alpha=0.22,
            linewidth=0.9,
            height=3.0,
            aspect=1.3,
            legend=False,
        )
        finish_grid(grid, title, y_label_for(signal_group))
        stem = "overlay_" + safe_join(title_values.values()) + "_" + safe_token(signal_group)
        written.extend(save_grid(grid, output_dir / "overlay", stem, args.formats))
    return written


def finish_grid(grid, title: str, ylabel: str) -> None:
    grid.set_axis_labels("Gait cycle (%)", ylabel)
    grid.set_titles("{col_name}")
    grid.figure.subplots_adjust(top=0.88)
    grid.figure.suptitle(title)
    for ax in grid.axes.flat:
        ax.set_xlim(0, 100)
        ax.axhline(0, color="0.4", linewidth=0.8, alpha=0.5)


def save_grid(grid, folder: Path, stem: str, formats: Iterable[str]) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for ext in formats:
        path = folder / f"{stem}.{ext}"
        grid.figure.savefig(path, dpi=180, bbox_inches="tight")
        written.append(path)
    plt.close(grid.figure)
    return written


def title_text(values: dict[str, object], signal_group: str, suffix: str) -> str:
    prefix = " | ".join(f"{key}={value}" for key, value in values.items())
    return f"{prefix} | {signal_group} | {suffix}"


def y_label_for(signal_group: str) -> str:
    labels = {
        "delsys_normalized_time_normalized": "EMG / visit max",
        "delsys_time_normalized": "EMG envelope",
        "xsens_time_normalized": "Joint angle",
    }
    return labels.get(signal_group, "value")


def normalize_participant(value: object) -> str:
    text = str(value).strip()
    try:
        return str(int(float(text)))
    except ValueError:
        return text.lstrip("0") or text


def safe_join(values: Iterable[object]) -> str:
    return "_".join(safe_token(value) for value in values)


def safe_token(value: object) -> str:
    if pd.isna(value):
        return "missing"
    text = str(value).strip()
    cleaned = "".join(char if char.isalnum() else "_" for char in text).strip("_")
    return cleaned or "missing"


if __name__ == "__main__":
    raise SystemExit(main())