# Retrofit — BBQ HW packet scheduler (cmu-snap NSDI 2024)

**Target:** [github.com/cmu-snap/BBQ](https://github.com/cmu-snap/BBQ)
**Existing claim surface:** a priority-queue packet scheduler
synthesised in SystemVerilog for line-rate dequeue. Implicit
claim: dequeue returns min(priority) AND insert_latency <= 4
cycles AND no duplicates AND no loss.

## Why this is BBQ's sweet spot

BBQ is pure hardware: state is the priority-queue heap + validity
bitmap; steps are insert / dequeue / swap. EBMC k-induction is
the load-bearing verifier for correctness of such invariants.
telos lets BBQ ship a machine-checked assertion suite alongside
the existing SystemVerilog — the assertions compile from a spec,
stay in sync as the queue is optimised, and are independently
auditable.

## Example spec

```yaml
version: "0.1"

protocol:
  name: bbq_priority_queue
  citation: "Sharma et al., BBQ (NSDI 2024)"
  state:
    - { name: heap,           type: "seq<real>" }
    - { name: valid_bits,     type: "seq<bool>" }
    - { name: insert_count,   type: nat         }
    - { name: dequeue_count,  type: nat         }
  params:
    - { name: N,              type: nat,  doc: "heap capacity" }
  substeps:
    - { name: insert,   modifies: [heap, valid_bits, insert_count]  }
    - { name: dequeue,  modifies: [heap, valid_bits, dequeue_count] }
  step_compose: []   # operations are independent, not composed

theorems:
  - name: dequeue_returns_min
    kind: invariant
    conclusion: "dequeue(s, x).returned_priority = min_priority(s.heap, s.valid_bits)"

  - name: insert_latency_bound
    kind: invariant
    conclusion: "insert_latency(s, x) <= 4"

  - name: no_duplicate_packets
    kind: invariant
    conclusion: "forall t > 0, insert_count(t) = dequeue_count(t) + |{valid entries in heap}|"

  - name: no_packet_loss_at_line_rate
    kind: invariant
    hypotheses:
      - "arrivals_per_cycle <= 1"
    conclusion: "forall t, exists bounded_insert_delay(t) <= 4"

verifiers:
  ebmc:
    k_induction: true
    bmc_bound: 200
    concrete_tuple: { N: 64 }
  lean4:     { mathlib: pinned }       # optional; for meta-properties
  hypothesis: { examples: 10000 }
```

## Why the BBQ team cares

- **All four invariants are EBMC-checkable** today; BBQ's paper
  states them informally. telos moves them from prose to
  machine-checked assertions without rewriting the SystemVerilog.
- **High star count (22)**, so a merged retrofit earns visibility.
- **Establishes non-CC generality** of telos — the same DSL works
  for an HW packet scheduler that never sees an ACK. Paper §VII
  can cite this as the generalisation direction.

## PR path

Two-file PR to [cmu-snap/BBQ](https://github.com/cmu-snap/BBQ):

> `verification/bbq-telos.yaml` + `verification/README.md` —
> four machine-checked SVA assertions compiled from the telos
> spec. EBMC k-induction verifies at heap capacity N=64.

Implementation effort: ~4 hours once telos v0.3 ebmc backend lands.

## Future extension

The `spec-from-trace` inference primitive (earmarked for telos
v0.5) would let BBQ auto-derive the spec from a trace of the
RTL simulation. That turns the retrofit into a one-command
workflow: `telos infer simulation.vcd | telos verify`.
