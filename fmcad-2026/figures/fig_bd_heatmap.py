#!/usr/bin/env python3
"""Regenerate fig_bd_heatmap.pdf — $B \\times D$ residual heatmap.

Two-panel figure. Left: quiescent schedule residuals (seeded filter
drains once per $W$-window, so starvation is bounded above by
analytic $T$). Right: aggregating schedule (no drain guarantee, so
the simulator reports horizon-reached and the cell is empty). Reveals
which regime the sandwich bound is tight in.

Usage: python3 figures/fig_bd_heatmap.py
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parent.parent
RUNS = REPO / "experiments" / "runs"


def load(name: str) -> dict[tuple[float, float], float | None]:
    path = RUNS / name
    table: dict[tuple[float, float], list[float]] = {}
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            B = float(row["B"])
            D = float(row["D_ms"])
            r = row.get("residual_rtt", "")
            if not r:
                table.setdefault((B, D), [])
                continue
            try:
                table.setdefault((B, D), []).append(float(r))
            except ValueError:
                pass
    out: dict[tuple[float, float], float | None] = {}
    for k, v in table.items():
        out[k] = sum(v) / len(v) if v else None
    return out


quiet = load("b_d_grid_quiet_thr0.csv")
agg = load("b_d_grid_agg_thr0.csv")

Bs = sorted({B for B, _ in quiet.keys() | agg.keys()})
Ds = sorted({D for _, D in quiet.keys() | agg.keys()})

fig, (ax_q, ax_a) = plt.subplots(
    1, 2, figsize=(8.0, 3.4), gridspec_kw=dict(wspace=0.40)
)


def draw(ax, table, title):
    grid = np.full((len(Bs), len(Ds)), np.nan, dtype=float)
    for i, B in enumerate(Bs):
        for j, D in enumerate(Ds):
            v = table.get((B, D))
            if v is not None:
                grid[i, j] = v
    masked = np.ma.masked_invalid(grid)
    im = ax.imshow(masked, aspect="auto", cmap="viridis",
                   origin="lower")
    ax.set_xticks(range(len(Ds)))
    ax.set_xticklabels([f"{D:g}" for D in Ds])
    ax.set_yticks(range(len(Bs)))
    ax.set_yticklabels([f"{B:g}" for B in Bs])
    ax.set_xlabel("$D$ (ms)")
    ax.set_ylabel("$B$")
    ax.set_title(title, fontsize=10)
    # Only label cells that carry a value. Empty cells are rendered
    # as the masked colour (viridis "bad" = light grey by default)
    # and the caption explains them as horizon-reached — this keeps
    # the heatmap text clear of the colorbar tick labels.
    for i in range(len(Bs)):
        for j in range(len(Ds)):
            if not np.isnan(grid[i, j]):
                ax.text(j, i, f"{grid[i, j]:.0f}", ha="center",
                        va="center", color="white", fontsize=8)
    return im


im_q = draw(ax_q, quiet, "Quiescent schedule (mean residual, RTT)")
im_a = draw(ax_a, agg, "Aggregating schedule (horizon-reached)")

cbar = fig.colorbar(im_q, ax=[ax_q, ax_a], shrink=0.7,
                    pad=0.06, label="residual (RTT)")

plt.subplots_adjust(left=0.08, right=0.9, top=0.88, bottom=0.2)

out = REPO / "figures" / "fig_bd_heatmap.pdf"
plt.savefig(out, format="pdf", bbox_inches="tight", pad_inches=0.25)
print(f"wrote {out}")
