#!/usr/bin/env python3
"""fig_proof_dag.py — Lean 4 proof-dependency DAG across all four CCAs.

Four panels in a 2x2 grid:
  (a) BBRv3 negative theorem: 8 supporting lemmas + starves_within.
  (b) F* positive theorem: 3 supporting lemmas + no_starvation_under_F_star.
  (c) CUBIC + Reno positive theorems: shared 2-step pattern (cwnd_floor ->
      pacing_rate >= MSS) instantiated twice.
  (d) KernelFidelity: kernel_fidelity_preserves_onset_bound reduces to (a).

All nodes closed (Aidan directive 2026-04-20: figures must reflect full
scope of the tool, not just BBRv3). Caption in main.tex carries the
module + line-count per panel.

Build:
  python3 experiments/figures/fig_proof_dag.py \
      --out figures/fig_proof_dag.pdf
"""
from __future__ import annotations

import argparse
import pathlib
import sys


NEGATIVE_NODES = [
    ("minrtt_mono",    "minrtt_filt\nmonotone"),
    ("ack_agg",        "ack_agg\ninflates"),
    ("bd_gt_two",      "$B/D > 2$\nunder $hB$"),
    ("cwnd_cap",       "cwnd_cap\ninsufficient"),
    ("probe_rtt",      "probeRTT\nperiod"),
    ("c_deriv",        "$c$-value\nderivation"),
    ("onset_upper",    "onset\nupper bound"),
    ("onset_lower",    "onset\nlower bound"),
    ("starves_within", "starves_within\n(MAIN)"),
]
NEGATIVE_EDGES = [
    ("starves_within", "onset_upper"),
    ("starves_within", "onset_lower"),
    ("onset_upper",    "minrtt_mono"),
    ("onset_upper",    "ack_agg"),
    ("onset_upper",    "cwnd_cap"),
    ("onset_upper",    "probe_rtt"),
    ("onset_upper",    "c_deriv"),
    ("onset_lower",    "minrtt_mono"),
    ("onset_lower",    "c_deriv"),
    ("ack_agg",        "bd_gt_two"),
    ("cwnd_cap",       "bd_gt_two"),
]
NEGATIVE_POS = {
    "starves_within":  (12.5, 7.5),
    "onset_upper":     (6.0, 5.0),
    "onset_lower":     (18.5, 5.0),
    "minrtt_mono":     (0.0, 2.5),
    "ack_agg":         (6.0, 2.5),
    "cwnd_cap":        (12.5, 2.5),
    "probe_rtt":       (18.5, 2.5),
    "c_deriv":         (24.5, 2.5),
    "bd_gt_two":       (9.0, 0.0),
}

POSITIVE_NODES = [
    ("ewma_pos",       "ewma preserves\npositivity"),
    ("step_patched",   "step_patched\npreserves $>0$"),
    ("cwnd_preserved", "cwnd_gain\npreserved"),
    ("no_starvation",  "no_starvation\n$F^*$ (MAIN)"),
]
POSITIVE_EDGES = [
    ("no_starvation", "step_patched"),
    ("no_starvation", "cwnd_preserved"),
    ("step_patched",  "ewma_pos"),
]
POSITIVE_POS = {
    "no_starvation":   (6.0, 6.0),
    "step_patched":    (1.5, 3.0),
    "cwnd_preserved":  (10.5, 3.0),
    "ewma_pos":        (1.5, 0.0),
}

# Shared-pattern panel for CUBIC + Reno.
AIMD_NODES = [
    ("cwnd_floor_cubic",   "cwnd_floor\n(CUBIC)"),
    ("pacing_ge_cubic",    "pacing_rate\n>= MSS (CUBIC)"),
    ("no_starv_cubic",     "no_starvation\nCUBIC (MAIN)"),
    ("cwnd_floor_reno",    "cwnd_floor\n(Reno)"),
    ("pacing_ge_reno",     "pacing_rate\n>= MSS (Reno)"),
    ("no_starv_reno",      "no_starvation\nReno (MAIN)"),
]
AIMD_EDGES = [
    ("no_starv_cubic", "pacing_ge_cubic"),
    ("pacing_ge_cubic", "cwnd_floor_cubic"),
    ("no_starv_reno", "pacing_ge_reno"),
    ("pacing_ge_reno", "cwnd_floor_reno"),
]
AIMD_POS = {
    "no_starv_cubic":   (3.0, 6.0),
    "pacing_ge_cubic":  (3.0, 3.0),
    "cwnd_floor_cubic": (3.0, 0.0),
    "no_starv_reno":    (11.0, 6.0),
    "pacing_ge_reno":   (11.0, 3.0),
    "cwnd_floor_reno":  (11.0, 0.0),
}

