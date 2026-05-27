#!/usr/bin/env python3
"""fig_residual.py --- ATH-343 output: rebuild the headline residual
figure from the B/D grid CSV.

Input:  experiments/runs/<stamp>/layer4_sim_residuals.csv
Output: figures/fig_residual.pdf

Figure spec (one page, ~0.98 linewidth):
  Left panel:  empirical T_emp (y) vs analytic T(B, D) (x) across all
               12000 cells. Scatter with error bars (median + IQR per
               cell). Diagonal line y = x. Pearson correlation r in
               corner.
  Right panel: residual T_emp - T_analytic as a function of B/D, with
               a horizontal band at +-10% of T_analytic. Cells outside
               the band are highlighted.
  Caption: the sandwich-bound closure story for the paper's Section 4.

Status: **scaffold**. Matplotlib import and input-CSV parse land after
ATH-343 produces the first run.
"""
from __future__ import annotations

import argparse
import pathlib
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="layer4_sim_residuals.csv")
    ap.add_argument("--out", required=True, help="output PDF path")
    args = ap.parse_args()

    csv_path = pathlib.Path(args.input)
    if not csv_path.exists():
        print(f"ERROR: input CSV missing: {csv_path}", file=sys.stderr)
        return 1

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import csv
    except ImportError as e:
        print(f"ERROR: matplotlib not available: {e}", file=sys.stderr)
        return 1

    rows = list(csv.DictReader(csv_path.open()))
    if not rows:
        print(f"ERROR: input CSV empty", file=sys.stderr)
        return 1

    # Scaffold: draw a single placeholder axis with the ATH-343-pending
    # note, so the figure builds end-to-end even before real data.
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.5))
    for ax in axs:
        ax.text(0.5, 0.5, "ATH-343 pending\n(scaffold)",
                ha="center", va="center", transform=ax.transAxes,
                fontsize=12, color="grey")
        ax.set_xticks([])
        ax.set_yticks([])
    axs[0].set_title("T_emp vs T_analytic")
    axs[1].set_title("residual vs B/D")
    fig.tight_layout()
    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, format="pdf")
    print(f"[fig_residual] wrote scaffold placeholder to {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
