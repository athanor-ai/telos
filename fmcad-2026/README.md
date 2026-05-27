# fmcad-2026/

Artifacts from the FMCAD 2026 submission *"Telos: A Domain-Specific
Language for Machine-Checked Congestion-Control Verification"*.
This tree is the permanent replication archive; the Telos DSL
itself lives at the repository root (`telos/`, `examples/`, etc.).

## Subtree layout

Every path matches the relative reference used in the paper body
and in the `ARTIFACT-EVAL.md` claim map.

- `lean/` — Lean 4 proof project. `BbrStarvation/` contains the
  closed-form starvation bound, the patched-filter positive
  theorem, the multi-flow corollary, and the kernel-fidelity
  refinement. `CC/` contains the CUBIC + Reno positive theorems.
- `dafny/` — Dafny/Z3 cross-replay. `BBRv3Trace.dfy`,
  `BBRv3PatchedFilter.dfy`, `Cubic.dfy`, `Reno.dfy`, plus helpers.
- `sv/` — SystemVerilog refinements + EBMC k-induction logs.
  `bbr3_trace.sv`, `bbr3_invariants.sv`, `bbr3_patched_trace.sv`,
  plus the emitted EBMC transcripts.
- `experiments/` — Hypothesis property sweeps (`hypothesis_*.py`),
  CPU-simulator reference (`reference_cca/bbrv3_lean_port.py`),
  the 1,200-cell residual grid (`b_d_grid.py`), mutation tensor
  (`mutation_sweep.py`), and figure generators (`figures/`).
- `kernel_replay/` — Mahimahi-based Linux kernel replay harness
  for §V.F's residual-bound validation. `results/sanity_cell.csv`
  + `results/summary.md` + per-cell `mm_up_*.log` raw traces.
- `figures/` — PDF figures used by `main.tex` (fig_pipeline,
  fig_proof_dag, fig_mutation_kill, fig_lean_proof_size,
  fig_residual_ecdf_scatter).
- `proofs/external-prover/` — External-prover project snapshots
  for the §VI catch-and-verify exemplar (16a52aab before-fix,
  fa17a115 after-fix). Contains the submitted Lean sources +
  prover-emitted summaries.
- `proofs/solve-runs/` — Per-run patched SystemVerilog artifacts
  + winner.txt for the §V.C + Table III CUBIC + Reno k=10 EBMC
  closures.

## One-command reproduction

From the repository root (NOT inside `fmcad-2026/`):

```bash
python3 -m telos.cli verify examples/bbrv3-starvation.yaml
```

Expected output: sandwich closure across all five backends
(lean4, dafny, ebmc, hypothesis, cpu_sim) under 20 minutes on
16 vCPU.

## Working tool for subsequent research

This repository is engineered to double as a working tool for
any congestion-control verification effort. To register a new
CCA:

1. Add `examples/<your-cca>.yaml` using the spec shape in
   `examples/bbrv3-starvation.yaml`.
2. Run `python3 -m telos.cli compile examples/<your-cca>.yaml`
   to emit the five backend artefacts.
3. Run `python3 -m telos.cli verify examples/<your-cca>.yaml`
   to drive each backend + collect the sandwich verdict.

Contributions via pull request against the public repository
are welcome.
