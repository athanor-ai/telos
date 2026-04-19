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

Expected output (on the BBRv3 example, ~5 s on 16 vCPU):

```
[starves_within]
  ✓ lean4       closed    wellformed skeleton, zero unproved
  ✓ dafny       closed    5 verified, 0 errors
  ✓ ebmc        closed    4 PROVED, 0 non-proved
  ✓ hypothesis  closed    1 passed (5000 examples)
  … cpu_sim     outlined  user-supplied step body
  SANDWICH: closed by 4 backends
```

A *wellformed* verdict means the emitted Lean skeleton typechecks
with no unproved obligations; supplying your own proof module
upgrades it to *proved*.

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
| `examples/bbrv3-starvation.yaml` | BBRv3 starves under B > 2D | 4-backend mechanical sandwich + cpu_sim outlined |

Community retrofits planned for `examples/` include a Cubic-toy
spec and the patched-filter F\* variant (see
`docs/retrofits/` for each target's adaptation notes).

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
