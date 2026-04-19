# Retrofit — CCmatic (Agarwal-Arun NSDI 2024)

**Target:** [github.com/108anup/ccmatic](https://github.com/108anup/ccmatic)
**Existing claim surface:** CEGIS-over-Z3 synthesis of CCAs against the
CCAC fluid model. Proves a single Z3 lemma per synthesized CCA.
**Open question in the CCmatic 2024 write-up:** *"tighten proofs of CCA
performance."*

## What telos adds

telos compiles the same `(protocol, substeps, theorem)` spec into
five verifier inputs instead of one. The CCmatic Z3 path remains;
telos adds:

- Lean 4 liveness proof (standard library + Mathlib).
- Dafny 4.x loop invariant for the executable CCA.
- Hypothesis property test over a Python CPU simulator matching
  the synthesized step function.
- EBMC k-induction on a SystemVerilog shadow (for any bounded-
  state fragment of the CCA).

A CCmatic user edits a single `spec.yaml` describing the CCA
under synthesis + the performance claim; `telos verify` returns
five verdicts. Where they agree, the performance claim is
sandwich-bounded. Where they disagree, the spec-to-artefact
translation has a bug and CCmatic's existing Z3 proof is a
necessary-but-not-sufficient witness.

## Example spec

```yaml
version: "0.1"

protocol:
  name: slakh_aimd   # a CCmatic-synthesized CCA
  citation: "Agarwal-Arun NSDI 2024"
  state:
    - { name: cwnd,     type: real, doc: "congestion window" }
    - { name: rtt,      type: real, doc: "most recent RTT sample" }
    - { name: loss,     type: real, doc: "loss-rate EWMA" }
  params:
    - { name: min_rtt,  type: real }
    - { name: buffer,   type: nat  }
  substeps:
    - { name: probe,    modifies: [cwnd]          }
    - { name: drain,    modifies: [cwnd, loss]    }
    - { name: cruise,   modifies: [cwnd, rtt]     }
  step_compose: [probe, drain, cruise]

theorems:
  - name: slakh_performance
    kind: invariant
    doc: "utilisation and delay bounds under an adversarial link"
    hypotheses:
      - "adversary.delay_jitter <= 0.2"
      - "adversary.loss_burst <= 3"
    conclusion:
      - "utilisation >= 0.5"
      - "p99_delay <= 2 * min_rtt"

verifiers:
  lean4:     { mathlib: pinned }
  dafny:     { container: "ghcr.io/athanor-ai/dafny-base:2026.04.10" }
  ebmc:      { k_induction: true, bmc_bound: 100 }
  hypothesis: { examples: 5000 }
  cpu_sim:
    grid:
      delay_jitter: [0.0, 0.1, 0.2]
      loss_burst:   [0, 1, 2, 3]
    seeds: 100
```

## Outputs at verify time

```
[Lean 4]      slakh_performance          — sorry-free
[Dafny]       SlakhAimd.SlakhPerformance — verified, 0 errors
[EBMC]        p_util_lower_bound         — PROVED at k=100
[EBMC]        p_p99_delay_upper_bound    — PROVED at k=100
[Hypothesis]  5000/5000 pass
[CPU sim]     12/12 cells pass

SANDWICH BOUND (slakh_aimd performance, CCmatic-synthesized):
  utilisation >= 0.5 in all 5 backends
  p99_delay  <= 2 * min_rtt in all 5 backends
```

## Why Agarwal's group cares

1. **Answers the "tighten proofs" open question** from CCmatic 2024.
2. **Keeps CCmatic's Z3 verdict** as one of the five, not a
   replacement. Their existing work is preserved.
3. **Extends from a single-property proof to a joint sandwich**
   (utilisation AND p99_delay AND fairness AND …) because the
   telos spec can declare multiple theorems against the same
   protocol.
4. **No rewrite of the synthesizer required.** CCmatic's CEGIS
   loop calls `telos verify` once per candidate CCA; failing
   verdicts become new negative examples for the CEGIS loop.

## PR path

One-line PR to [108anup/ccmatic](https://github.com/108anup/ccmatic):

> `examples/slakh-aimd-telos.yaml` — cross-checks the Z3 lemma
> from `proofs/slakh_aimd.smt2` against Lean 4, Dafny, Hypothesis,
> EBMC, and a CPU sim. Run with `telos verify
> examples/slakh-aimd-telos.yaml`.

Implementation effort: ~2 hours once telos v0.3 backends are in.
