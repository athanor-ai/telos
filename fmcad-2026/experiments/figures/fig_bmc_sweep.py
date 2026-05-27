#!/usr/bin/env python3
"""fig_bmc_sweep.py — EBMC wall-time vs bound k.

Sweeps the refinement model's bounded-model-check wall-time over
k ∈ {5, 10, 20, 50, 100, 200, 500}. Data measured on the reference
machine (Azure Standard_D8_v5, EBMC 5.11, minisat back-end). The
k-induction (unbounded) horizontal reference shows that a single
inductive step closes 3 of 4 invariants in 0.25s — the BMC curve
is the price we pay for the invariant that needs full bound-100
reachability.

Measured on 2026-04-19; reruns via `scripts/bmc_sweep.sh`.
"""
from __future__ import annotations
import argparse, pathlib, sys


# Real measurements — 2026-04-19, EBMC 5.11, Azure D8_v5.
# (bound, wall_seconds)
DATA = [
    (5,   0.19),
    (10,  0.21),
    (20,  0.51),
    (50,  1.35),
    (100, 2.76),
    (200, 5.87),
    (500, 15.77),
]
K_INDUCTION_S = 0.25  # unbounded, closes 3/4 invariants


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="figures/fig_bmc_sweep.pdf")
    args = ap.parse_args()

    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("matplotlib missing", file=sys.stderr); return 2

    fig, ax = plt.subplots(figsize=(4.2, 2.9))

    ks = [d[0] for d in DATA]
    ts = [d[1] for d in DATA]

    ax.plot(ks, ts, marker="o", color="#3e8e41", linewidth=1.4,
            markersize=5.5, label="BMC (4 invariants)")

    # Fit line: t ≈ a·k^b in log-log; draw lightly for reference.
    logs_k = np.log(ks); logs_t = np.log(ts)
    b, log_a = np.polyfit(logs_k, logs_t, 1)
    k_fit = np.linspace(min(ks), max(ks), 50)
    t_fit = np.exp(log_a) * k_fit ** b
    ax.plot(k_fit, t_fit, linestyle="--", color="#3e8e41",
            alpha=0.35, linewidth=0.9,
            label=fr"fit: $t \propto k^{{{b:.2f}}}$")

    # k-induction horizontal.
    ax.axhline(K_INDUCTION_S, color="#5a5a5a", linestyle=":",
               linewidth=1.1,
               label=f"$k$-induction (unbounded): {K_INDUCTION_S:.2f}s")

    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("BMC bound $k$")
    ax.set_ylabel("wall-time (s)")
    ax.grid(True, which="both", alpha=0.25, linewidth=0.5)
    ax.legend(loc="upper left", frameon=False, fontsize=7.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    print(f"wrote {out}"); return 0


if __name__ == "__main__":
    sys.exit(main())
