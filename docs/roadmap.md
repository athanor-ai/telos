# telos roadmap

## v0.1 (scaffold, this release)
- Spec schema + pydantic validation. ✅
- First example: `examples/bbrv3-starvation.yaml`. ✅
- CLI stubs: `telos compile | verify | pack`. ✅
- CI: `pytest` + `setup.sh` smoke. ✅
- Backend modules under `telos/backends/` present but stub-only.

## v0.2 (compile-to-artefacts — target Week 2)
- `backends/lean4.py`: emit `BbrStarvation/{Basic,Trace,Theorem}.lean`
  from a spec. Verify `lake build` succeeds.
- `backends/dafny.py`: emit `<Protocol>.dfy`. Verify inside the
  dafny-base container.
- `backends/ebmc.py`: emit `<protocol>_trace.sv` +
  `<protocol>_invariants.sv`. Verify via EBMC k-induction.
- `backends/hypothesis.py`: emit a pytest file with strategies
  matching the spec's state schema.
- `backends/cpusim.py`: emit a CPU-sim runner script and a
  gridded sweep config.

## v0.3 (replication pack + Docker)
- `telos pack` generates a complete reproducibility tarball
  (Dockerfile, `run.sh`, pinned versions, deterministic seeds).
- Every example in `examples/` is end-to-end reproducible from a
  clean `docker build`.

## v0.4 (community retrofits)
- `docs/retrofits/ccmatic.md` — tighten Agarwal-Arun Z3-only
  CEGIS proofs into a 5-backend sandwich.
- `docs/retrofits/ratemon.md` — formalize cmu-snap/ratemon's
  BBR-vs-Cubic fairness ratio.
- `docs/retrofits/bbq.md` — priority-queue invariants for the
  NSDI-24 HW scheduler.

## Future primitives (earmarked in the schema)
- Harm-metric predicates (Ware HotNets-19 framework).
- Trace-to-spec inference (Ferreira Abagnale methodology).
- HW-SVA emit templates (BBQ-style).
- CEGIS adversary generation (CCmatic pattern).
- Fairness-ratio predicates with tolerance bounds (ratemon).

## Not in scope
- LLM-driven spec authoring or proof search. telos is the
  machine-checking half only; LLM orchestration lives elsewhere.
- Kernel patches or live deployment. telos verifies the
  abstraction; real-kernel experiments are a separate artefact.
