"""Wide R1 EMG plots with left vs right muscle traces by gait cycle.

Reads the long-form CycleUnmatched export and writes one plot per
muscle/condition/speed. Each plot overlays individual cycles faintly and
draws the side mean prominently.
"""

from __future__ import annotations

from pathlib import Path

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


REPO_ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = REPO_ROOT / "analysis_scripts" / "exports" / "20260717_r1_bacpacs_cycle_unmatched.csv"
OUTPUT_DIR = REPO_ROOT / "analysis_scripts" / "plots" / "r1_001_bl_emg_left_right_by_muscle"
SIGNAL_GROUP = "delsys_normalized_time_normalized"
SIDE_COLORS = {"Left": "#ff7a1a", "Right": "#55c7df"}
MUSCLES = {
    "HAM": ("LHAM", "RHAM"),
    "MG": ("LMG", "RMG"),
    "RF": ("LRF", "RRF"),
    "TA": ("LTA", "RTA"),
    "VL": ("LVL", "RVL"),
}
USE_COLUMNS = [
    "participant_number",
    "visit",
    "test",
    "condition",
    "speed",
    "trial",
    "cycle",
    "source_record_id",
    "signal_group",
    "signal_name",
    "percent_gait_cycle",
    "value",
]


def main() -> int:
    if not INPUT_CSV.exists():
        raise SystemExit(f"Missing export: {INPUT_CSV}")

    df = pd.read_csv(INPUT_CSV, usecols=USE_COLUMNS)
    df = df[
        (df["signal_group"] == SIGNAL_GROUP)
        & (df["participant_number"].map(normalize_participant) == "1")
        & (df["visit"].astype(str) == "BL")
    ].copy()
    df = add_muscle_side(df)
    df = df.dropna(subset=["muscle", "side", "percent_gait_cycle", "value"])
    if df.empty:
        raise SystemExit("No paired R1 BL normalized EMG rows were found.")

    sns.set_theme(style="whitegrid", context="talk")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for key, subset in df.groupby(["test", "condition", "speed", "muscle"], sort=True, dropna=False):
        test, condition, speed, muscle = key
        if subset.empty:
            continue
        fig, ax = plt.subplots(figsize=(14, 5.2), constrained_layout=True)
        draw_individual_cycles(ax, subset)
        draw_side_means(ax, subset)
        ax.set_title(f"R1 001 BL {test} {condition} {speed} - {muscle}", fontsize=18, weight="bold")
        ax.set_xlabel("Gait cycle (%)")
        ax.set_ylabel("Normalized EMG (EMG / visit max)")
        ax.set_xlim(0, 100)
        ax.set_ylim(bottom=0)
        ax.legend(title="Side", loc="upper right", frameon=True)
        ax.grid(True, axis="both", color="0.86", linewidth=0.8)

        stem = "_".join(safe_token(part) for part in ("r1_001_bl", test, condition, speed, muscle, "left_vs_right"))
        for ext in ("png",):
            path = OUTPUT_DIR / f"{stem}.{ext}"
            fig.savefig(path, dpi=220, bbox_inches="tight")
            written.append(path)
        plt.close(fig)

    print(f"Wrote {len(written)} files to {OUTPUT_DIR}")
    for path in written:
        print(path)
    return 0


def add_muscle_side(df: pd.DataFrame) -> pd.DataFrame:
    signal_map = {}
    for muscle, (left_signal, right_signal) in MUSCLES.items():
        signal_map[left_signal] = (muscle, "Left")
        signal_map[right_signal] = (muscle, "Right")

    mapped = df["signal_name"].map(signal_map)
    df["muscle"] = mapped.map(lambda value: value[0] if isinstance(value, tuple) else None)
    df["side"] = mapped.map(lambda value: value[1] if isinstance(value, tuple) else None)
    return df


def draw_individual_cycles(ax, subset: pd.DataFrame) -> None:
    cycle_columns = ["condition", "speed", "trial", "cycle", "source_record_id", "side"]
    for _, cycle_df in subset.groupby(cycle_columns, dropna=False, sort=False):
        side = cycle_df["side"].iloc[0]
        ax.plot(
            cycle_df["percent_gait_cycle"],
            cycle_df["value"],
            color=SIDE_COLORS[side],
            alpha=0.16,
            linewidth=0.9,
        )


def draw_side_means(ax, subset: pd.DataFrame) -> None:
    mean_df = (
        subset.groupby(["side", "percent_gait_cycle"], as_index=False, sort=True)["value"]
        .mean()
        .sort_values(["side", "percent_gait_cycle"])
    )
    for side, side_df in mean_df.groupby("side", sort=True):
        ax.plot(
            side_df["percent_gait_cycle"],
            side_df["value"],
            color=SIDE_COLORS[side],
            linewidth=3.2,
            label=side,
        )


def normalize_participant(value: object) -> str:
    text = str(value).strip()
    try:
        return str(int(float(text)))
    except ValueError:
        return text.lstrip("0") or text


def safe_token(value: object) -> str:
    text = str(value).strip()
    cleaned = "".join(char if char.isalnum() else "_" for char in text).strip("_")
    return cleaned or "missing"


if __name__ == "__main__":
    raise SystemExit(main())
