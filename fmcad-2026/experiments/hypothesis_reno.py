#!/usr/bin/env python3
"""hypothesis_reno.py — Hypothesis property sweep on Reno's positive theorem.

For every (MSS, srtt, cwnd_0, in_slow_start, loss_schedule) drawn from the
strategies below, `pacing_rate > 0` at every tick of a HORIZON-tick trace.
Empirical companion for the Lean `no_starvation_under_bounded_ack_reno`
theorem asabi drops in lean/Reno.lean.

Usage:
    pytest experiments/hypothesis_reno.py --hypothesis-profile=ci
    python3 experiments/hypothesis_reno.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from reference_cca.aimd_lean_port import (  # noqa: E402
    AckEvent, RenoState, step_reno,
)

try:
    import hypothesis
    from hypothesis import given, settings, strategies as st, Verbosity
except ImportError:
    print("hypothesis missing — pip install hypothesis", file=sys.stderr)
    sys.exit(2)


HORIZON = 60


hypothesis.settings.register_profile(
    "ci", max_examples=10000, deadline=2000, verbosity=Verbosity.quiet,
)
hypothesis.settings.register_profile(
    "quick", max_examples=200, deadline=2000,
)

hypothesis.settings.register_profile(
    "mega", max_examples=100_000, deadline=5000,
)


@given(
    MSS=st.floats(min_value=512.0, max_value=9000.0),
    srtt=st.floats(min_value=1e-3, max_value=1.0),
    cwnd_0_mult=st.floats(min_value=1.0, max_value=64.0),
    in_slow_start=st.booleans(),
    loss_mask=st.lists(st.booleans(), min_size=HORIZON, max_size=HORIZON),
)
@settings(hypothesis.settings.get_profile(
    os.environ.get("HYPOTHESIS_PROFILE", "quick")
))
def test_reno_never_starves(
    MSS, srtt, cwnd_0_mult, in_slow_start, loss_mask,
):
    """Reno pacing_rate > 0 for every tick, regardless of loss schedule."""
    s = RenoState(
        cwnd=cwnd_0_mult * MSS,
        ssthresh=cwnd_0_mult * MSS,
        pacing_rate=(cwnd_0_mult * MSS) / srtt,
        srtt=srtt,
        in_slow_start=in_slow_start,
    )
    assert s.pacing_rate > 0
    wall_clock = 0.0
    for is_loss in loss_mask:
        wall_clock += srtt
        a = AckEvent(is_loss=is_loss, wall_clock=wall_clock)
        s = step_reno(s, a, MSS=MSS)
        assert s.pacing_rate > 0, (
            f"Reno starvation counterexample: MSS={MSS} srtt={srtt} "
            f"cwnd_0={cwnd_0_mult * MSS} in_slow_start={in_slow_start} "
            f"at wall_clock={wall_clock} pacing_rate={s.pacing_rate}"
        )


def main() -> int:
    profile = os.environ.get("HYPOTHESIS_PROFILE", "quick")
    hypothesis.settings.load_profile(profile)
    print(f"[hypothesis_reno] profile={profile}, "
          f"max_examples={hypothesis.settings.default.max_examples}")
    try:
        test_reno_never_starves()
    except AssertionError as e:
        print(f"[hypothesis_reno] FAIL: {e}", file=sys.stderr)
        return 1
    print(f"[hypothesis_reno] PASS — 0 starving traces across "
          f"{hypothesis.settings.default.max_examples} random cells")
    return 0


if __name__ == "__main__":
    sys.exit(main())
