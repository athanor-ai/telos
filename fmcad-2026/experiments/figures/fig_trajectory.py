#!/usr/bin/env python3
"""fig_trajectory.py — pacing-rate trajectory over time: BBRv3 vs F*.

Instruments the Lean-port reference CCA to dump pacing_rate at every
tick under a representative quiescent schedule (B=5, D=2, W=10), and
plots BBRv3's collapse-to-zero alongside F*'s stable-positive decay.

Output: figures/fig_trajectory.pdf. Two overlaid line plots in
grayscale (solid for BBRv3, dashed for F*). Annotations mark the
quiescent-window start tick and the absorbing-boundary reach.

Headline reading: BBRv3's windowed-max drops from 1 to 0 in exactly
W ticks after the quiescent block starts. F*'s EWMA decays
geometrically with time constant W, never reaching zero. Both
curves share an x-axis (tick number) and y-axis (pacing_rate, log).
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from reference_cca.bbrv3_lean_port import (  # noqa: E402
    AckEvent, BBRState, step, step_patched,
)


def simulate_with_trace(W: int, B: int, D: int, schedule: list, filter_kind: str):
    """Run the state machine, returning the list of pacing_rate values
    tick-by-tick."""
    s = BBRState(W=W)
    step_fn = step_patched if filter_kind == "fstar" else step
    rates = [s.pacing_rate]
    for a in schedule:
        s = step_fn(s, a)
        rates.append(s.pacing_rate)
    return rates


def build_quiescent_schedule(W: int, B: int, D: int, t_max: int, quiet_start: int):
    """Build a deterministic schedule with a quiescent window of length W
    starting at tick `quiet_start`, otherwise bursty aggregating ACKs."""
    schedule = []
    for k in range(t_max):
        is_quiet = (quiet_start <= k < quiet_start + W)
        if is_quiet:
            delivered = 0
        else:
            # aggregating: every B-th tick, a burst; otherwise 0
            delivered = int(B * D) if (k % B == 0) else 0
        schedule.append(AckEvent(
            burst_size=max(1, delivered or 1),
            delivered=delivered,
            wall_clock=float(D),
        ))
    return schedule


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--w", type=int, default=10)
    ap.add_argument("--b", type=int, default=5)
    ap.add_argument("--d", type=int, default=2)
    ap.add_argument("--t-max", type=int, default=60)
    ap.add_argument("--quiet-start", type=int, default=20)
    ap.add_argument("--out", default="figures/fig_trajectory.pdf")
    args = ap.parse_args()

    sched = build_quiescent_schedule(args.w, args.b, args.d, args.t_max, args.quiet_start)
    bbrv3_rates = simulate_with_trace(args.w, args.b, args.d, sched, "bbrv3")
    fstar_rates = simulate_with_trace(args.w, args.b, args.d, sched, "fstar")

    print(f"[fig_trajectory] BBRv3 min rate: {min(bbrv3_rates):.4f}")
    print(f"[fig_trajectory] F*    min rate: {min(fstar_rates):.4f}")

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("[fig_trajectory] matplotlib missing", file=sys.stderr)
        return 2

    ticks = list(range(len(bbrv3_rates)))

    # Collapse + floor stats rolled into the legend labels instead
    # of onto arrow annotations (Aidan directive 2026-04-19: no
    # arrows with text; use the legend).
    bbrv3_zero_tick = None
    for i, r in enumerate(bbrv3_rates):
        if r <= 1e-9:
            bbrv3_zero_tick = i
            break
    fstar_min = min(fstar_rates[args.quiet_start:args.quiet_start + args.w + 1])

    bbrv3_label = "BBRv3 (windowed-max)"
    if bbrv3_zero_tick is not None:
        bbrv3_label += f"; collapses at tick {bbrv3_zero_tick}"
    fstar_label = (r"$F^{*}$ (burst-norm + EWMA)"
                   f"; floor $\\approx {fstar_min:.2f}$")

    fig, ax = plt.subplots(figsize=(6.0, 3.2))
    ax.plot(ticks, bbrv3_rates, color="black", linewidth=1.4,
            label=bbrv3_label)
    ax.plot(ticks, fstar_rates, color="black", linewidth=1.2,
            linestyle="--", dashes=(4, 2), label=fstar_label)

    # Shade the quiescent window so the reader can see exactly where
    # BBRv3 crosses zero.
    ax.axvspan(args.quiet_start, args.quiet_start + args.w,
               color="0.88", alpha=0.6,
               label=f"quiescent window ($W = {args.w}$ ticks)")
    ax.axhline(0, color="0.4", linewidth=0.6, linestyle=":")

    ax.set_xlabel("tick (RTT units)")
    ax.set_ylabel("pacing rate")
    ax.set_ylim(bottom=-0.05)
    ax.set_xlim(0, args.t_max)
    # Legend ABOVE the plot area so it stays clear of the data lines.
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.30),
              ncol=1, frameon=False, fontsize=7.5,
              handletextpad=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle=":", alpha=0.4)

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    print(f"[fig_trajectory] wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
