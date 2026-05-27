#!/usr/bin/env python3
"""cpu_sim_aimd.py — deterministic CPU-simulator sweep for CUBIC + Reno.

The positive theorem `no_starvation_under_bounded_ack` is the only
theorem the CUBIC/Reno specs state; unlike BBRv3 there is no onset
time to measure, only the invariant `pacing_rate > 0` to verify on
every cell of the spec's cpu_sim grid.

Per spec (dsl/examples/cubic.yaml, reno.yaml):
    CUBIC: burst_size [1,4,8,16] x rtt_ms [1,10,100] x seeds 50
    Reno:  burst_size [1,2,4,8]  x rtt_ms [1,10,100] x seeds 50

Each cell runs HORIZON ticks with a deterministic loss pattern keyed
to (burst_size, seed); burst_size is interpreted as "one loss event
every burst_size ticks" since the CCAs have no ACK-aggregation state.

Emits one CSV row per cell with columns: protocol, burst_size, rtt_ms,
seed, starved, min_pacing_rate, final_pacing_rate.

Usage:
    python3 experiments/cpu_sim_aimd.py --protocol cubic --out out.csv
    python3 experiments/cpu_sim_aimd.py --protocol reno  --out out.csv
"""
from __future__ import annotations

import argparse
import csv
import itertools
import pathlib
import random
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from reference_cca.aimd_lean_port import (  # noqa: E402
    AckEvent, CubicState, RenoState, step_cubic, step_reno,
)


HORIZON = 60  # ticks per trace; matches BBRv3 sim and hypothesis runs.
MSS = 1500.0  # RFC default, consistent with both YAML specs' concrete_tuple.


def _loss_schedule(burst_size: int, seed: int) -> list[bool]:
    """Deterministic loss pattern: one loss every `burst_size` ticks,
    with per-seed jitter on which ticks trigger."""
    rng = random.Random(seed)
    mask = [False] * HORIZON
    for k in range(0, HORIZON, max(1, burst_size)):
        k_jit = min(HORIZON - 1, max(0, k + rng.randint(-1, 1)))
        mask[k_jit] = True
    return mask


def _run_cubic_cell(burst_size: int, rtt_ms: float, seed: int) -> dict:
    srtt = rtt_ms / 1000.0
    s = CubicState(
        cwnd=10 * MSS, W_max=10 * MSS, t_last_event=0.0,
        ssthresh=10 * MSS, pacing_rate=(10 * MSS) / srtt, srtt=srtt,
    )
    min_rate = s.pacing_rate
    wall = 0.0
    for is_loss in _loss_schedule(burst_size, seed):
        wall += srtt
        s = step_cubic(
            s, AckEvent(is_loss=is_loss, wall_clock=wall),
            MSS=MSS, C=0.4, beta=0.7,
        )
        if s.pacing_rate < min_rate:
            min_rate = s.pacing_rate
    return {"min_pacing_rate": min_rate, "final_pacing_rate": s.pacing_rate,
            "starved": min_rate <= 0.0}


def _run_reno_cell(burst_size: int, rtt_ms: float, seed: int) -> dict:
    srtt = rtt_ms / 1000.0
    s = RenoState(
        cwnd=10 * MSS, ssthresh=10 * MSS,
        pacing_rate=(10 * MSS) / srtt, srtt=srtt, in_slow_start=True,
    )
    min_rate = s.pacing_rate
    wall = 0.0
    for is_loss in _loss_schedule(burst_size, seed):
        wall += srtt
        s = step_reno(s, AckEvent(is_loss=is_loss, wall_clock=wall), MSS=MSS)
        if s.pacing_rate < min_rate:
            min_rate = s.pacing_rate
    return {"min_pacing_rate": min_rate, "final_pacing_rate": s.pacing_rate,
            "starved": min_rate <= 0.0}


GRIDS = {
    "cubic": {"burst_size": [1, 4, 8, 16], "rtt_ms": [1, 10, 100], "seeds": 50},
    "reno":  {"burst_size": [1, 2, 4, 8],  "rtt_ms": [1, 10, 100], "seeds": 50},
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", choices=["cubic", "reno"], required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    grid = GRIDS[args.protocol]
    runner = _run_cubic_cell if args.protocol == "cubic" else _run_reno_cell
    rows: list[dict] = []
    for B, D, seed in itertools.product(
        grid["burst_size"], grid["rtt_ms"], range(grid["seeds"]),
    ):
        result = runner(B, D, seed)
        rows.append({
            "protocol": args.protocol,
            "burst_size": B, "rtt_ms": D, "seed": seed,
            **result,
        })

    n_starved = sum(1 for r in rows if r["starved"])
    print(f"[cpu_sim_aimd:{args.protocol}] {len(rows)} cells, "
          f"{n_starved} starved, {len(rows) - n_starved} horizon-reached")

    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    return 0 if n_starved == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
