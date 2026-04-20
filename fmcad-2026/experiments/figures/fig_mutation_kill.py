#!/usr/bin/env python3
"""fig_mutation_kill.py --- ATH-344 output: render the cross-layer
mutation-kill tensor as a stacked-bar figure.

Input:  experiments/runs/<stamp>/mutation_tensor.json
Output: figures/fig_mutation_kill.pdf

Figure spec:
  Rows: 10 mutations.
  Columns: 4 layers (Lean, EBMC, Hypothesis, simulator).
  Cell: colored square with one of {caught, missed, pending, n/a}.
  Right panel: per-layer kill-rate bar chart aggregated across
               mutations. Matches the dopamine paper Figure 4 visual
               convention.

Status: **scaffold**. Wire-up after ATH-344 produces the first tensor.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="mutation_tensor.json")
    ap.add_argument("--out", required=True, help="output PDF")
    args = ap.parse_args()

    j_path = pathlib.Path(args.input)
    if not j_path.exists():
        print(f"ERROR: tensor JSON missing: {j_path}", file=sys.stderr)
        return 1

    tensor = json.loads(j_path.read_text())

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as e:
        print(f"ERROR: matplotlib not available: {e}", file=sys.stderr)
        return 1

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.5),
                                   gridspec_kw={"width_ratios": [3, 1]})
    ax1.text(0.5, 0.5, "ATH-344 pending\n(scaffold placeholder)",
             ha="center", va="center", transform=ax1.transAxes, color="grey")
    ax2.text(0.5, 0.5, "per-layer kill rate",
             ha="center", va="center", transform=ax2.transAxes, color="grey")
    for ax in (ax1, ax2):
        ax.set_xticks([])
        ax.set_yticks([])
    ax1.set_title("Caught[mutation, layer]")
    ax2.set_title("Aggregate")
    fig.tight_layout()
    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, format="pdf")
    print(f"[fig_mutation_kill] wrote scaffold placeholder to {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
