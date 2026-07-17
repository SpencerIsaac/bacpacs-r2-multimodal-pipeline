"""Plot BACPACS matched gait-cycle exports.

Reads the long-form ``*_bacpacs_cycle_matched.csv`` export and writes
self-contained HTML/SVG plots. This intentionally depends only on pandas and
Python's standard library so it works in the repo BAKPACS_env even when
matplotlib/seaborn are not installed.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Iterable

import pandas as pd

DEFAULT_SIGNAL_GROUPS = (
    "delsys_normalized_time_normalized",
    "xsens_time_normalized",
)
GROUP_COLUMNS = ("participant_number", "visit", "test", "condition", "speed")
CYCLE_ID_COLUMNS = ("source_record_id", "matched_cycle_index")


@dataclass(frozen=True)
class PlotSpec:
    signal_group: str
    signal_names: tuple[str, ...]
    group_values: dict[str, object]
    output_path: Path
    mode: str


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = args.input
    if source is None:
        source = newest_export(Path("analysis_scripts") / "exports", "*_bacpacs_cycle_matched.csv")
    if source is None or not source.exists():
        raise SystemExit("Could not find a cycle matched export. Pass --input path/to/*_bacpacs_cycle_matched.csv")

    output_dir = args.output_dir or source.parent / "plots" / source.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(source)
    df = filter_frame(df, args)
    if df.empty:
        raise SystemExit("No rows matched the requested filters.")

    required = {"signal_group", "signal_name", "percent_gait_cycle", "value", *GROUP_COLUMNS}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise SystemExit(f"Input is missing required columns: {', '.join(missing)}")

    signal_groups = tuple(args.signal_group or DEFAULT_SIGNAL_GROUPS)
    written: list[Path] = []
    for signal_group in signal_groups:
        group_df = df[df["signal_group"] == signal_group].copy()
        if group_df.empty:
            continue
        for group_key, subset in group_df.groupby(list(GROUP_COLUMNS), dropna=False, sort=True):
            values = dict(zip(GROUP_COLUMNS, group_key))
            signal_names = tuple(sorted(str(name) for name in subset["signal_name"].dropna().unique()))
            if not signal_names:
                continue
            safe_name = "_".join(safe_token(values[col]) for col in GROUP_COLUMNS)
            signal_slug = safe_token(signal_group)
            output_path = output_dir / signal_slug / f"{safe_name}.html"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            spec = PlotSpec(signal_group, signal_names, values, output_path, args.mode)
            write_plot_html(subset, spec)
            written.append(output_path)

    index_path = output_dir / "index.html"
    write_index(index_path, source, written)
    print(f"Wrote {len(written)} plot files")
    print(index_path)
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot BACPACS matched gait-cycle exports.")
    parser.add_argument("--input", type=Path, help="Path to YYYYMMDD_*_bacpacs_cycle_matched.csv")
    parser.add_argument("--output-dir", type=Path, help="Folder for generated plot HTML files")
    parser.add_argument("--signal-group", action="append", choices=DEFAULT_SIGNAL_GROUPS + ("delsys_time_normalized",), help="Signal group to plot; repeat for multiple groups")
    parser.add_argument("--mode", choices=("overlay", "mean", "both"), default="both", help="Plot individual cycles, condition mean, or both")
    parser.add_argument("--participant", help="Filter participant_number")
    parser.add_argument("--visit", help="Filter visit")
    parser.add_argument("--test", help="Filter test")
    parser.add_argument("--condition", help="Filter condition")
    parser.add_argument("--speed", help="Filter speed")
    parser.add_argument("--max-panels", type=int, default=12, help="Maximum signals/subplots per HTML file")
    args = parser.parse_args(argv)
    return args


def newest_export(root: Path, pattern: str) -> Path | None:
    files = sorted(root.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    return files[0] if files else None


def filter_frame(df: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    filters = {
        "participant_number": args.participant,
        "visit": args.visit,
        "test": args.test,
        "condition": args.condition,
        "speed": args.speed,
    }
    out = df
    for column, value in filters.items():
        if value is None or column not in out.columns:
            continue
        out = out[out[column].astype(str) == str(value)]
    return out


def write_plot_html(df: pd.DataFrame, spec: PlotSpec) -> None:
    signals = spec.signal_names[:12]
    panel_svgs = []
    for signal_name in signals:
        signal_df = df[df["signal_name"].astype(str) == signal_name]
        panel_svgs.append(render_signal_panel(signal_df, signal_name, spec.mode))

    title = " | ".join(f"{key}={value}" for key, value in spec.group_values.items())
    cycle_count = count_cycles(df)
    body = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{escape(spec.signal_group)} {escape(title)}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
.header {{ margin-bottom: 18px; }}
.meta {{ color: #52606d; font-size: 14px; line-height: 1.5; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 20px; }}
.panel {{ border: 1px solid #d9e2ec; border-radius: 6px; padding: 10px; background: #fff; }}
.legend {{ font-size: 13px; color: #52606d; margin-top: 8px; }}
</style>
</head>
<body>
<div class="header">
<h1>{escape(spec.signal_group)}</h1>
<div class="meta">{escape(title)}<br>Mode: {escape(spec.mode)} | matched cycles: {cycle_count}</div>
</div>
<div class="grid">
{''.join(panel_svgs)}
</div>
</body>
</html>
"""
    spec.output_path.write_text(body, encoding="utf-8")


