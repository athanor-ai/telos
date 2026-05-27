#!/usr/bin/env python3
"""
t_refined.py  --  Track 1 of follow-up (iii) from the FMCAD-26 BBRv3
starvation paper.

Context
-------
The kernel-replay sanity sweep (kernel_replay/results/sanity_cell.csv)
shows that the core 5-substep abstraction's onset bound
    T_analytic(B, D) = (B // D - 2) * W + c
is a SOUND but LOOSE upper bound on the real Linux BBRv3 kernel: in
all five in-regime cells (B > 2D) the kernel held pacing steady at
480-920 Mbps for 30 s, never crossing the 8 kbps collapse
threshold. T_analytic ranged 10-40 ms; the empirical onset is
unmeasured above 30 s (>=3 orders of magnitude larger).

The kernel-fidelity spec (examples/bbrv3-kernel-fidelity.yaml) adds
the four tcp_bbr.c state fields the core abstraction ignores:
    inflight_lo, inflight_hi, lt_bw, packets_in_flight.

Two of those fields impose additive delays on starvation onset:

  delta(inflight_lo_floor) = W * (1 / (1 - 0.85)) = W * 6.67
    -- the fixed-point of the 0.85 floor.  On each RTT the kernel
       ratchets inflight_lo down by at most a factor of 0.85, so the
       time to drain inflight_lo to its probing floor is a geometric
       sum W * sum_{k>=0} 0.85^k = W / (1 - 0.85).

  delta(lt_bw_inertia) = W * (lt_bw_sample_period / min_rtt)
    -- BBRv3 samples long-term bandwidth over 10 * min_rtt windows
       (tcp_bbr_check_full_bw_reached sets lt_rtt_cnt = 10 as the
       default), so the lt_bw filter absorbs an ACK-aggregation
       adversary for 10 * W extra ms of min-RTT ticks.

Refined bound:
    T_refined(B, D) = T_analytic(B, D) + 6.67 * W + 10 * W
                    = T_analytic(B, D) + 16.67 * W
    At W = 10 ms this is an extra ~167 ms over T_analytic.

Output: kernel_replay/results/t_refined_predictions.csv with columns
    B, D, T_analytic, T_refined, T_kernel
for the six sweep rows.
"""
import csv
import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
IN_CSV = HERE / "results" / "sanity_cell.csv"
OUT_CSV = HERE / "results" / "t_refined_predictions.csv"

# BBRv3 paper / Linux tcp_bbr.c defaults.
W_MS = 10                       # min-RTT filter tick (ms)
INFLIGHT_LO_RATIO = 0.85        # tcp_bbr.c §4.5.1 floor ratchet
LT_BW_SAMPLE_RTT_COUNT = 10     # tcp_bbr.c check_full_bw_reached cap

DELTA_INFLIGHT_LO_MS = W_MS * (1.0 / (1.0 - INFLIGHT_LO_RATIO))
DELTA_LT_BW_MS = W_MS * LT_BW_SAMPLE_RTT_COUNT
DELTA_TOTAL_MS = DELTA_INFLIGHT_LO_MS + DELTA_LT_BW_MS


def t_analytic(B: int, D: int, W: int = W_MS) -> int:
    """Core 5-substep onset bound: (B // D - 2) * W + W.

    Matches the harness-authoritative formula used to populate
    sanity_cell.csv (README.md §Setup line 11).
    """
    return (B // D - 2) * W + W


def t_refined(B: int, D: int, W: int = W_MS) -> float:
    """Kernel-fidelity extended onset bound.

    T_refined = T_analytic + delta(inflight_lo) + delta(lt_bw).
    """
    return t_analytic(B, D, W) + DELTA_TOTAL_MS


def parse_int_or_none(value: str):
    value = value.strip()
    if value == "" or value.upper() == "NA":
        return None
    try:
        return int(value)
    except ValueError:
        # Some rows record floats; tolerate those too.
        try:
            return int(round(float(value)))
        except ValueError:
            return None


def main() -> int:
    if not IN_CSV.exists():
        print(f"ERROR: input CSV missing: {IN_CSV}", file=sys.stderr)
        return 2

    out_rows = []
    with IN_CSV.open(newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                B = int(row["B"])
                D = int(row["D"])
            except (KeyError, ValueError):
                continue
            t_an = t_analytic(B, D)
            t_re = t_refined(B, D)
            t_kernel = parse_int_or_none(row.get("T_kernel_ms", "NA"))
            out_rows.append(
                {
                    "B": B,
                    "D": D,
                    "T_analytic": t_an,
                    "T_refined": f"{t_re:.2f}",
                    "T_kernel": "NA" if t_kernel is None else str(t_kernel),
                }
            )

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["B", "D", "T_analytic", "T_refined", "T_kernel"]
        )
        writer.writeheader()
        for row in out_rows:
            writer.writerow(row)

    # Human-readable summary to stdout.
    print(
        f"W = {W_MS} ms, "
        f"delta(inflight_lo_floor) = {DELTA_INFLIGHT_LO_MS:.2f} ms, "
        f"delta(lt_bw_inertia) = {DELTA_LT_BW_MS:.2f} ms, "
        f"delta_total = {DELTA_TOTAL_MS:.2f} ms."
    )
    print(f"Wrote {len(out_rows)} rows to {OUT_CSV}")
    header = f"{'B':>3} {'D':>3} {'T_analytic(ms)':>15} {'T_refined(ms)':>14} {'T_kernel(ms)':>13}"
    print(header)
    print("-" * len(header))
    for r in out_rows:
        print(
            f"{r['B']:>3} {r['D']:>3} {r['T_analytic']:>15} "
            f"{r['T_refined']:>14} {r['T_kernel']:>13}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
