# Preregistration: clocked-ACK starvation-onset prediction

This note preregisters the falsifiable experimental prediction from the
paper `bbr3-starvation-bench`. The prediction is stated here in advance
of the physical measurement; a positive measurement means the closed-form
theorem holds on the specified testbed, a negative measurement falsifies
it (within the stated tolerances) and the paper is retracted.

## Hypothesis

On a clocked-ACK testbed with ACK aggregation burst `B` tunable from
`0.25 D` to `4 D`, where `D` is the measured equilibrium delay range, the
BBRv3 starvation-onset time `T_emp` satisfies

    T_emp ~ ((B / D) - 2) * W + c

where `W` is the BBRv3 min-RTT filter window (draft default 10 s) and
`c` is a constant derived from the BBRv3 state-machine constants and
machine-checked by the `c_bounded_by_W` lemma in
`lean/BbrStarvation/OnsetTheorem.lean`.

## Falsifiable statements

1. **Proportionality.** For `B / D > 2`, onset time is linear in
   `(B / D) - 2` with slope `W` and intercept `c`. A Pearson correlation
   below 0.85 between the empirical and analytic values across the
   sixfold `B / D` grid falsifies this.
2. **Independence of link rate.** Onset time is independent of the
   physical link rate across the fourfold rate grid (10, 100, 1000,
   10000 Mbps). A coefficient of variation above 0.20 across rates at a
   fixed `B / D` cell falsifies this.
3. **Boundary condition.** At `B = 2 D` the onset time equals `c`
   within one RTT. A measured onset more than `c + W / 10` at that
   boundary cell falsifies this.

## Testbed

Physical testbed specification:
- Two-endpoint dumbbell topology on a pair of bare-metal Linux servers
  running kernel 6.x with Cardwell BBR v3 backport applied.
- Emulated bottleneck via `tc netem` with `rate = R Mbps`, `delay = D / 2
  ms each way`, and a custom ACK-aggregation module emitting bursts of
  `B` ACKs at a period derived from the link rate.
- Each cell runs `N = 100` trials; each trial observes the sender's
  `inflight` counter via `ss -ti` at 1 ms granularity until either
  starvation (`inflight == 0` sustained for `>= 2 * D`) or `T_max = 10 s`.

## Fallback to simulator

If no bare-metal testbed is available, the packet simulator at
the bundled congestion-control environment substitutes for the
physical testbed. The simulator's ACK-aggregation emulation is an
approximation (see `experiments/README.md`); we report both the
simulator-only result and, when available, the bare-metal result.

## Non-deniability

This preregistration is committed to the repository before the physical
measurement is attempted. The commit hash that introduces this file
is part of the paper artifact. The paper's Section 5.3 reports the
measurement outcome whether it supports or falsifies the hypothesis.

## Filed

_Filed by @qa (qa-agent) 2026-04-19. Commit hash: (this commit, to be
read from `git log --oneline -1`)._
