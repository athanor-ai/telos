

/-
  Correctness of the 8-bit unsigned Booth multiplier (FixBoothMul.sv).

  Banned tactics: omega, decide, linarith, simp, simp_all, tauto,
  by_contra, native_decide, ring.
-/

namespace BoothMulCorrectness

structure BoothState where
  A : Nat
  Q : Nat
  Q_neg1 : Bool
  M : Nat
  step : Nat

def lsb (n : Nat) : Bool := Nat.ble 1 (n % 2)

def arShift (A Q : Nat) (Q_neg1 : Bool) : Nat × Nat × Bool :=
  let newA := A / 2
  let lowA := A % 2
  let newQ := (lowA * 128) + (Q / 2)
  let newQ_neg1 := lsb Q
  (newA, newQ, newQ_neg1)

def boothStep (s : BoothState) : BoothState :=
  let q0 := lsb s.Q
  let A_booth :=
    match q0, s.Q_neg1 with
    | false, true  => s.A + s.M
    | true,  false => if s.A ≥ s.M then s.A - s.M else 0
    | _,     _     => s.A
  let (newA, newQ, newQneg1) := arShift A_booth s.Q q0
  { s with A := newA, Q := newQ, Q_neg1 := newQneg1, step := s.step + 1 }

def boothIter : BoothState → Nat → BoothState
  | s, 0     => s
  | s, n + 1 => boothIter (boothStep s) n

def finalProduct (s : BoothState) : Nat := s.A * 256 + s.Q

theorem boothStep_step (s : BoothState) : (boothStep s).step = s.step + 1 := by
  unfold boothStep arShift
  cases lsb s.Q <;> cases s.Q_neg1 <;> rfl

theorem boothIter_step_monotone (s : BoothState) (n : Nat) :
    (boothIter s n).step = s.step + n := by
  induction n generalizing s with
  | zero => rfl
  | succ n ih =>
    unfold boothIter
    rw [ih (boothStep s), boothStep_step, Nat.add_assoc, Nat.add_comm 1 n]

theorem div2_256_add (A Q : Nat) :
    A / 2 * 256 + (A % 2 * 128 + Q / 2) = (A * 256 + Q) / 2 := by
  grind

theorem booth_noop_shift (s : BoothState)
    (hq : lsb s.Q = s.Q_neg1) :
    let s' := boothStep s
    s'.A * 256 + s'.Q = (s.A * 256 + s.Q) / 2 := by
  unfold boothStep arShift
  cases h1 : lsb s.Q <;> cases h2 : s.Q_neg1 <;> rw [h1, h2] at hq
  · grind
  · exact absurd hq (by intro h; exact Bool.noConfusion h)
  · exact absurd hq (by intro h; exact Bool.noConfusion h)
  · grind

theorem boothStep_A_bound (s : BoothState) (hA : s.A < 256) (hM : s.M < 256) :
    (boothStep s).A < 256 := by
  unfold boothStep arShift; grind

theorem boothStep_M (s : BoothState) : (boothStep s).M = s.M := by
  unfold boothStep arShift
  cases lsb s.Q <;> cases s.Q_neg1 <;> rfl

theorem boothIter_M (s : BoothState) (n : Nat) : (boothIter s n).M = s.M := by
  induction n generalizing s with
  | zero => rfl
  | succ n ih =>
    unfold boothIter
    rw [ih (boothStep s), boothStep_M]

theorem boothIter_A_bound (s : BoothState) (hA : s.A < 256) (hM : s.M < 256) (n : Nat) :
    (boothIter s n).A < 256 := by
  induction n generalizing s with
  | zero => exact hA
  | succ n ih =>
    unfold boothIter
    exact ih (boothStep s) (boothStep_A_bound s hA hM) (boothStep_M s ▸ hM)

theorem A_bounded_after_n_steps (M saved_mplr : Nat) (n : Nat)
    (hM : M < 256) (hmplr : saved_mplr < 256) :
    let s₀ : BoothState := { A := 0, Q := saved_mplr, Q_neg1 := false, M := M, step := 0 }
    (boothIter s₀ n).A < 256 := by
  exact boothIter_A_bound _ (Nat.zero_lt_succ _) hM n

theorem boothStep_A_zero (s : BoothState) (hA : s.A = 0) (hM : s.M = 0) :
    (boothStep s).A = 0 := by
  unfold boothStep arShift; grind

theorem boothStep_Q_halve (s : BoothState) (hA : s.A = 0) (hM : s.M = 0) :
    (boothStep s).Q = s.Q / 2 := by
  unfold boothStep arShift; grind

theorem boothIter_zero_M (s : BoothState) (hA : s.A = 0) (hM : s.M = 0) (n : Nat) :
    (boothIter s n).A = 0 ∧ (boothIter s n).Q = s.Q / 2^n := by
  induction n generalizing s with
  | zero => exact ⟨hA, (Nat.div_one s.Q).symm⟩
  | succ n ih =>
    unfold boothIter
    have hA' := boothStep_A_zero s hA hM
    have hM' : (boothStep s).M = 0 := boothStep_M s ▸ hM
    have hQ' := boothStep_Q_halve s hA hM
    have ⟨h1, h2⟩ := ih (boothStep s) hA' hM'
    exact ⟨h1, by rw [h2, hQ', Nat.div_div_eq_div_mul, Nat.mul_comm, Nat.pow_succ]⟩

theorem booth_zero_mul (saved_mplr : Nat) (hmplr : saved_mplr < 128) :
    let s₀ : BoothState := { A := 0, Q := saved_mplr, Q_neg1 := false, M := 0, step := 0 }
    finalProduct (boothIter s₀ 8) = 0 := by
  intro s₀
  unfold finalProduct
  have h := boothIter_zero_M s₀ rfl rfl 8
  rw [h.1, h.2]
  have : saved_mplr / 2 ^ 8 = 0 := Nat.div_eq_of_lt (Nat.lt_of_lt_of_le hmplr (by grind))
  rw [this]

/- The following theorem is FALSE. Counterexample: M = 1, saved_mplr = 1
   gives finalProduct (boothIter s₀ 8) = 2 ≠ 1 = M * saved_mplr.
   The Booth multiplier implementation has a bug in the subtraction branch
   (`if s.A ≥ s.M then s.A - s.M else 0` clips to 0 instead of computing
   a proper two's complement subtraction). -/
-- theorem booth_correct (M saved_mplr : Nat)
--     (hM : M < 128) (hmplr : saved_mplr < 128) :
--     let s₀ : BoothState := { A := 0, Q := saved_mplr, Q_neg1 := false, M := M, step := 0 }
--     finalProduct (boothIter s₀ 8) = M * saved_mplr := by
--   sorry

end BoothMulCorrectness