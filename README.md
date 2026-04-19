# telos

Machine-checked congestion-control verification. A small DSL:
one YAML spec compiles into Lean 4 + Dafny + EBMC + Hypothesis
+ CPU-sim cross-checks, plus a Docker-containerised replication
package.

## Quick start

```bash
# Install.
./setup.sh

# Verify the bundled BBRv3 starvation example end-to-end.
telos verify examples/bbrv3-starvation.yaml
```

Expected output:

```
[Lean 4]      starves_within            — sorry-free
[Dafny]       BBRv3Trace                — 25 verified, 0 errors
[EBMC]        p_onset_upper_bound       — PROVED at k=100
[Hypothesis]  5000/5000 pass
[CPU sim]     40/40 starve under quiescent schedule

SANDWICH BOUND: T(B, D) = (B/D - 2) * W + c
                |residual| <= 1 RTT on > 99% of 1,200 cells
```

## What this is for

You have a congestion-control algorithm and a claim about its
behaviour — "it starves under ACK aggregation", "it is fair to
competing flows", "it converges within k RTTs." You want a
machine-checked guarantee, but you don't want to hand-encode
the same state machine five times.

`telos` compiles one YAML spec into five verifier inputs, runs
each backend, and reconciles their verdicts into a single
sandwich bound. Backends that agree reinforce the claim;
backends that disagree expose a real bug.

## Examples

| Spec | Theorem | Result |
|------|---------|--------|
| `examples/bbrv3-starvation.yaml` | BBRv3 starves under B > 2D | 5-backend agreement |
| `examples/bbrv3-fstar.yaml` | The patched filter F* never starves | 5-backend agreement |
| `examples/cubic-toy.yaml` | Cubic reaches steady-state throughput | template for your own CCA |

## Retrofit targets (community wishlist)

`telos` is designed to retrofit cleanly onto existing
congestion-control verification work. Candidate adaptations in
`docs/retrofits/`:

- `docs/retrofits/ccmatic.md` — tighten the Z3-only CEGIS
  proofs from Agarwal-Arun NSDI-24 into a 5-backend sandwich.
- `docs/retrofits/ratemon.md` — formalize the receiver-side
  BBR-vs-Cubic fairness ratio from cmu-snap/ratemon.
- `docs/retrofits/bbq.md` — priority-queue invariants for the
  NSDI-24 HW scheduler, EBMC-primary.

## Layout

```
telos/
├── setup.sh              # one-command install (tested via CI)
├── telos/                # python package
│   ├── spec/             # spec schema (pydantic)
│   ├── backends/         # lean4, dafny, ebmc, hypothesis, cpusim
│   └── cli/              # `telos compile | verify | pack`
├── examples/             # reference specs
├── docs/                 # schema reference, tutorial, retrofits
├── Dockerfile            # one-container reproducibility
└── .github/workflows/    # CI: verify every example
```

## License

MIT. See `LICENSE`.

## Contact

For questions, open an issue or email the maintainers listed in
`MAINTAINERS`.
