#!/usr/bin/env python3
"""fig_fstar_panel.py — F* vs BBRv3 A/B panel (paper Figure 3).

Reads the four b_d_grid CSVs produced by:
  experiments/b_d_grid.py --schedule {aggregating,quiescent}
                          --filter   {bbrv3,fstar}

and emits a single-panel grouped bar chart that reports the fraction
of cells (B, D, seed) that starve under each (schedule, filter)
combination. Four bars total:

    (agg,   BBRv3)   (agg,   F*)
    (quiet, BBRv3)   (quiet, F*)

The headline reading is the right-hand pair: under the quiescent
schedule that drains BBRv3's windowed-max filter to zero, F*
(burst-normalized samples + EWMA replacement of the max) holds
pacing_rate strictly positive. Same state machine modulo one sub-
step swap; opposite verdict.

Build:
    python3 experiments/figures/fig_fstar_panel.py \
        --out figures/fig_fstar_panel.pdf
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import sys


def _starvation_rate(csv_path: pathlib.Path) -> float:
    rows = list(csv.DictReader(csv_path.open()))
    if not rows:
        return 0.0
    starved = sum(1 for r in rows if r.get("reason") == "starvation_detected")
    return 100.0 * starved / len(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", default="experiments/runs")
    ap.add_argument("--out", default="figures/fig_fstar_panel.pdf")
    args = ap.parse_args()

    runs = pathlib.Path(args.runs_dir)
    matrix = {
        ("BBRv3", "aggregating"): runs / "b_d_grid_bbrv3_agg.csv",
        ("BBRv3", "quiescent"):   runs / "b_d_grid_bbrv3_quiet.csv",
        ("F*",    "aggregating"): runs / "b_d_grid_fstar_agg.csv",
        ("F*",    "quiescent"):   runs / "b_d_grid_fstar_quiet.csv",
    }
    for (filt, sched), p in matrix.items():
        if not p.exists():
            print(f"[fig_fstar_panel] missing {p} — rerun b_d_grid.py "
                  f"--filter={filt.lower()} --schedule={sched}", file=sys.stderr)
            return 2

    # Build the 4 data points.
    cells = {k: _starvation_rate(p) for k, p in matrix.items()}
    print("[fig_fstar_panel] starvation rates (%):")
    for k, v in cells.items():
        print(f"  {k[0]:6s} {k[1]:12s} {v:.1f}%")

    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("[fig_fstar_panel] matplotlib missing — pip install matplotlib", file=sys.stderr)
        return 2

    filters = ["BBRv3", "F*"]
    schedules = ["aggregating", "quiescent"]
    x = np.arange(len(schedules))
    width = 0.35

    # Two bars per schedule group.
    bbrv3_vals = [cells[("BBRv3", s)] for s in schedules]
    fstar_vals = [cells[("F*",    s)] for s in schedules]

    # Match paper voice: grayscale, no color, simple.
    fig, ax = plt.subplots(figsize=(5.0, 3.0))
    bars1 = ax.bar(x - width/2, bbrv3_vals, width,
                    label="BBRv3 (windowed-max)", color="0.55",
                    edgecolor="black", linewidth=0.8)
    bars2 = ax.bar(x + width/2, fstar_vals, width,
                    label=r"$F^{*}$ (burst-norm $+$ EWMA)",
                    color="white", edgecolor="black", linewidth=0.8, hatch="//")

    # Annotate each bar with its percent value.
    for bar, val in list(zip(bars1, bbrv3_vals)) + list(zip(bars2, fstar_vals)):
        ax.annotate(f"{val:.0f}%",
                    xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(["aggregating\nACK schedule", "quiescent\nACK schedule"])
    ax.set_ylabel("cells starved (\\%)")
    ax.set_ylim(0, 110)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.legend(loc="upper left", frameon=False, fontsize=8)

    # Minimalist frame.
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle=":", alpha=0.5)

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    print(f"[fig_fstar_panel] wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
