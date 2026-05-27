#!/usr/bin/env python3
"""Regenerate fig_pareto_surface.pdf — two 2D scatter panels of the
(correctness, speed, fairness) design space from §VIII.

Aidan directive 2026-04-19: the 3D projection is hard to read at a
glance. Convert to two 2D panels instead:
  (a) correctness gap vs speed multiplier  — shows BBRv3 is the only
      starving point; every other design sits on the c=0 axis.
  (b) speed vs fairness, at correctness gap 0 — the F* locus traces
      a curve over W; Ideal sits at (1, 0) and is ruled out.

No text annotations on points; labels go in a single legend.

Design points and F* locus definition come from Thm 4 (§VIII.2)
and Thm 5 (§VIII.3) in the paper.

Usage: python3 figures/fig_pareto_surface.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

REPO = Path(__file__).resolve().parent.parent


# (name, correctness_gap c, speed_mult k, fairness_harm eta,
#  colour, marker, marker_size)
POINTS = [
    ("BBRv3",           1.0, 1.0, 0.00, "#d62728", "X", 110),
    ("F* (W=10)",       0.0, 2.2, 0.20, "#2ca02c", "o",  95),
    ("F* (W=20)",       0.0, 2.3, 0.10, "#2ca02c", "o",  95),
    ("Ideal",           0.0, 1.0, 0.00, "#1f77b4", "*", 160),
    ("Partial (A1)",    0.3, 1.5, 0.10, "#888888", "s",  80),
    ("Slow EWMA (A2)",  0.0, 4.0, 0.50, "#888888", "s",  80),
    ("CUBIC-like (A3)", 0.5, 1.0, 0.30, "#888888", "s",  80),
]

# F* locus from §VIII.2 closed form:
#   T_conv = ln(1/eps) / ln(W / (W-1)) at eps=0.1
#   k = T_conv / W
#   eta = 2/W  (Thm 5 harm envelope)
W_range = np.linspace(10.0, 40.0, 40)
eps = 0.1
T_conv = np.log(1.0 / eps) / np.log(W_range / (W_range - 1.0))
k_W = T_conv / W_range
eta_W = 2.0 / W_range


def main() -> None:
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(8.0, 3.3))

    # ── Panel (a): correctness gap vs speed multiplier ─────────────
    for name, c, k, eta, colour, marker, size in POINTS:
        axA.scatter([c], [k], color=colour, marker=marker,
                    s=size, edgecolors="black", linewidths=0.6, zorder=3)
    # Shade the c=0 Pareto wall to make the "everything lives on
    # c=0 except BBRv3" claim legible without text.
    axA.axvspan(-0.05, 0.05, color="#2ca02c", alpha=0.10, zorder=1)
    axA.set_xlabel("correctness gap\n(0 = correct, 1 = starves)", fontsize=9)
    axA.set_ylabel(r"speed multiplier $k = T_{\mathrm{conv}} / W$",
                   fontsize=9)
    axA.set_xlim(-0.15, 1.15)
    axA.set_ylim(0.4, 4.5)
    axA.set_title("(a) correctness vs speed", fontsize=10, pad=6)
    axA.grid(linestyle=":", alpha=0.4)

    # ── Panel (b): speed vs fairness on the c=0 plane ──────────────
    # Plot the F* locus as a curve, then only the c=0 design points
    # on top of it. BBRv3 does not appear in panel (b) because its
    # correctness gap is 1.
    axB.plot(k_W, eta_W, color="#2ca02c", linewidth=1.8, zorder=2,
             label=r"$F^{*}$ locus ($W\!\in\![10,40]$)")
    for name, c, k, eta, colour, marker, size in POINTS:
        if c > 0.05:
            continue  # panel (b) is the c=0 slice only
        axB.scatter([k], [eta], color=colour, marker=marker,
                    s=size, edgecolors="black", linewidths=0.6,
                    zorder=3, label=name)
    axB.set_xlabel(r"speed multiplier $k = T_{\mathrm{conv}} / W$",
                   fontsize=9)
    axB.set_ylabel(r"fairness harm $\eta$ (Ware 2019)", fontsize=9)
    axB.set_xlim(0.6, 4.5)
    axB.set_ylim(-0.03, 0.6)
    axB.set_title("(b) speed vs fairness, correctness gap = 0",
                  fontsize=10, pad=6)
    axB.grid(linestyle=":", alpha=0.4)
    axB.legend(loc="upper left", fontsize=7.5, frameon=False,
               handletextpad=0.4, borderaxespad=0.2)

    # ── Shared point legend at the bottom ──────────────────────────
    # Shows every design class in one row so the reader doesn't have
    # to consult both panels to decode the markers.
    shared = [
        Line2D([0], [0], marker="X", color="w", markerfacecolor="#d62728",
               markeredgecolor="black", markersize=9, label="BBRv3 (starves)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#2ca02c",
               markeredgecolor="black", markersize=9,
               label=r"$F^{*}$ (patched)"),
        Line2D([0], [0], marker="*", color="w", markerfacecolor="#1f77b4",
               markeredgecolor="black", markersize=12, label="Ideal (ruled out)"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="#888888",
               markeredgecolor="black", markersize=8, label="Hypothetical"),
    ]
    fig.legend(handles=shared, loc="lower center",
               bbox_to_anchor=(0.5, -0.08), ncol=4,
               frameon=False, fontsize=8.5)

    fig.tight_layout(rect=[0, 0.05, 1, 1])
    out = REPO / "figures" / "fig_pareto_surface.pdf"
    fig.savefig(out, bbox_inches="tight")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
