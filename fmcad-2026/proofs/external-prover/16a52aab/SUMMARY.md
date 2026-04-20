# Summary of changes for run 16a52aab-7355-44fb-aa54-142b17abb357
I proved 4 out of 5 theorems in `LeanGateScratch.lean` without using any banned tactics (omega, decide, linarith, simp, simp_all, tauto, by_contra, native_decide, ring). The proofs use only allowed tactics like `grind`, `cases`, `rfl`, `rw`, `exact`, `induction`, `unfold`, `intro`, and `apply`.

**Proved theorems:**
1. `boothIter_step_monotone` — by induction on `n`, using `boothStep_step` helper and `Nat.add_assoc`/`Nat.add_comm`.
2. `booth_noop_shift` — by case-splitting on `lsb s.Q` and `s.Q_neg1`, eliminating contradictory cases via `hq`, and using `grind` for the arithmetic identity.
3. `A_bounded_after_n_steps` — via a generalized induction lemma (`boothIter_A_bound`) using `boothStep_A_bound` (single-step bound) and `boothStep_M` (M preservation).
4. `booth_zero_mul` — via `boothIter_zero_M` showing that when M=0, A stays 0 and Q halves each step, so after 8 steps Q = saved_mplr/256 = 0.

**Commented out (FALSE):**
- `booth_correct` — This theorem is provably false. Counterexample: M=1, saved_mplr=1 yields `finalProduct = 2 ≠ 1 = M * saved_mplr`. Computational testing confirms 361 out of 400 cases fail for M, saved_mplr ∈ [0,20). The bug is in the subtraction branch of `boothStep`: `if s.A ≥ s.M then s.A - s.M else 0` clips to 0 instead of computing a proper two's complement subtraction, breaking the Booth multiplication algorithm.

**Helper lemmas added:**
- `boothStep_step`, `div2_256_add`, `boothStep_A_bound`, `boothStep_M`, `boothIter_M`, `boothIter_A_bound`, `boothStep_A_zero`, `boothStep_Q_halve`, `boothIter_zero_M`

All proofs depend only on standard axioms (propext, Classical.choice, Quot.sound).