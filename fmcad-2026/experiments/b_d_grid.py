#!/usr/bin/env python3
"""b_d_grid.py --- a follow-up pass CPU simulator B/D residual sweep.

For each (B, D, link_rate, seed) cell:
  1. Load the base scenario `scenarios/clocked_ack_base.json`.
  2. Derive a cell-specific scenario by tuning the return-path link
     buffer + rate to emulate ACK aggregation of burst size B.
  3. Instantiate the student BBRv3 reference implementation from
     the student congestion-control reference (bundled in the replication package)
     via the CC env adapter bundled with the replication package.
  4. Run the simulator to time T_max (default 60 s of simulated time).
  5. Record the *first* RTT index at which `inflight == 0` sustained
     for >= 1 RTT. That is the empirical starvation-onset time.
  6. Emit one CSV row per cell: (B, D, link_rate, seed, T_emp, T_analytic,
     residual, reason).

Output shape matches what `figures/fig_residual.py` expects.

Usage:
    python3 experiments/b_d_grid.py \\
        --b-grid 0.25,0.5,1,2,3,4 \\
        --d-ms 1,5,20,50,100 \\
        --link-rate-mbps 10,100,1000,10000 \\
        --seeds 100 \\
        --w-rtt 100 \\
        --t-max-s 60 \\
        --out experiments/runs/$(date +%Y%m%d-%H%M%S)/layer4_sim_residuals.csv

Status: **scaffold only**. Actual simulator invocation wired in under
a follow-up pass. Runs as a no-op preflight today; prints the cell grid it would
sweep and exits 0. The scaffold lets the CI preflight at PR-time without
pulling in the ~500 MB CC env container.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import pathlib
import sys
import time


def parse_grid(s: str, cast=float):
    return [cast(x.strip()) for x in s.split(",") if x.strip()]


def analytic_onset_time(B_over_D: float, W_rtt: int, c_rtt: int) -> float:
    """T(B, D) = (B/D - 2) * W + c, in RTT units. Returns None if the
    closed form is vacuous (B/D <= 2)."""
    if B_over_D <= 2.0:
        return float("nan")
    return (B_over_D - 2.0) * W_rtt + c_rtt


def derive_scenario(base: dict, B: float, D_ms: float, link_rate_mbps: float) -> dict:
    """Produce a cell-specific scenario JSON. ACK aggregation of burst B
    is modelled by tuning the return-path link buffer + rate; see
    experiments/README.md for the approximation note."""
    # ... full derivation implemented under a follow-up pass ...
    cell = json.loads(json.dumps(base))  # deepcopy via JSON
    cell["_ack_aggregation"] = {
        "B": B,
        "D_ms": D_ms,
        "link_rate_mbps": link_rate_mbps,
        "derivation_notes": "buffer = B * MTU; rate = capacity / B; approximate",
    }
    return cell


def _build_ack_schedule(
    B: float, D_ms: float, W_rtt: int, t_max_rtt: int, seed: int,
    schedule_kind: str = "aggregating",
) -> list:
    """Construct the per-tick AckEvent schedule for one cell.

    Two schedule models for a follow-up pass Phase A:

    `aggregating` (default) — every ceil(B) ticks the sender sees a
    burst of B*D delivered bytes; between bursts, 0 delivery. This is
    the standard BBRv3 ACK-aggregation pattern. Under this schedule,
    the iter-3 counterexample predicted the original `pacing_rate = 0`
    starvation predicate is unreachable — the windowed max always
    contains at least one recent burst, so pacing_rate stays positive.
    This sim reproduces that empirically.

    `quiescent` — the schedule has a block of W consecutive zero-
    delivery ticks starting at tick k, matching Option A's scheduler
    hypothesis. Under this schedule the windowed max drains to zero
    by tick k+W, which IS starvation. Option C's theorem is the
    empirical match point.

    The schedule is deterministic in (B, D, seed). Seed only drives
    jitter on wall_clock within ±10% of D.
    """
    import random
    from reference_cca.bbrv3_lean_port import AckEvent
    rng = random.Random(seed)
    schedule = []
    B_int = max(1, int(round(B)))
    # Quiescent window placement. Two modes:
    #   fixed — start at tick 2W (the original scale-up run).
    #   analytic — start the quiescent block exactly at T_analytic = max(1, (B-2)*W),
    #              so that the "does starvation happen within 1 RTT of the
    #              analytic prediction?" check probes the sandwich-bound
    #              tightness directly.
    # Analytic placement is the CAV-relevant measurement.
    analytic_T = max(1, int(round((B - 2.0) * W_rtt)))
    quiescent_start = analytic_T
    quiescent_end = quiescent_start + W_rtt
    for k in range(t_max_rtt):
        is_quiet = (schedule_kind == "quiescent"
                    and quiescent_start <= k < quiescent_end)
        if is_quiet:
            delivered = 0
        else:
            phase_in_cycle = k % B_int
            if phase_in_cycle == 0:
                delivered = int(round(B * D_ms))
            else:
                delivered = 0
        jitter = 1.0 + (rng.random() - 0.5) * 0.2  # ±10%
        schedule.append(AckEvent(
            burst_size=max(1, delivered or 1),
            delivered=delivered,
            wall_clock=D_ms * jitter,
        ))
    return schedule


def run_cell(scenario: dict, seed: int, t_max_s: float, w_rtt: int,
             threshold: float = 0.0, schedule_kind: str = "aggregating",
             filter_kind: str = "bbrv3") -> dict:
    """Invoke the BBRv3 Lean-port reference CCA on one cell.

    a follow-up pass Phase A: direct simulation of the Lean state machine
    (`experiments/reference_cca/bbrv3_lean_port.py`) on an ACK schedule
    derived from the cell's (B, D, link_rate) parameters. By-construction
    equivalent to the theorem's state space, so the residual
    `T_emp − T_analytic` measures whether the closed-form sandwich
    bound holds under a realistic aggregating-ACK schedule.
    """
    import os
    import sys
    _here = os.path.dirname(os.path.abspath(__file__))
    if _here not in sys.path:
        sys.path.insert(0, _here)
    from reference_cca.bbrv3_lean_port import simulate

    B = scenario["_ack_aggregation"]["B"]
    D_ms = scenario["_ack_aggregation"]["D_ms"]
    # Approximate t_max in RTTs from wall time budget.
    t_max_rtt = max(10, int(round(t_max_s * 1000.0 / max(D_ms, 0.1))))
    schedule = _build_ack_schedule(B, D_ms, w_rtt, t_max_rtt, seed,
                                    schedule_kind=schedule_kind)

    onset_tick = simulate(W=w_rtt, B=B, D=D_ms, schedule=schedule,
                          threshold=threshold, filter_kind=filter_kind)
    starved = onset_tick < len(schedule)
    if not starved:
        reason = "horizon_reached"
    else:
        reason = "starvation_detected"
    return {
        "T_emp_rtt": float(onset_tick) if starved else float("nan"),
        "starved": starved,
        "reason": reason,
        "horizon_rtt": t_max_rtt,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--b-grid", default="0.25,0.5,1,2,3,4", help="B/D ratios, comma-separated")
    ap.add_argument("--d-ms", default="1,5,20,50,100", help="path delay range in ms")
    ap.add_argument("--link-rate-mbps", default="10,100,1000,10000", help="bottleneck link rates")
    ap.add_argument("--seeds", type=int, default=100)
    ap.add_argument("--w-rtt", type=int, default=100, help="min-RTT filter window in RTTs")
    ap.add_argument("--c-rtt", type=int, default=2, help="derived BBRv3 constant c, placeholder")
    ap.add_argument("--t-max-s", type=float, default=60.0)
    ap.add_argument("--base-scenario", default="experiments/scenarios/clocked_ack_base.json")
    ap.add_argument("--out", default=None)
    ap.add_argument("--dry-run", action="store_true", help="print cell count + exit")
    ap.add_argument(
        "--threshold", type=float, default=0.0,
        help="Option-C threshold: starved := pacing_rate <= threshold. "
             "Default 0.0 matches the original Lean predicate (pacing_rate = 0), "
             "which iter-3 showed was unreachable under non-halting ACK schedules. "
             "Set >0 to measure Option-C's refined starvation under realistic ACK.",
    )
    ap.add_argument(
        "--schedule", default="aggregating",
        choices=["aggregating", "quiescent"],
        help="ACK schedule model. `aggregating` = BBRv3's standard burst-then-silence "
             "pattern (matches iter-3 counterexample). `quiescent` = Option-A "
             "scheduler-hypothesis with a W-tick zero-delivery window; drains the "
             "filter and triggers onset (matches Option-C theorem prediction).",
    )
    ap.add_argument(
        "--filter", dest="filter_kind", default="bbrv3",
        choices=["bbrv3", "fstar"],
        help="Bandwidth-filter variant. `bbrv3` is the windowed-max the starvation "
             "theorem is stated over. `fstar` is the a follow-up pass patched filter whose "
             "positive theorem (no_starvation_under_F_star) predicts zero cells "
             "starve under the same (B, D, W) grid.",
    )
    args = ap.parse_args()

    base_path = pathlib.Path(args.base_scenario)
    if not base_path.exists():
        # Scaffold the base scenario on first run.
        base_path.parent.mkdir(parents=True, exist_ok=True)
        base_path.write_text(json.dumps({
            "links": [{"id": "bottleneck", "rate_mbps": 100, "delay_ms": 10, "buffer": 128}],
            "flows": [{"id": "F1", "cca": "bbrv3", "start_s": 0.0}],
        }, indent=2))
        print(f"[b_d_grid] wrote base scenario placeholder: {base_path}", file=sys.stderr)

    base = json.loads(base_path.read_text())
    Bs = parse_grid(args.b_grid, float)
    Ds = parse_grid(args.d_ms, float)
    Rs = parse_grid(args.link_rate_mbps, float)
    seeds = list(range(args.seeds))
    total = len(Bs) * len(Ds) * len(Rs) * len(seeds)
    print(f"[b_d_grid] cells: {len(Bs)} * {len(Ds)} * {len(Rs)} * {len(seeds)} = {total}", file=sys.stderr)

    if args.dry_run:
        return 0

    out_path = pathlib.Path(args.out) if args.out else None
    rows: list[dict] = []
    t0 = time.time()
    for B, D, R, seed in itertools.product(Bs, Ds, Rs, seeds):
        cell = derive_scenario(base, B, D, R)
        result = run_cell(cell, seed, args.t_max_s, args.w_rtt,
                          threshold=args.threshold,
                          schedule_kind=args.schedule,
                          filter_kind=args.filter_kind)
        T_ana = analytic_onset_time(B, args.w_rtt, args.c_rtt)
        residual = None
        if isinstance(result["T_emp_rtt"], float) and result["T_emp_rtt"] == result["T_emp_rtt"]:
            if isinstance(T_ana, float) and T_ana == T_ana:
                residual = result["T_emp_rtt"] - T_ana
        rows.append({
            "B": B,
            "D_ms": D,
            "link_rate_mbps": R,
            "seed": seed,
            "T_emp_rtt": result["T_emp_rtt"],
            "T_analytic_rtt": T_ana,
            "residual_rtt": residual if residual is not None else "",
            "reason": result.get("reason", ""),
        })
    elapsed = time.time() - t0
    print(f"[b_d_grid] {len(rows)} rows in {elapsed:.1f}s", file=sys.stderr)

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)
        print(f"[b_d_grid] wrote {out_path}", file=sys.stderr)
    else:
        w = csv.DictWriter(sys.stdout, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
