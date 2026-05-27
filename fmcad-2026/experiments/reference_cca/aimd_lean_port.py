"""aimd_lean_port.py — Python ports of the CUBIC and Reno positive-theorem
state machines. Mirrors `dsl/examples/cubic.yaml` + `reno.yaml` step_compose.

The theorem `no_starvation_under_bounded_ack` is the same for both:
    forall n, pacing_rate_n > 0, given MSS > 0, srtt > 0, cwnd_0 >= MSS.

Both ports exist to back the Hypothesis sweep that closes the sandwich
rule's 4th of 5 backends (Lean + Dafny are asabi's lane; CPU-sim is the
5th backend). The `step` function implementation follows spec YAML
substep order exactly so any divergence is diagnosable as a spec-vs-port
mismatch rather than an implementation bug.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CubicState:
    cwnd: float
    W_max: float
    t_last_event: float
    ssthresh: float
    pacing_rate: float
    srtt: float


@dataclass
class RenoState:
    cwnd: float
    ssthresh: float
    pacing_rate: float
    srtt: float
    in_slow_start: bool


@dataclass
class AckEvent:
    """Per-tick ACK event: ECN/loss flag + elapsed wall clock."""
    is_loss: bool
    wall_clock: float  # seconds since flow start


def step_cubic(
    s: CubicState, a: AckEvent, *, MSS: float, C: float, beta: float,
) -> CubicState:
    """One step of the CUBIC substep chain per cubic.yaml."""
    t_since = max(0.0, a.wall_clock - s.t_last_event)
    cwnd = s.cwnd + C * (t_since ** 3)
    W_max, t_last_event, ssthresh = s.W_max, s.t_last_event, s.ssthresh
    if a.is_loss:
        cwnd, W_max, t_last_event, ssthresh = (
            beta * s.cwnd, s.cwnd, a.wall_clock, beta * s.cwnd,
        )
    cwnd = max(MSS, cwnd)
    pacing_rate = cwnd / s.srtt
    return CubicState(
        cwnd=cwnd, W_max=W_max, t_last_event=t_last_event,
        ssthresh=ssthresh, pacing_rate=pacing_rate, srtt=s.srtt,
    )


def step_reno(
    s: RenoState, a: AckEvent, *, MSS: float,
) -> RenoState:
    """One step of the Reno substep chain per reno.yaml."""
    if s.in_slow_start:
        cwnd = s.cwnd + MSS
    else:
        cwnd = s.cwnd + (MSS * MSS) / max(s.cwnd, MSS)
    ssthresh = s.ssthresh
    in_slow_start = s.in_slow_start
    if a.is_loss:
        cwnd = s.cwnd / 2.0
        ssthresh = s.cwnd / 2.0
        in_slow_start = False
    cwnd = max(MSS, cwnd)
    pacing_rate = cwnd / s.srtt
    return RenoState(
        cwnd=cwnd, ssthresh=ssthresh, pacing_rate=pacing_rate,
        srtt=s.srtt, in_slow_start=in_slow_start,
    )
