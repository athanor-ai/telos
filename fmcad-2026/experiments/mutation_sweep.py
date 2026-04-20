#!/usr/bin/env python3
"""mutation_sweep.py --- a follow-up pass mutation-kill tensor driver.

Applies 10 BBRv3 state-machine mutations to the Lean source, the
SystemVerilog dual, and the Python simulator in lockstep. Measures
which verification layer catches each mutation.

Mutation catalogue (matches `sections/appendix.tex` Appendix C):
    M01 pacing-gain drop (ProbeBW phase 0: 1.25 -> 1.0)
    M02 min-RTT filter window truncation (W -> W / 2)
    M03 cwnd_gain perturbation (2 -> 1.5)
    M04 STARTUP exit flag inversion
    M05 DRAIN threshold swap
    M06 PROBE_RTT duration cut (200 ms -> 50 ms)
    M07 delivered-rate underestimate (rate -> 0.9 * rate)
    M08 loss-response bypass (skip the loss handler entirely)
    M09 pacing-delay quantization error (delay -> floor(delay))
    M10 ACK-compression amplification (treat one ACK as 2)

Cross-layer detection tensor `Caught[mutation, layer]` with layers in
{Lean, EBMC, Hypothesis, simulator}. Target: each mutation killed by
>= 2 layers.

Status: **scaffold only**. The catalogue is frozen here; the
per-mutation source transform pipeline lands under a follow-up pass after the
Lean source has stable sub-step bodies (post a follow-up pass).

Usage:
    python3 experiments/mutation_sweep.py --out experiments/runs/<stamp>/mutation_tensor.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

MUTATIONS = [
    {"id": "M01", "name": "pacing_gain_drop", "target": "Trace.pacing_gain_cycle"},
    {"id": "M02", "name": "filter_window_truncation", "target": "Basic.BBRState.min_rtt_filt"},
    {"id": "M03", "name": "cwnd_gain_perturbation", "target": "Basic.BBRState.cwnd_gain"},
    {"id": "M04", "name": "startup_exit_flag_inversion", "target": "Trace.mode_transition"},
    {"id": "M05", "name": "drain_threshold_swap", "target": "Trace.mode_transition"},
    {"id": "M06", "name": "probe_rtt_duration_cut", "target": "Trace.mode_transition"},
    {"id": "M07", "name": "delivered_rate_underestimate", "target": "Trace.bandwidth_update"},
    {"id": "M08", "name": "loss_response_bypass", "target": "Trace.mode_transition"},
    {"id": "M09", "name": "pacing_delay_quantization", "target": "Trace.cwnd_compute"},
    {"id": "M10", "name": "ack_compression_amplification", "target": "Trace.filter_update"},
]

LAYERS = ["lean", "ebmc", "hypothesis", "simulator"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.dry_run:
        print(f"[mutation_sweep] {len(MUTATIONS)} mutations x {len(LAYERS)} layers = {len(MUTATIONS) * len(LAYERS)} cells", file=sys.stderr)
        return 0

    # Scaffold output: every cell as "pending", so downstream figure +
    # acceptance code can be developed against the expected shape.
    tensor = {
        "mutations": MUTATIONS,
        "layers": LAYERS,
        "caught": {m["id"]: {l: "pending" for l in LAYERS} for m in MUTATIONS},
        "notes": "a follow-up pass scaffold; real mutant generation + per-layer checks land after a follow-up pass.",
    }

    if args.out:
        out_path = pathlib.Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(tensor, indent=2))
        print(f"[mutation_sweep] wrote scaffold tensor to {out_path}", file=sys.stderr)
    else:
        json.dump(tensor, sys.stdout, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
