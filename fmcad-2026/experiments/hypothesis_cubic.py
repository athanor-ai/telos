#!/usr/bin/env python3
"""hypothesis_cubic.py — Hypothesis property sweep on CUBIC's positive theorem.

For every (MSS, C, beta, srtt, cwnd_0, schedule) drawn from the strategies
below, `pacing_rate > 0` at every tick of a HORIZON-tick trace. Companion
empirical closure for the Lean `no_starvation_under_bounded_ack_cubic`
theorem asabi drops in lean/Cubic.lean.

Usage:
    pytest experiments/hypothesis_cubic.py --hypothesis-profile=ci
    python3 experiments/hypothesis_cubic.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from reference_cca.aimd_lean_port import (  # noqa: E402
    AckEvent, CubicState, step_cubic,
)

try:
    import hypothesis
    from hypothesis import given, settings, strategies as st, Verbosity
except ImportError:
    print("hypothesis missing — pip install hypothesis", file=sys.stderr)
    sys.exit(2)


HORIZON = 60  # ticks per trace, same as BBRv3 sweep


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
    C=st.floats(min_value=0.1, max_value=1.0),
    beta=st.floats(min_value=0.3, max_value=0.9),
    srtt=st.floats(min_value=1e-3, max_value=1.0),
    cwnd_0_mult=st.floats(min_value=1.0, max_value=64.0),
    loss_mask=st.lists(st.booleans(), min_size=HORIZON, max_size=HORIZON),
)
@settings(hypothesis.settings.get_profile(
    os.environ.get("HYPOTHESIS_PROFILE", "quick")
))
def test_cubic_never_starves(
    MSS, C, beta, srtt, cwnd_0_mult, loss_mask,
):
    """CUBIC pacing_rate > 0 for every tick, regardless of loss schedule."""
    s = CubicState(
        cwnd=cwnd_0_mult * MSS, W_max=cwnd_0_mult * MSS,
        t_last_event=0.0, ssthresh=cwnd_0_mult * MSS,
        pacing_rate=(cwnd_0_mult * MSS) / srtt, srtt=srtt,
    )
    assert s.pacing_rate > 0
    wall_clock = 0.0
    for is_loss in loss_mask:
        wall_clock += srtt
        a = AckEvent(is_loss=is_loss, wall_clock=wall_clock)
        s = step_cubic(s, a, MSS=MSS, C=C, beta=beta)
        assert s.pacing_rate > 0, (
            f"CUBIC starvation counterexample: MSS={MSS} C={C} "
            f"beta={beta} srtt={srtt} cwnd_0={cwnd_0_mult * MSS} "
            f"at wall_clock={wall_clock} pacing_rate={s.pacing_rate}"
        )


def main() -> int:
    profile = os.environ.get("HYPOTHESIS_PROFILE", "quick")
    hypothesis.settings.load_profile(profile)
    print(f"[hypothesis_cubic] profile={profile}, "
          f"max_examples={hypothesis.settings.default.max_examples}")
    try:
        test_cubic_never_starves()
    except AssertionError as e:
        print(f"[hypothesis_cubic] FAIL: {e}", file=sys.stderr)
        return 1
    print(f"[hypothesis_cubic] PASS — 0 starving traces across "
          f"{hypothesis.settings.default.max_examples} random cells")
    return 0


if __name__ == "__main__":
    sys.exit(main())
