"""Wide R1 HAM/TA EMG plots comparing AFO vs noAFO by side.

Reads the R1 CycleUnmatched export and writes four poster-friendly PNGs:
left HAM, right HAM, left TA, and right TA. Each plot shows AFO vs noAFO
over percent gait cycle.
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
OUTPUT_DIR = REPO_ROOT / "analysis_scripts" / "plots" / "r1_001_bl_ham_ta_afo_vs_noafo_by_side"
SIGNAL_GROUP = "delsys_normalized_time_normalized"
CONDITION_COLORS = {"AFO": "#ff7a1a", "noAFO": "#55c7df"}
SIGNALS = {
    "LHAM": ("HAM", "Left"),
    "RHAM": ("HAM", "Right"),
    "LTA": ("TA", "Left"),
    "RTA": ("TA", "Right"),
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
        & (df["signal_name"].isin(SIGNALS))
        & (df["condition"].isin(CONDITION_COLORS))
    ].copy()
    if df.empty:
        raise SystemExit("No R1 BL HAM/TA normalized EMG rows were found.")

    sns.set_theme(style="whitegrid", context="talk")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for signal_name in ("LHAM", "RHAM", "LTA", "RTA"):
        subset = df[df["signal_name"] == signal_name].copy()
        if subset.empty:
            continue
        muscle, side = SIGNALS[signal_name]
        fig, ax = plt.subplots(figsize=(10.5, 5.2), constrained_layout=True)
        draw_individual_cycles(ax, subset)
        draw_condition_means(ax, subset)
        ax.set_title(f"R1 001 BL {side} {muscle} - AFO vs noAFO", fontsize=18, weight="bold")
        ax.set_xlabel("Gait cycle (%)")
        ax.set_ylabel("Normalized EMG (EMG / visit max)")
        ax.set_xlim(0, 100)
        ax.set_ylim(bottom=0)
        ax.legend(title="Condition", loc="upper right", frameon=True)
        ax.grid(True, axis="both", color="0.86", linewidth=0.8)

        path = OUTPUT_DIR / f"r1_001_bl_{side.lower()}_{muscle.lower()}_afo_vs_noafo.png"
        fig.savefig(path, dpi=220, bbox_inches="tight")
        plt.close(fig)
        written.append(path)

    print(f"Wrote {len(written)} files to {OUTPUT_DIR}")
    for path in written:
        print(path)
    return 0


def draw_individual_cycles(ax, subset: pd.DataFrame) -> None:
    cycle_columns = ["condition", "speed", "trial", "cycle", "source_record_id"]
    for _, cycle_df in subset.groupby(cycle_columns, dropna=False, sort=False):
        condition = cycle_df["condition"].iloc[0]
        ax.plot(
            cycle_df["percent_gait_cycle"],
            cycle_df["value"],
            color=CONDITION_COLORS[condition],
            alpha=0.16,
            linewidth=0.9,
        )


def draw_condition_means(ax, subset: pd.DataFrame) -> None:
    mean_df = (
        subset.groupby(["condition", "percent_gait_cycle"], as_index=False, sort=True)["value"]
        .mean()
        .sort_values(["condition", "percent_gait_cycle"])
    )
    for condition in ("AFO", "noAFO"):
        condition_df = mean_df[mean_df["condition"] == condition]
        if condition_df.empty:
            continue
        ax.plot(
            condition_df["percent_gait_cycle"],
            condition_df["value"],
            color=CONDITION_COLORS[condition],
            linewidth=3.2,
            label=condition,
        )


def normalize_participant(value: object) -> str:
    text = str(value).strip()
    try:
        return str(int(float(text)))
    except ValueError:
        return text.lstrip("0") or text


if __name__ == "__main__":
    raise SystemExit(main())
