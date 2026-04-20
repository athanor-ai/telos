#!/usr/bin/env python3
"""hypothesis_patched.py — Hypothesis property-based sweep on F*.

Randomised check of the positive theorem
`no_starvation_under_F_star` (§VII): for every (W, B, D, schedule)
drawn from the strategies below, and for every tick n in a finite
horizon, the patched-filter pacing_rate is strictly positive.

Cross-check for the Lean/Dafny/EBMC statements. If any random
combination starves, Hypothesis will shrink to a minimal falsifying
example and report it; in practice the theorem holds because
`F*`'s EWMA carries unbounded memory and cannot be drained to zero
in finite time from a positive initial pacing_rate.

Targets 5000 examples per release run. ~0.5 s per example on the
reference host.

Usage:
    pytest experiments/hypothesis_patched.py --hypothesis-profile=ci
    # or:
    python3 experiments/hypothesis_patched.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make `reference_cca` importable.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from reference_cca.bbrv3_lean_port import (  # noqa: E402
    AckEvent, BBRState, step_patched,
)

try:
    from hypothesis import given, settings, strategies as st, Verbosity
    import hypothesis
except ImportError:
    print("hypothesis missing — pip install hypothesis", file=sys.stderr)
    sys.exit(2)


HORIZON = 60  # ticks per trace


def _build_random_schedule(W: int, B: int, D: int, mask: list[bool]) -> list:
    """Schedule derived from a boolean mask: True = delivered burst,
    False = zero-delivery tick. Covers aggregating + quiescent +
    arbitrary mixtures in a single parameter space."""
    sched = []
    for i, quiet in enumerate(mask):
        if quiet:
            delivered = 0
        else:
            delivered = max(1, int(B * D))
        sched.append(AckEvent(
            burst_size=max(1, delivered or 1),
            delivered=delivered,
            wall_clock=float(D),
        ))
    return sched


def _run_fstar(W: int, B: int, D: int, schedule: list) -> tuple[float, float]:
    """Run F* over the schedule. Return (min_rate, final_rate)."""
    s = BBRState(W=W)
    # Positive initial pacing_rate — hypothesis of no_starvation_under_F_star.
    assert s.pacing_rate > 0
    min_rate = s.pacing_rate
    for a in schedule:
        s = step_patched(s, a)
        if s.pacing_rate < min_rate:
            min_rate = s.pacing_rate
    return min_rate, s.pacing_rate


# ─── Hypothesis profile ─────────────────────────────────────────────
hypothesis.settings.register_profile(
    "ci", max_examples=10000, deadline=2000,
    verbosity=Verbosity.quiet,
)
hypothesis.settings.register_profile(
    "quick", max_examples=200, deadline=2000,
)
hypothesis.settings.register_profile(
    "mega", max_examples=100_000, deadline=5000,
    verbosity=Verbosity.quiet,
)


@given(
    W=st.integers(min_value=2, max_value=32),
    B=st.integers(min_value=1, max_value=12),
    D=st.integers(min_value=1, max_value=8),
    mask=st.lists(st.booleans(), min_size=HORIZON, max_size=HORIZON),
)
@settings(hypothesis.settings.get_profile(
    os.environ.get("HYPOTHESIS_PROFILE", "quick")
))
def test_no_starvation_under_F_star(W: int, B: int, D: int, mask: list[bool]):
    """For every random (W, B, D, schedule), F*'s pacing_rate stays
    strictly positive over a HORIZON-tick trace. This is the
    empirical companion to Theorem 'No starvation under F*'."""
    schedule = _build_random_schedule(W, B, D, mask)
    min_rate, final_rate = _run_fstar(W, B, D, schedule)
    assert min_rate > 0, (
        f"starvation detected: W={W} B={B} D={D} "
        f"min_rate={min_rate} final_rate={final_rate}"
    )


def main() -> int:
    """Standalone runner — runs 200 examples quickly, reports pass-count."""
    profile = os.environ.get("HYPOTHESIS_PROFILE", "quick")
    hypothesis.settings.load_profile(profile)
    print(f"[hypothesis_patched] profile={profile}, "
          f"max_examples={hypothesis.settings.default.max_examples}")
    failures = []

    @given(
        W=st.integers(min_value=2, max_value=32),
        B=st.integers(min_value=1, max_value=12),
        D=st.integers(min_value=1, max_value=8),
        mask=st.lists(st.booleans(), min_size=HORIZON, max_size=HORIZON),
    )
    @settings(hypothesis.settings.get_profile(profile))
    def _run(W, B, D, mask):
        schedule = _build_random_schedule(W, B, D, mask)
        min_rate, _ = _run_fstar(W, B, D, schedule)
        if min_rate <= 0:
            failures.append((W, B, D, mask, min_rate))
            raise AssertionError(
                f"starve: W={W} B={B} D={D} min={min_rate}")

    try:
        _run()
    except AssertionError as e:
        print(f"[hypothesis_patched] FAIL: {e}", file=sys.stderr)
        for f in failures:
            print(f"  counterexample: {f}", file=sys.stderr)
        return 1
    print(f"[hypothesis_patched] PASS — 0 starving traces across "
          f"{hypothesis.settings.default.max_examples} random cells")
    return 0


if __name__ == "__main__":
    sys.exit(main())
