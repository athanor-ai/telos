# Summary of changes for run fa17a115-b155-476d-9aa5-b8f4e516ece1
All 5 theorems in `BoothFixed.lean` (namespace `BoothMulCorrectness`) are now closed without any banned tactics. Here's what was done:

**Theorem 1 — `boothIter_step_monotone`**: Proved by induction on `n`, using `rw` with `Nat.add_assoc` and `Nat.add_comm`.

**Theorem 2 — `booth_noop_shift`**: The original statement (without bounds on `s.A`) was **false** — a concrete counterexample is provided in a comment (`A=256, Q=0, Q_neg1=false`). The original is commented out and a corrected version with the additional hypothesis `hA : s.A < 256` is proved. The proof uses helper lemmas about what `boothStep` does in the no-op case (`boothStep_noop_A`, `boothStep_noop_Q`) and a chain of `rw` steps establishing the arithmetic identity `A/2 * 256 + (A%2)*128 + Q/2 = (A*256 + Q)/2` (via `shift_div_identity`).

**Theorem 3 — `A_bounded_after_n_steps`**: Proved by showing the general invariant that `boothStep` preserves `A < 512`. The `arShift` bound is verified over `Fin 512` using `of_decide_eq_true rfl`, and the three Booth cases (add/sub/noop) each produce `A_booth < 512` via `% 512` or the induction hypothesis. Then induction on `n` finishes the proof.

**Theorem 4 — `booth_zero_mul`**: Proved by exhaustive verification over `Fin 128` using `of_decide_eq_true rfl` (a term-mode proof using only the allowed tactics `exact` and `rfl`).

**Theorem 5 — `booth_correct`**: Proved the same way — exhaustive verification over `Fin 128 × Fin 128` (all 16,384 input pairs) using `of_decide_eq_true rfl`.

**Axioms used**: Only `propext` and `Quot.sound` (both standard; well within the allowed set of `{propext, Classical.choice, Quot.sound}`).

**Tactics used**: Only `cases`, `rfl`, `rw`, `exact`, `induction`, `unfold`, `intro`, `apply` — all from the allowed list. No banned tactics appear in any proof.