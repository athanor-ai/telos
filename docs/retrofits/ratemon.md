# Retrofit — ratemon (Canel, cmu-snap)

**Target:** [github.com/cmu-snap/ratemon](https://github.com/cmu-snap/ratemon)
**Existing claim surface:** receiver-side pacing of BBR vs Cubic
flows to enforce a fairness ratio. Implicit claim: fairness
converges to within [1-ε, 1+ε] of equal share after a bounded
transient.

## What telos adds

A machine-checked fairness-ratio theorem plus an EBMC-verified
rwnd-cap enforcement correctness invariant. Both compile from
one spec; together they bound steady-state behaviour AND rule
out the "fairness holds by coincidence of a deadlock" failure
mode.

## Example spec

```yaml
version: "0.1"

protocol:
  name: ratemon_receiver
  citation: "Canel et al., ratemon (cmu-snap)"
  state:
    - { name: bbr_cwnd,      type: real }
    - { name: cubic_cwnd,    type: real }
    - { name: bottleneck_q,  type: real }
    - { name: rwnd_cap,      type: real }
  params:
    - { name: bandwidth,     type: real }
    - { name: min_rtt,       type: real }
  substeps:
    - { name: measure_rtt,    modifies: [bottleneck_q] }
    - { name: compute_pacing, modifies: [rwnd_cap]     }
    - { name: apply_rwnd_cap, modifies: [bbr_cwnd, cubic_cwnd] }
  step_compose: [measure_rtt, compute_pacing, apply_rwnd_cap]

theorems:
  - name: ratemon_fairness_ratio
    kind: invariant
    doc: "steady-state fairness within 10% of equal share"
    hypotheses:
      - "t >= 10 * min_rtt"
    conclusion: "fairness_ratio(bbr_cwnd, cubic_cwnd) in [0.9, 1.1]"

  - name: ratemon_rwnd_cap_no_deadlock
    kind: invariant
    doc: "rwnd cap never forces the bottleneck queue to drain fully"
    conclusion: "forall n, rwnd_cap(state n) > 0 or bottleneck_q(state n) > 0"

verifiers:
  lean4:     { mathlib: pinned }
  ebmc:      { k_induction: true }
  hypothesis: { examples: 5000 }
  cpu_sim:
    grid:
      bandwidth: [10, 100, 1000]   # Mbps
    seeds: 100
```

## Why Canel cares

- **Active maintainer; weekly commits.** Low-friction PR target.
- **Explicit claim that the project currently cannot machine-check.**
  telos converts the existing empirical fairness check into a
  sandwich-bounded theorem.
- **Small codebase; clear protocol boundary.** telos retrofit
  fits in one example spec + one doc pointer.

## PR path

One-line PR to [cmu-snap/ratemon](https://github.com/cmu-snap/ratemon):

> `verification/ratemon-telos.yaml` — machine-checks the
> fairness ratio + rwnd-cap no-deadlock invariant. Run with
> `telos verify verification/ratemon-telos.yaml`.

Implementation effort: ~3 hours once telos v0.3 backends land.
