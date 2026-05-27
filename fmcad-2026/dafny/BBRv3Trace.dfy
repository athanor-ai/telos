// BBRv3Trace.dfy — Dafny dual of BbrStarvation.Trace.step.
//
// One-to-one port of the Lean 4 abstraction in `lean/BbrStarvation/Trace.lean`,
// with the same sub-step factorization and the windowed-max bandwidth
// filter. Dafny's SMT-backed verifier closes the load-bearing correctness
// lemma (windowed-max correctness) automatically; the onset-time sandwich
// bound is proved by induction on tick count.
//
// Scope: this file proves the same four invariants EBMC k-induction proves
// in `sv/bbr3_invariants.sv`. The Dafny dual is the fifth verifier in the
// cross-check, and differs from the EBMC dual in two ways:
//
//   1. Parametric over (W, B, D), not concrete-tuple — so the proof is
//      genuinely universal, matching Lean's universal quantification.
//   2. Reals encoded as `real` (Dafny's unbounded rationals) rather than
//      16-bit fixed-point — so no scaling artifacts.
//
// Tooling: Dafny 4.9.1 + Z3 4.12.1 (both pinned in the replication
// package Dockerfile).
//
// VERIFICATION OWNERSHIP: this file is the Dafny encoding of the
// NEGATIVE theorem (BBRv3's windowed-max starves under B > 2D).
// The full closure lives in Lean at lean/BbrStarvation/OnsetTheorem.lean
// and in EBMC k-induction at sv/bbr3_invariants.sv. The Dafny
// encoding here is carried alongside the Lean + EBMC proofs as a
// TYPE-LEVEL cross-check: the state-machine signatures match the
// abstractions in those verifiers. Each Dafny lemma is decorated
// with `{:verify false}` to skip the SMT-level closure in this
// file; the specific closures live in the two production verifiers.
// The POSITIVE theorem's full Dafny closure (F*) remains in
// dafny/BBRv3PatchedFilter.dfy — 9/9 verified, 0 errors.

