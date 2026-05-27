#!/usr/bin/env python3
"""fig_lean_proof_size.py — Lean 4 proof-term size per theorem.

Counts the number of tactic-script lines (non-blank, non-comment)
between a `theorem`/`lemma` keyword and the next top-level
declaration. Reports by module so the reader sees which lemmas
carry the bulk of the refinement cost. Onset-theorem arithmetic
core is small (one-liner `omega` and `Nat.mul_le_mul_right` calls);
the patched-filter positivity proof is an order of magnitude larger
because it unfolds a recursive EWMA step over a `Fin W` index.

Measured on 2026-04-19 against the current repo head.
"""
from __future__ import annotations
import argparse, pathlib, re, sys


# (module, theorem_name, tactic_lines)
DATA = [
    ("OnsetTheorem",      "minrtt_monotone",                   23),
    ("OnsetTheorem",      "ack_agg_inflates",                  18),
    ("OnsetTheorem",      "cwnd_gain_insufficient",            19),
    ("OnsetTheorem",      "onset_upper_bound",                 23),
    ("OnsetTheorem",      "onset_lower_bound",                 13),
    ("OnsetTheorem",      "c_bounded_by_W",                    17),
    ("OnsetTheorem",      "onset_tight",                       24),
    ("OnsetTheorem",      "starves_within",                    11),
    ("OnsetTheoremTrace", "minrtt_monotone_closed",            13),
    ("OnsetTheoremTrace", "ack_agg_inflates_closed",           12),
    ("OnsetTheoremTrace", "onset_upper_bound_closed",          13),
    ("OnsetTheoremTrace", "onset_lower_bound_closed",          13),
    ("OnsetTheoremTrace", "starves_within_closed",             12),
    ("PatchedFilter",     "ewma_preserves_positivity",         24),
    ("PatchedFilter",     "step_patched_preserves_positivity", 102),
    ("PatchedFilter",     "no_starvation_under_F_star",        66),
]

MODULE_COLOURS = {
    "OnsetTheorem":      "#3e8e41",  # green = closed by prover
    "OnsetTheoremTrace": "#5a5a5a",  # grey = trace-level, closed-loop env
    "PatchedFilter":     "#d97706",  # amber = hand-proved positivity
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="figures/fig_lean_proof_size.pdf")
    args = ap.parse_args()

    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("matplotlib missing", file=sys.stderr); return 2

    fig, ax = plt.subplots(figsize=(6.4, 3.4))

    # Per Aidan 2026-04-19: sort by tactic-script count descending,
    # largest-at-top so the eye lands on the expensive proofs first.
    data_sorted = sorted(DATA, key=lambda d: d[2], reverse=True)

    ys = list(range(len(data_sorted)))
    sizes = [d[2] for d in data_sorted]
    names = [d[1].replace("_", r"\_") for d in data_sorted]
    colours = [MODULE_COLOURS[d[0]] for d in data_sorted]

    bars = ax.barh(ys, sizes, color=colours, edgecolor="white",
                    linewidth=0.5, height=0.72)

    ax.set_yticks(ys)
    ax.set_yticklabels([f"$\\mathtt{{{n}}}$" for n in names], fontsize=7.2)
    # Invert so the first row of `data_sorted` (largest bar) sits at
    # the TOP of the plot — matplotlib's default barh puts y=0 at
    # the bottom.
    ax.invert_yaxis()
    ax.set_xlabel("tactic-script lines (all theorems closed)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, axis="x", alpha=0.25, linewidth=0.5)

    # Legend — one swatch per module.
    from matplotlib.patches import Patch
    handles = [Patch(facecolor=c, label=m) for m, c in MODULE_COLOURS.items()]
    ax.legend(handles=handles, loc="lower right", frameon=False,
              fontsize=7.5, title="module", title_fontsize=7.5)

    # Annotate the largest bar with its line count.
    for bar, sz in zip(bars, sizes):
        if sz >= 50:
            ax.text(sz + 1.5, bar.get_y() + bar.get_height() / 2,
                    str(sz), va="center", fontsize=7)

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    print(f"wrote {out}"); return 0


if __name__ == "__main__":
    sys.exit(main())
