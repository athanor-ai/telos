# Experimental sweep outputs

## What this directory contains

CSV outputs of `experiments/b_d_grid.py`, which runs the Python port
of the Lean `Trace.step` state machine
(`experiments/reference_cca/bbrv3_lean_port.py`) over a grid of
`(B, D, link_rate, seed)` cells and records the first tick at which
the refined `starved` predicate fires.

Two schedule models are exercised:

- **aggregating** — BBRv3's standard bursty ACK pattern: every
  `ceil(B)` ticks the sender sees a burst of `B*D` delivered
  bytes, between bursts zero delivery. Models the real deployment
  case.
- **quiescent** — a scheduler hypothesis with a block of `W`
  consecutive zero-delivery ticks at tick `2W` so the windowed-max
  filter fully drains.

## Headline results

### `b_d_grid_agg_thr0.csv` — aggregating schedule, original predicate

`starved := pacing_rate = 0` with `aggregating` schedule →
**0/40 cells starve** across
(B ∈ {3,4,5,6}, D ∈ {1ms, 5ms}, seeds 0-4).

This empirically reproduces the iteration-3 counterexample
(paper §V, iter-3): under a non-halting ACK stream, the
windowed-max `bw_filt` always contains at least one recent
non-zero sample, so `pacing_rate` never reaches 0 and the
existential in `starves_within` has no witness. The theorem is
false under its original statement.

### `b_d_grid_quiet_thr0.csv` — quiescent schedule, original predicate

Same predicate, but schedule has a `W`-tick block of zero delivery
at tick `2W` → **40/40 cells starve**, empirical residual clustered
around the analytic prediction (mean ≈ 0, range ±16 RTT).

This empirically validates the quiescent scheduler-hypothesis
refinement: add `hQuiescent : ∃ k, ∀ j ∈ [k, k+W), delivered j = 0`
to the theorem and the sandwich bound fires. The residual
`T_emp − T_analytic` is bounded — empirical backing of the
theoretical result.

### `b_d_grid_quiet_large.csv` — 1,200-cell primary residual sweep

The full 1,200-cell grid reported in the paper's §VI residual
sweep. Decomposition: 10 values of B × 6 values of D × 20 seeds
= 1,200 cells. See Table 2 in the paper for exact grid values.

## Reproducing

Same machine, any date:

```bash
cd bbr3-starvation-bench
python3 experiments/b_d_grid.py \
    --b-grid 3,4,5,6 --d-ms 1,5 --link-rate-mbps 100 \
    --seeds 5 --w-rtt 10 --t-max-s 3 \
    --schedule aggregating --threshold 0.0 \
    --out experiments/runs/b_d_grid_agg_thr0.csv

python3 experiments/b_d_grid.py \
    --b-grid 3,4,5,6 --d-ms 1,5 --link-rate-mbps 100 \
    --seeds 5 --w-rtt 10 --t-max-s 3 \
    --schedule quiescent --threshold 0.0 \
    --out experiments/runs/b_d_grid_quiet_thr0.csv
```

Results are deterministic in seed.

## Out of scope

The reference CCA used here is a direct Python port of the Lean
abstraction. This validates `Lean abstraction ↔ analytical bound`.
A complementary kernel-replay comparison against Linux
`tcp_bbr.c` lives in `kernel_replay/`; see the paper's §V.F for
that setup's scope.
