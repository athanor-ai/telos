# lean/

Lean 4 project for the BBRv3 starvation-onset theorem.

Toolchain: `lean-toolchain` pins Lean 4 v4.14.0. Mathlib is declared as a
`require` in `lakefile.lean`.

## Structure

```
lakefile.lean                       package + mathlib dependency
lean-toolchain                      Lean 4 version pin
BbrStarvation/
  Basic.lean                        types (BBRMode, PathParams, BBRState,
                                    AckEvent, World), onsetTime, starved
  Trace.lean                        transition function factored into 5 pure
                                    sub-steps, trace semantics
  OnsetTheorem.lean                 8 supporting lemmas + the main theorem
                                    `starves_within`, all `sorry` bodies
```

## ATH-340 fleet closure

Every `sorry` in `OnsetTheorem.lean` and the five sub-step bodies in
`Trace.lean` is a target for the ATH-340 fleet pass. Expected acceptance:

- Zero `sorry` remaining after hand-written Mathlib closures.
- Axiom audit reports only `{propext, Classical.choice, Quot.sound}`.
- `lake build` exits 0.
- Per-theorem elapsed time logged to `experiments/runs/<stamp>/lean_closures.json`.

## Local build (after ATH-340 closes)

```bash
cd lean/
lake exe cache get   # fetch pre-built Mathlib
lake build
```
