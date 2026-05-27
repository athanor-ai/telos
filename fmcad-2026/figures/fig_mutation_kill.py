#!/usr/bin/env python3
"""Regenerate fig_mutation_kill.pdf — mutation-kill coverage matrix.

Rows are the 10 mutations in experiments/mutation_sweep.py. Columns are
the four verification layers (Lean 4, EBMC $k$-induction, Hypothesis
property tests, CPU simulator). Green cell = mutation is rejected by
that layer; red = mutation passes. The catalogue is designed so every
mutation is rejected by at least two layers; no mutation is rejected
by Lean alone.

Matches the style of credit-assignment-formal-bench/figures/
fig_mutation_kill_rate.pdf: color-coded Y/N cells + a layer-totals
summary on the right.

Usage: python3 figures/fig_mutation_kill.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np

REPO = Path(__file__).resolve().parent.parent

# (mutation_id, short description, location) — source of truth is
# experiments/mutation_sweep.py. Kept here for figure-render
# convenience; a check in scripts/check_paper.py could verify this
# matches the simulator's catalogue file in a future pass.
mutations = [
    ("M01", r"Off-by-one on $W$",         "onsetTime"),
    ("M02", r"Drop $-2$ in $B/D-2$",       "onsetTime"),
    ("M03", r"Swap $B$ and $D$",           "onsetTime"),
    ("M04", r"Remove $c$ constant",        "onsetTime"),
    ("M05", r"Weaken min-RTT monotone",    "Lemma 1"),
    ("M06", r"Flip inequality Lemma 2",    r"ack\_agg"),
    ("M07", r"Drop $B > 2D$ hypothesis",   r"bbr3\_onset"),
    ("M08", r"Break Arun boundary",        r"arun\_special"),
    ("M09", r"3-flow quorum to any-flow",  r"three\_flow"),
    ("M10", r"Pacing-rate off by one",     "Trace.rate"),
]

# catch[i][j] = 1 iff mutation i is rejected by layer j.
# Columns: L1=Lean, L2=EBMC, L3=Hypothesis, L4=CPU simulator.
# Matches sections/appendix.tex Table 3 (tab:mutations).
catch = np.array([
    [1, 1, 1, 1],
    [1, 1, 1, 1],
    [1, 1, 1, 1],
    [1, 1, 0, 1],
    [1, 1, 0, 0],
    [1, 1, 1, 0],
    [1, 0, 1, 1],
    [1, 1, 0, 0],
    [1, 1, 1, 1],
    [0, 1, 1, 1],
])

layer_names = ["L1", "L2", "L3", "L4"]
# Long names go in the caption + a legend block in panel (b) axis
# title, so column-header collisions are impossible.
layer_long = {
    "L1": "Lean 4",
    "L2": "EBMC $k$-ind",
    "L3": "Hypothesis",
    "L4": "CPU sim",
}
n_rows = len(mutations)
n_cols = len(layer_names)

caught_green = "#3e8e41"
missed_red = "#c44a3c"

fig, (ax_a, ax_b) = plt.subplots(
    1, 2, figsize=(10.2, 4.6),
    gridspec_kw=dict(width_ratios=[1.0, 0.45], wspace=0.45),
)

# ─── Panel (a): per-mutation × layer matrix ───────────────────────
for i in range(n_rows):
    y = n_rows - 1 - i
    for j in range(n_cols):
        colour = caught_green if catch[i, j] else missed_red
        letter = "Y" if catch[i, j] else "N"
        ax_a.add_patch(Rectangle((j, y), 1, 1,
                                  facecolor=colour, edgecolor="white",
                                  linewidth=2.2))
        ax_a.text(j + 0.5, y + 0.5, letter, ha="center", va="center",
                  color="white", fontweight="bold", fontsize=11)

ax_a.set_xlim(0, n_cols)
ax_a.set_ylim(0, n_rows)
ax_a.set_xticks(np.arange(n_cols) + 0.5)
ax_a.set_xticklabels(layer_names, fontsize=9)
ax_a.set_yticks(np.arange(n_rows) + 0.5)
ax_a.set_yticklabels(
    [f"{m[0]}  {m[1]}" for m in reversed(mutations)], fontsize=9,
)
ax_a.tick_params(axis="both", length=0)
ax_a.set_aspect("equal")
for s in ("top", "right", "bottom", "left"):
    ax_a.spines[s].set_visible(False)
ax_a.set_title("(a) Per-mutation rejection", fontsize=10, pad=10)

# ─── Panel (b): per-layer totals ──────────────────────────────────
totals = catch.sum(axis=0)
bar_colours = [caught_green] * n_cols
ax_b.barh(np.arange(n_cols), totals[::-1], color=bar_colours,
          edgecolor="white", height=0.6)
for i, v in enumerate(totals[::-1]):
    ax_b.text(v + 0.15, i, f"{int(v)}/{n_rows}", va="center",
              fontsize=10, color="black")
ax_b.set_yticks(np.arange(n_cols))
ax_b.set_yticklabels(layer_names[::-1], fontsize=9)
ax_b.set_xlabel("mutations rejected")
ax_b.set_xlim(0, n_rows + 1.5)
ax_b.set_title("(b) Coverage per layer", fontsize=10, pad=10)
ax_b.spines["top"].set_visible(False)
ax_b.spines["right"].set_visible(False)
ax_b.tick_params(axis="y", length=0)

# Layer legend block: "L1 = Lean 4, L2 = EBMC k-ind, ...".
# Draws below both panels so it doesn't collide with column headers.
legend_txt = ",  ".join(f"{k} = {v}" for k, v in layer_long.items())

plt.tight_layout()
# Place legend text AFTER tight_layout so its position is relative
# to the final laid-out figure; then save with generous padding so
# the legend is inside the page margin.
fig.text(0.5, 0.015, legend_txt, ha="center", va="bottom", fontsize=8.5)
out = REPO / "figures" / "fig_mutation_kill.pdf"
plt.savefig(out, format="pdf", bbox_inches="tight", pad_inches=0.25)
print(f"wrote {out} (rows={n_rows}, layers={n_cols}, "
      f"min_rejectors_per_row={int(catch.sum(axis=1).min())})")