# KernelFidelity panel: the extended spec inherits the core onset
# bound through a single reduction step. The arrow into `starves_within`
# is into panel (a) conceptually; we redraw the target box locally
# so the panel is self-contained.
KFID_NODES = [
    ("kf_preserves",   "kernel_fidelity\npreserves onset"),
    ("kf_gap",         "kernel_fidelity\ngap = 17 W"),
    ("kf_core",        "core\nstarves_within"),
]
KFID_EDGES = [
    ("kf_preserves", "kf_core"),
    ("kf_gap",       "kf_core"),
]
KFID_POS = {
    "kf_preserves":  (3.0, 3.0),
    "kf_gap":        (11.0, 3.0),
    "kf_core":       (7.0, 0.0),
}


def _draw_panel(ax, nodes, edges, pos, title: str,
                box_w: float, box_h: float):
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
    label_map = {nid: lab for (nid, lab) in nodes}

    for parent, child in edges:
        px, py = pos[parent]
        cx, cy = pos[child]
        p_anchor = (px, py - box_h / 2)
        c_anchor = (cx, cy + box_h / 2)
        ax.add_patch(FancyArrowPatch(
            p_anchor, c_anchor,
            arrowstyle="->", mutation_scale=10,
            linewidth=0.7, color="0.45",
            shrinkA=1.0, shrinkB=1.0,
        ))

    for nid, (x, y) in pos.items():
        ax.add_patch(FancyBboxPatch(
            (x - box_w / 2, y - box_h / 2), box_w, box_h,
            boxstyle="round,pad=0.05,rounding_size=0.10",
            linewidth=0.9, edgecolor="black", facecolor="0.82",
        ))
        ax.text(x, y, label_map[nid], ha="center", va="center",
                fontsize=7.0, family="sans-serif", linespacing=1.05)

    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    ax.set_xlim(min(xs) - box_w, max(xs) + box_w)
    ax.set_ylim(min(ys) - box_h - 0.3, max(ys) + box_h + 0.8)
    ax.set_title(title, fontsize=9.0, pad=8)
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="figures/fig_proof_dag.pdf")
    args = ap.parse_args()

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("[fig_proof_dag] matplotlib missing", file=sys.stderr)
        return 2

    # 2-column layout: panel (a) BBRv3 gets the full height on the
    # left (it has 4 levels of nodes); panels (b) F*, (c) CUBIC/Reno,
    # and (d) kernel-fidelity stack on the right in 3 rows. Each
    # small panel is only as tall as its content, so the figure has
    # no empty vertical whitespace next to the short trees.
    fig = plt.figure(figsize=(15.5, 7.5))
    gs = fig.add_gridspec(
        3, 2,
        width_ratios=[1.45, 1.0],
        height_ratios=[1.0, 1.0, 1.0],
        wspace=0.08, hspace=0.30,
    )
    ax_neg  = fig.add_subplot(gs[:, 0])
    ax_pos  = fig.add_subplot(gs[0, 1])
    ax_aimd = fig.add_subplot(gs[1, 1])
    ax_kfid = fig.add_subplot(gs[2, 1])

    _draw_panel(ax_neg, NEGATIVE_NODES, NEGATIVE_EDGES, NEGATIVE_POS,
                "(a) BBRv3 negative (9 lemmas)",
                box_w=4.4, box_h=1.8)
    _draw_panel(ax_pos, POSITIVE_NODES, POSITIVE_EDGES, POSITIVE_POS,
                "(b) $F^{*}$ positive (4 lemmas)",
                box_w=5.2, box_h=1.6)
    _draw_panel(ax_aimd, AIMD_NODES, AIMD_EDGES, AIMD_POS,
                "(c) CUBIC + Reno (3+3 lemmas)",
                box_w=5.8, box_h=1.5)
    _draw_panel(ax_kfid, KFID_NODES, KFID_EDGES, KFID_POS,
                "(d) kernel-fidelity (2 lemmas $\\to$ (a))",
                box_w=5.6, box_h=1.5)

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight")
    print(f"[fig_proof_dag] wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
