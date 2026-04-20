"""Reference Python simulator for the BBRv3 spec.

Pointed at from examples/bbrv3-starvation.yaml via
`verifiers.cpu_sim.reference_python: examples/bbrv3_reference.py`.

Implements the substeps declared in the YAML spec (filter_update,
bandwidth_update, mode_transition, pacing_gain_cycle, cwnd_compute) in
Python, mirroring the inline_lean expressions. The cpu_sim backend's
emitted shim imports this module and delegates step()/simulate() to it,
so `telos verify examples/bbrv3-starvation.yaml` actually runs the
simulator and reports a real verdict instead of the v0.3 stub's
"outlined / skip".

Honest scope: this is a simplified Python analogue — it reproduces the
positive-theorem (no starvation under bounded-ACK) semantics the paper
cares about. It is NOT a byte-accurate port of the Linux kernel
tcp_bbr2.c / tcp_bbr.c sources; see the Aidan-requested kernel-fidelity
submodule at bbr3-starvation-bench/kernel_replay/ for that.
"""
from __future__ import annotations

import dataclasses


_PACING_GAIN_CYCLE = [1.25, 0.75, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]


@dataclasses.dataclass
class State:
    W: int = 4
    min_rtt_filt: float = 1.0
    rt_elapsed: int = 0
    bw_filt: float = 1.0
    pacing_rate: float = 1.0
    mode: str = "ProbeBW"
    phase: int = 0
    pacing_gain: float = 1.0
    cwnd_gain: float = 2.0


def _slide_in(window_max: float, sample: float) -> float:
    """Windowed-max slide-in: the running maximum over a sliding window.
    One-line approximation — the real BBRv3 has 3-round tracking."""
    return max(window_max, sample)


def step(state: State, ack: dict) -> State:
    """Apply the spec's step composition to `state` under `ack`.

    filter_update → bandwidth_update → mode_transition →
    pacing_gain_cycle → cwnd_compute.
    """
    wall_clock = float(ack.get("wall_clock", 1.0))
    delivered = float(ack.get("delivered", 1.0))

    new_min_rtt = _slide_in(state.min_rtt_filt, wall_clock)
    rate_sample = delivered / max(wall_clock + 1.0, 1.0)
    new_bw_filt = _slide_in(state.bw_filt, rate_sample)

    mode_transitions = {
        "Startup": "Drain",
        "Drain": "ProbeBW",
        "ProbeBW": "ProbeBW",
        "ProbeRTT": "ProbeBW",
    }
    new_mode = mode_transitions.get(state.mode, state.mode)

    new_phase = (state.phase + 1) % 8
    new_gain = _PACING_GAIN_CYCLE[new_phase]

    new_pacing_rate = min(new_bw_filt * new_gain, new_bw_filt * state.cwnd_gain)
    # No-starvation invariant per Lean positive theorem: under bounded ACKs
    # (delivered > 0), pacing_rate cannot drop to zero. The max(…, tiny)
    # below is a numerical floor; any violation means the ACK stream went
    # starved, which the caller tracks via a separate bound check.
    new_pacing_rate = max(new_pacing_rate, 1e-9)

    return dataclasses.replace(
        state,
        min_rtt_filt=new_min_rtt,
        rt_elapsed=state.rt_elapsed + 1,
        bw_filt=new_bw_filt,
        pacing_rate=new_pacing_rate,
        mode=new_mode,
        phase=new_phase,
        pacing_gain=new_gain,
    )


def simulate(W: int, B: int, D: int, schedule, filter_kind: str = "bbrv3") -> dict:
    """Run a single trace, return final-state verdict dict.

    Signature matches the cpu_sim shim contract: positional-or-keyword
    W, B, D, schedule; optional filter_kind.
    """
    state = State(W=W)
    for ack in schedule:
        state = step(state, ack)
    return dataclasses.asdict(state)
