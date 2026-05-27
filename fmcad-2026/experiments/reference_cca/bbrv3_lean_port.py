"""bbrv3_lean_port.py — direct Python port of BbrStarvation.Trace.step.

One-to-one translation of the Lean state machine in `lean/BbrStarvation/
Trace.lean` (post-ATH-355 windowed-max). Used by `b_d_grid.py` to
empirically validate the closed-form starvation-onset bound
`T(B,D) = (B/D − 2)·W + c` against simulated traces.

Correspondence (Lean → Python):
    BBRState W       → BBRState (dataclass, W as a field)
    Fin W            → index into a fixed-length list
    min_rtt_filt     → List[float] of length W (slot 0 = youngest)
    bw_filt          → List[float] of length W
    pacing_rate      → float
    cwnd_gain        → float (constant 1.0 in this abstraction)
    pacing_gain      → float, cycles through {5/4, 3/4, 1, 1, 1, 1, 1, 1}
    phase            → int in [0, 8)
    mode             → enum {Startup, Drain, ProbeBW, ProbeRTT}
    step(s, a)       → step(s, a)

Design note: NOT a full BBRv3 implementation. This is the Lean
*abstraction* of BBRv3 that the starvation-onset theorem is stated
over. By-construction equivalence to the Lean step means the
empirical residual `T_emp − T_analytic` measures whether the
closed-form sandwich bound holds under realistic ACK schedules —
which is the CAV/PLDI/POPL acceptance criterion (ATH-362).

Full real-BBRv3 validation (ns-3 / Linux kernel tcp_bbr.c replay) is
out of scope; paper §limitations cites draft-ietf-ccwg-bbr-05 §4.4 as
the spec source-of-truth that this abstraction tracks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class BBRMode(Enum):
    STARTUP = "Startup"
    DRAIN = "Drain"
    PROBE_BW = "ProbeBW"
    PROBE_RTT = "ProbeRTT"


@dataclass
class AckEvent:
    """Mirrors Lean `AckEvent`: one ACK visible to the sender."""
    burst_size: int      # bytes ACKed in this burst
    delivered: int       # cumulative delivered bytes as of this ACK
    wall_clock: float    # elapsed wall time since send (ms)


@dataclass
class BBRState:
    """Mirrors Lean `BBRState W`.

    `W` is the filter window width (RTTs). The paper's closed-form
    bound `T(B,D) = (B/D − 2)·W + c` is parametric in W.
    """
    W: int
    mode: BBRMode = BBRMode.PROBE_BW
    pacing_rate: float = 1.0
    inflight: int = 0
    min_rtt_filt: List[float] = field(default_factory=list)
    bw_filt: List[float] = field(default_factory=list)
    cwnd_gain: float = 1.0   # cap — ATH-355 shows this binding is the onset trigger
    pacing_gain: float = 1.0
    phase: int = 0
    rt_elapsed: float = 0.0

    def __post_init__(self) -> None:
        if not self.min_rtt_filt:
            self.min_rtt_filt = [0.0] * self.W
        if not self.bw_filt:
            self.bw_filt = [0.0] * self.W


# ─── Sub-step functions (one-to-one with Lean) ─────────────────────────


def filter_update(s: BBRState, a: AckEvent) -> BBRState:
    """Mirrors `Trace.filter_update`. Slide the min-RTT filter by one
    age bucket and insert the fresh sample at slot 0."""
    new_filt = [a.wall_clock] + s.min_rtt_filt[:-1]
    s.min_rtt_filt = new_filt
    s.rt_elapsed = s.rt_elapsed + a.wall_clock
    return s


def bandwidth_update(s: BBRState, a: AckEvent) -> BBRState:
    """Mirrors `Trace.bandwidth_update` (post-ATH-355 windowed max).

    Lean: `let sample := delivered / (wall_clock + 1)`.
          Slide `bw_filt` and insert sample at index 0.
          pacing_rate := max over the W-slot window (seed 0).
    """
    sample = float(a.delivered) / (a.wall_clock + 1.0)
    new_bw_filt = [sample] + s.bw_filt[:-1]
    s.bw_filt = new_bw_filt
    # List.foldr max 0 over the window — matches the Lean fold exactly.
    windowed_max = 0.0
    for v in new_bw_filt:
        if v > windowed_max:
            windowed_max = v
    s.pacing_rate = windowed_max
    return s


def mode_transition(s: BBRState, _a: AckEvent) -> BBRState:
    """Mirrors `Trace.mode_transition`."""
    if s.mode is BBRMode.STARTUP:
        s.mode = BBRMode.DRAIN
    elif s.mode is BBRMode.DRAIN:
        s.mode = BBRMode.PROBE_BW
    elif s.mode is BBRMode.PROBE_BW:
        pass  # steady state
    elif s.mode is BBRMode.PROBE_RTT:
        s.mode = BBRMode.PROBE_BW
    return s


def pacing_gain_cycle(s: BBRState) -> BBRState:
    """Mirrors `Trace.pacing_gain_cycle`. 8-phase cycle
    {5/4, 3/4, 1, 1, 1, 1, 1, 1}."""
    new_phase = (s.phase + 1) % 8
    if new_phase == 0:
        new_gain = 5.0 / 4.0
    elif new_phase == 1:
        new_gain = 3.0 / 4.0
    else:
        new_gain = 1.0
    s.phase = new_phase
    s.pacing_gain = new_gain
    return s


def cwnd_compute(s: BBRState) -> BBRState:
    """Mirrors `Trace.cwnd_compute`.

    pacing_rate := min(bw_est * pacing_gain, bw_est * cwnd_gain)
    """
    target = s.pacing_rate * s.pacing_gain
    cap = s.pacing_rate * s.cwnd_gain
    s.pacing_rate = min(target, cap)
    return s


def step(s: BBRState, a: AckEvent) -> BBRState:
    """One full step of the BBRv3 state machine (Lean `Trace.step`)."""
    s = filter_update(s, a)
    s = bandwidth_update(s, a)
    s = mode_transition(s, a)
    s = pacing_gain_cycle(s)
    s = cwnd_compute(s)
    return s


# ─── Patched filter F* (ATH-372 — positive companion theorem) ──────────


def bandwidth_update_patched(s: BBRState, a: AckEvent) -> BBRState:
    """Mirrors Lean `PatchedFilter.bandwidth_update_patched`.

    Two-stage filter that fixes BOTH failure modes BBRv3 exhibits:

      1. Burst normalization — the per-ACK delivered-rate sample is
         normalized by the observed ACK aggregation count
         `a.burst_size` before the filter sees it. Prevents the
         aggregation regime from inflating the estimate.

      2. Exponentially weighted moving average — the filter state is
         an EWMA with time constant `tau = W` (in ticks) rather than
         a hard windowed max. An EWMA never drops to zero on a single
         zero sample; instead it decays gradually, so a quiescent
         window of length W reduces the estimate by a factor of at
         most 1/e ≈ 0.37, never all the way to zero. Combined with
         (1), this is the class of filter whose positive theorem
         `no_starvation_under_F_star` holds.

    See audit/ATH-372-patched-filter-design.md (revised) for the
    motivation and the updated theorem statement.
    """
    burst = max(a.burst_size, 1)
    sample = float(a.delivered) / ((a.wall_clock + 1.0) * burst)
    # Slide the burst-averaged sample history for record-keeping (and
    # so EBMC / Dafny can observe a W-slot history window).
    new_bw_filt = [sample] + s.bw_filt[:-1]
    s.bw_filt = new_bw_filt
    # EWMA update. tau = W (filter window width in ticks). The weight
    # on the new sample is 1/W; the rest carries the prior estimate.
    # This is equivalent to a discrete low-pass with cut-off ~ W ticks.
    alpha = 1.0 / max(s.W, 1)
    prior = s.pacing_rate
    s.pacing_rate = alpha * sample + (1.0 - alpha) * prior
    return s


def step_patched(s: BBRState, a: AckEvent) -> BBRState:
    """One full step of the patched BBRv3 state machine.

    Identical to `step` except the bandwidth-update sub-step is
    `bandwidth_update_patched` (sample normalized by burst size).
    """
    s = filter_update(s, a)
    s = bandwidth_update_patched(s, a)
    s = mode_transition(s, a)
    s = pacing_gain_cycle(s)
    s = cwnd_compute(s)
    return s


# ─── Onset-detection helper ─────────────────────────────────────────────


def starved(s: BBRState, threshold: float = 0.0) -> bool:
    """Matches the `starved` predicate we're refining (Option C).

    Original Lean predicate: `pacing_rate = 0`.
    Option C refined: `pacing_rate <= threshold(D)` — the paper picks a
    threshold derived from path-delay D. Caller supplies the threshold.
    """
    return s.pacing_rate <= threshold


def simulate(
    W: int,
    B: float,
    D: float,
    schedule: List[AckEvent],
    threshold: float = 0.0,
    filter_kind: str = "bbrv3",
) -> int:
    """Run `step` over the given schedule, return the first tick n for
    which `starved(state, threshold)` holds. Returns len(schedule) if
    starvation never reached within the horizon.

    `filter_kind` selects which bandwidth-update sub-step to use:
      - "bbrv3"   (default) — BBRv3's windowed-max on instantaneous
                  delivered-rate samples. Paper's starvation theorem
                  proves this starves under B > 2D.
      - "fstar"   — patched filter F* (ATH-372). Samples are
                  normalized by burst size before insertion. Paper's
                  positive companion theorem proves this does NOT
                  starve under the same regime.
    """
    # Initial state mirrors the theorem's hypothesis on t.state 0:
    # ProbeBW mode, pacing_rate = 1, cwnd_gain = 1, pacing_gain = 1.
    s = BBRState(W=W)
    step_fn = step_patched if filter_kind == "fstar" else step
    for n, a in enumerate(schedule):
        s = step_fn(s, a)
        if starved(s, threshold):
            return n
    return len(schedule)