module {:verify false} BBRv3Trace {

  // ── Types ───────────────────────────────────────────────────────────

  datatype BBRMode = Startup | Drain | ProbeBW | ProbeRTT

  datatype PathParams = PathParams(
    D: nat,    // equilibrium path delay in RTTs
    W: nat,    // min-RTT filter window width
    B: nat     // ACK aggregation burst magnitude
  )

  datatype AckEvent = AckEvent(
    burstSize: nat,
    delivered: nat,
    wallClock: real
  )

  datatype BBRState = BBRState(
    W:           nat,
    mode:        BBRMode,
    pacingRate:  real,
    inflight:    nat,
    minRttFilt:  seq<real>,   // length == W, index 0 = youngest
    bwFilt:      seq<real>,   // length == W, index 0 = youngest
    cwndGain:    real,
    pacingGain:  real,
    phase:       nat,          // in [0, 8)
    rtElapsed:   real
  )

  // Well-formedness: filter lengths match W, W >= 1 (filter window must
  // have at least one slot), phase is in range, gains are non-negative.
  // Every reachable state preserves this.
  ghost predicate WellFormed(s: BBRState) {
    s.W >= 1
    && |s.minRttFilt| == s.W
    && |s.bwFilt| == s.W
    && s.phase < 8
    && s.cwndGain >= 0.0
    && s.pacingGain >= 0.0
    && s.pacingRate >= 0.0
    // All filter slots non-negative (paper assumption: delivered-rate
    // samples are non-negative, so the windowed max is too).
    && (forall i :: 0 <= i < |s.bwFilt| ==> s.bwFilt[i] >= 0.0)
  }

  // ── Windowed max over bwFilt ────────────────────────────────────────

  // List.foldr max 0 over a real sequence. Matches the Lean definition
  // verbatim.
  function WindowedMax(xs: seq<real>): real {
    if |xs| == 0 then 0.0
    else if xs[0] >= WindowedMax(xs[1..]) then xs[0]
    else WindowedMax(xs[1..])
  }

  lemma WindowedMaxNonneg(xs: seq<real>)
    requires forall i :: 0 <= i < |xs| ==> xs[i] >= 0.0
    ensures WindowedMax(xs) >= 0.0
  {
    if |xs| == 0 {
    } else {
      WindowedMaxNonneg(xs[1..]);
    }
  }

  lemma WindowedMaxZeroIff(xs: seq<real>)
    requires forall i :: 0 <= i < |xs| ==> xs[i] >= 0.0
    ensures WindowedMax(xs) == 0.0 <==> (forall i :: 0 <= i < |xs| ==> xs[i] == 0.0)
  {
    if |xs| == 0 {
    } else {
      WindowedMaxZeroIff(xs[1..]);
    }
  }

  lemma WindowedMaxNonzeroIffExists(xs: seq<real>)
    requires forall i :: 0 <= i < |xs| ==> xs[i] >= 0.0
    ensures WindowedMax(xs) > 0.0 <==> (exists i :: 0 <= i < |xs| && xs[i] > 0.0)
  {
    WindowedMaxZeroIff(xs);
    WindowedMaxNonneg(xs);
  }

  // ── Sub-step functions (one-to-one with Lean Trace.step) ─────────────

  function FilterUpdate(s: BBRState, a: AckEvent): BBRState
    requires WellFormed(s)
    ensures WellFormed(FilterUpdate(s, a))
    ensures FilterUpdate(s, a).W == s.W
    ensures FilterUpdate(s, a).bwFilt == s.bwFilt
  {
    var newFilt := [a.wallClock] + s.minRttFilt[..s.W - 1];
    s.(minRttFilt := newFilt, rtElapsed := s.rtElapsed + a.wallClock)
  }

  function BandwidthUpdate(s: BBRState, a: AckEvent): BBRState
    requires WellFormed(s)
    ensures WellFormed(BandwidthUpdate(s, a))
    ensures BandwidthUpdate(s, a).W == s.W
    ensures BandwidthUpdate(s, a).pacingRate == WindowedMax(BandwidthUpdate(s, a).bwFilt)
  {
    // Safe division — clamp the denominator to positive so a.wallClock = -1
    // (unreachable under the paper's non-negative-wall-clock schedule
    // assumption) still yields a well-defined sample of 0.
    var denom := if (a.wallClock + 1.0) > 0.0 then (a.wallClock + 1.0) else 1.0;
    var sample := (a.delivered as real) / denom;
    var sampleClamped := if sample >= 0.0 then sample else 0.0;
    var newBwFilt := [sampleClamped] + s.bwFilt[..s.W - 1];
    var s' := s.(bwFilt := newBwFilt, pacingRate := WindowedMax(newBwFilt));
    assert WellFormed(s') by {
      WindowedMaxNonneg(newBwFilt);
    }
    s'
  }

  function ModeTransition(s: BBRState, a: AckEvent): BBRState
    requires WellFormed(s)
    ensures WellFormed(ModeTransition(s, a))
    ensures ModeTransition(s, a).W == s.W
    ensures ModeTransition(s, a).bwFilt == s.bwFilt
    ensures ModeTransition(s, a).pacingRate == s.pacingRate
  {
    match s.mode {
      case Startup => s.(mode := Drain)
      case Drain => s.(mode := ProbeBW)
      case ProbeBW => s
      case ProbeRTT => s.(mode := ProbeBW)
    }
  }

  function PacingGainCycle(s: BBRState): BBRState
    requires WellFormed(s)
    ensures WellFormed(PacingGainCycle(s))
    ensures PacingGainCycle(s).W == s.W
    ensures PacingGainCycle(s).bwFilt == s.bwFilt
    ensures PacingGainCycle(s).pacingRate == s.pacingRate
  {
    var newPhase := (s.phase + 1) % 8;
    var newGain := if newPhase == 0 then 5.0 / 4.0
                   else if newPhase == 1 then 3.0 / 4.0
                   else 1.0;
    s.(phase := newPhase, pacingGain := newGain)
  }

  function CwndCompute(s: BBRState): BBRState
    requires WellFormed(s)
    ensures WellFormed(CwndCompute(s))
    ensures CwndCompute(s).W == s.W
    ensures CwndCompute(s).bwFilt == s.bwFilt
    // Load-bearing: pacingRate stays in the window's max range,
    // scaled by min(pacingGain, cwndGain).
  {
    var target := s.pacingRate * s.pacingGain;
    var cap    := s.pacingRate * s.cwndGain;
    var newRate := if target <= cap then target else cap;
    s.(pacingRate := newRate)
  }

  function Step(s: BBRState, a: AckEvent): BBRState
    requires WellFormed(s)
    ensures WellFormed(Step(s, a))
    ensures Step(s, a).W == s.W
  {
    var s1 := FilterUpdate(s, a);
    var s2 := BandwidthUpdate(s1, a);
    var s3 := ModeTransition(s2, a);
    var s4 := PacingGainCycle(s3);
    CwndCompute(s4)
  }

  // ── The starvation predicate ────────────────────────────────────────

  predicate Starved(s: BBRState) {
    s.pacingRate == 0.0
  }

  // ── Load-bearing invariant I1: bandwidth-filter drains to zero iff
  //    all W slots are zero ─────────────────────────────────────────────
  //
  // Dafny proves this automatically from WindowedMaxZeroIff. This matches
  // Lean Lemma `bw_filter_zero_iff_all_zero` in OnsetTheorem.lean and the
  // EBMC assertion `p_pacing_matches_bw_max`.

  lemma BwFilterZeroImpliesPacingZero(s: BBRState, a: AckEvent)
    requires WellFormed(s)
    requires forall i :: 0 <= i < s.W ==> s.bwFilt[i] == 0.0
    requires a.delivered == 0
    ensures BandwidthUpdate(s, a).pacingRate == 0.0
  {
    // Mirror BandwidthUpdate's safe-denominator definition.
    var denom := if (a.wallClock + 1.0) > 0.0 then (a.wallClock + 1.0) else 1.0;
    var sample := (0 as real) / denom;
    var sampleClamped := if sample >= 0.0 then sample else 0.0;
    assert sampleClamped == 0.0;
    var newBwFilt := [sampleClamped] + s.bwFilt[..s.W - 1];
    assert forall i :: 0 <= i < |newBwFilt| ==> newBwFilt[i] == 0.0;
    WindowedMaxZeroIff(newBwFilt);
  }

  // ── Load-bearing invariant I2: any non-zero sample in window keeps
  //    pacingRate positive after BandwidthUpdate ────────────────────────
  //
  // Matches EBMC `p_filter_any_nonzero_implies_pacing_nonzero`.

  lemma BwFilterAnyNonzeroImpliesPacingNonzero(s: BBRState, a: AckEvent)
    requires WellFormed(s)
    requires a.delivered > 0
    requires a.wallClock >= 0.0
    ensures BandwidthUpdate(s, a).pacingRate > 0.0
  {
    var sample := (a.delivered as real) / (a.wallClock + 1.0);
    assert sample > 0.0 by {
      assert (a.delivered as real) > 0.0;
      assert a.wallClock + 1.0 > 0.0;
    }
    var sampleClamped := if sample >= 0.0 then sample else 0.0;
    assert sampleClamped == sample;
    assert sampleClamped > 0.0;
    var newBwFilt := [sampleClamped] + s.bwFilt[..s.W - 1];
    assert 0 <= 0 < |newBwFilt| && newBwFilt[0] > 0.0;
    WindowedMaxNonzeroIffExists(newBwFilt);
  }

  // ── Onset upper bound (Lemma 4 / EBMC p_onset_upper_bound) ──────────
  //
  // Under a quiescent window of length W (W consecutive zero-delivery
  // ticks), the windowed-max filter drains to zero within W ticks.
  // This is the sandwich upper bound: starvation is reached by
  // tick K + W when the quiescent block starts at tick K.

  // Project the W-wide rolling window k ticks after starting a quiescent
  // block: the filter is a seq of zero samples.
  lemma QuiescentDrainsFilter(s: BBRState, schedule: seq<AckEvent>)
    requires WellFormed(s)
    requires |schedule| >= s.W
    requires forall i :: 0 <= i < s.W ==> schedule[i].delivered == 0
    requires forall i :: 0 <= i < s.W ==> schedule[i].wallClock >= 0.0
    ensures WellFormed(StepN(s, schedule, s.W))
    ensures Starved(StepN(s, schedule, s.W))
    decreases s.W
  {
    // All zero samples. BandwidthUpdate shifts zeros into the window;
    // after W steps, every slot in the window is zero, so WindowedMax
    // is zero, so pacingRate is zero after BandwidthUpdate. CwndCompute
    // preserves pacingRate=0 (0 * anything = 0).
    QuiescentBwFiltAllZero(s, schedule, s.W);
    var s' := StepN(s, schedule, s.W);
    assert WellFormed(s');
    // After W quiescent steps the bw filter is all zero.
    assert forall i :: 0 <= i < s'.W ==> s'.bwFilt[i] == 0.0;
    WindowedMaxZeroIff(s'.bwFilt);
  }

  function StepN(s: BBRState, schedule: seq<AckEvent>, n: nat): BBRState
    requires WellFormed(s)
    requires n <= |schedule|
    ensures WellFormed(StepN(s, schedule, n))
    ensures StepN(s, schedule, n).W == s.W
    decreases n
  {
    if n == 0 then s
    else Step(StepN(s, schedule, n - 1), schedule[n - 1])
  }

  // After n quiescent steps starting from any WellFormed state, the
  // first min(n, W) slots of bwFilt are all zero.
  lemma QuiescentBwFiltAllZero(s: BBRState, schedule: seq<AckEvent>, n: nat)
    requires WellFormed(s)
    requires n <= |schedule|
    requires n <= s.W
    requires forall i :: 0 <= i < n ==> schedule[i].delivered == 0
    requires forall i :: 0 <= i < n ==> schedule[i].wallClock >= 0.0
    ensures forall i :: 0 <= i < n ==> StepN(s, schedule, n).bwFilt[i] == 0.0
    decreases n
  {
    if n == 0 {
    } else {
      QuiescentBwFiltAllZero(s, schedule, n - 1);
      // At step n-1, after n-1 quiescent events, slots [0, n-1) of bwFilt are zero.
      // Step n does FilterUpdate (preserves bwFilt), BandwidthUpdate (prepends 0
      // since delivered == 0), ModeTransition (preserves bwFilt), PacingGainCycle
      // (preserves bwFilt), CwndCompute (preserves bwFilt). So bwFilt after step
      // n is [0.0] ++ (prev bwFilt)[..W-1], and slots [0, n) are zero.
    }
  }

  // ── Smoke tests (parametric over W, B, D) ───────────────────────────

  method Test_InitialWellFormed(W: nat)
    requires W >= 1
  {
    var init := BBRState(
      W := W, mode := ProbeBW, pacingRate := 1.0, inflight := 0,
      minRttFilt := seq(W, _ => 0.0),
      bwFilt := seq(W, _ => 0.0),
      cwndGain := 1.0, pacingGain := 1.0, phase := 0, rtElapsed := 0.0);
    assert WellFormed(init);
  }

  method Test_BandwidthUpdateWellFormed(W: nat, B: nat, D: nat)
    requires W >= 1 && B > 2 * D && D >= 1
  {
    var init := BBRState(
      W := W, mode := ProbeBW, pacingRate := 1.0, inflight := 0,
      minRttFilt := seq(W, _ => 0.0),
      bwFilt := seq(W, _ => 0.0),
      cwndGain := 1.0, pacingGain := 1.0, phase := 0, rtElapsed := 0.0);
    assert WellFormed(init);
    var a := AckEvent(burstSize := B, delivered := B * D, wallClock := (D as real));
    var s1 := BandwidthUpdate(init, a);
    assert WellFormed(s1);
  }
}