def render_signal_panel(df: pd.DataFrame, signal_name: str, mode: str) -> str:
    width, height = 480, 330
    left, right, top, bottom = 58, 16, 34, 44
    plot_w = width - left - right
    plot_h = height - top - bottom
    y_max = float(df["value"].max()) if not df.empty else 1.0
    y_min = float(df["value"].min()) if not df.empty else 0.0
    if y_min >= 0:
        y_min = 0.0
    if y_max == y_min:
        y_max = y_min + 1.0
    pad = (y_max - y_min) * 0.08
    y_min -= pad
    y_max += pad

    def sx(value: float) -> float:
        return left + value / 100.0 * plot_w

    def sy(value: float) -> float:
        return top + (1.0 - (value - y_min) / (y_max - y_min)) * plot_h

    parts = [
        '<div class="panel">',
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2:.1f}" y="21" text-anchor="middle" font-size="16" font-weight="700">{escape(signal_name)}</text>',
    ]
    for pct in (0, 20, 40, 60, 80, 100):
        x = sx(pct)
        parts.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top+plot_h}" stroke="#edf2f7"/>')
        parts.append(f'<text x="{x:.1f}" y="{top+plot_h+24}" text-anchor="middle" font-size="11">{pct}</text>')
    for idx in range(5):
        value = y_min + (y_max - y_min) * idx / 4
        y = sy(value)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+plot_w}" y2="{y:.1f}" stroke="#edf2f7"/>')
        parts.append(f'<text x="{left-8}" y="{y+4:.1f}" text-anchor="end" font-size="11">{value:.2f}</text>')
    parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_h}" stroke="#334e68"/>')
    parts.append(f'<line x1="{left}" y1="{top+plot_h}" x2="{left+plot_w}" y2="{top+plot_h}" stroke="#334e68"/>')

    colors = palette(df["condition"].dropna().astype(str).unique())
    if mode in ("overlay", "both"):
        for _, cycle_df in df.groupby(list(CYCLE_ID_COLUMNS), dropna=False, sort=False):
            condition = str(cycle_df["condition"].iloc[0])
            points = polyline_points(cycle_df, sx, sy)
            if points:
                parts.append(f'<polyline points="{points}" fill="none" stroke="{colors.get(condition, "#8a8f98")}" stroke-opacity="0.18" stroke-width="1"/>')

    if mode in ("mean", "both"):
        mean_df = df.groupby(["condition", "percent_gait_cycle"], dropna=False)["value"].mean().reset_index()
        for condition, condition_df in mean_df.groupby("condition", dropna=False, sort=True):
            condition_text = str(condition)
            points = polyline_points(condition_df, sx, sy)
            if points:
                parts.append(f'<polyline points="{points}" fill="none" stroke="{colors.get(condition_text, "#334e68")}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>')

    parts.append(f'<text x="{left+plot_w/2:.1f}" y="{height-8}" text-anchor="middle" font-size="12">Gait cycle (%)</text>')
    parts.append('</svg>')
    legend = " &nbsp; ".join(
        f'<span style="color:{colors[key]}; font-weight:700;">&#8212;</span> {escape(key)}'
        for key in sorted(colors)
    )
    parts.append(f'<div class="legend">{legend}</div>')
    parts.append('</div>')
    return "".join(parts)


def polyline_points(df: pd.DataFrame, sx, sy) -> str:
    ordered = df.sort_values("percent_gait_cycle")
    return " ".join(
        f"{sx(float(row.percent_gait_cycle)):.2f},{sy(float(row.value)):.2f}"
        for row in ordered.itertuples()
        if pd.notna(row.percent_gait_cycle) and pd.notna(row.value)
    )


def palette(values: Iterable[str]) -> dict[str, str]:
    base = ["#2F80ED", "#F2994A", "#219653", "#9B51E0", "#EB5757", "#00A3A3"]
    return {str(value): base[idx % len(base)] for idx, value in enumerate(sorted(set(values)))}


def count_cycles(df: pd.DataFrame) -> int:
    available = [column for column in CYCLE_ID_COLUMNS if column in df.columns]
    if not available:
        return 0
    return int(df[available].drop_duplicates().shape[0])


def safe_token(value: object) -> str:
    text = str(value).strip() if pd.notna(value) else "missing"
    cleaned = "".join(char if char.isalnum() else "_" for char in text).strip("_")
    return cleaned or "missing"


def write_index(index_path: Path, source: Path, written: list[Path]) -> None:
    links = "\n".join(
        f'<li><a href="{escape(path.relative_to(index_path.parent).as_posix())}">{escape(path.relative_to(index_path.parent).as_posix())}</a></li>'
        for path in sorted(written)
    )
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>BACPACS cycle plots</title></head>
<body style="font-family: Arial, sans-serif; margin: 24px;">
<h1>BACPACS cycle plots</h1>
<p>Source: <code>{escape(str(source))}</code></p>
<ul>{links}</ul>
</body></html>
"""
    index_path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())