// BBRv3PatchedFilter.dfy — Dafny/Z3 dual of the Lean `PatchedFilter`
// module. Proves the positive theorem `no_starvation_under_F_star`
// via the SMT backend.
//
// Companion to BBRv3Trace.dfy (which proves the negative result).
// Together they certify both verdicts in the same SMT-backed
// verifier: BBRv3's windowed-max starves under quiescent windows;
// F*'s burst-normalized EWMA never starves.
//
// Tooling: Dafny 4.9.1 + Z3 (both pinned in the replication
// package Dockerfile).
//
// Verify from the paper repo root:
//   bash replication/run.sh --only dafny
//
// Or on a native host with dafny on PATH:
//   cd dafny && dafny verify BBRv3PatchedFilter.dfy

module BBRv3PatchedFilter {

  // ── Minimal state + event types ─────────────────────────────────────
  // Intentionally a trimmed view of the full BBRState — only the fields
  // the patched-filter positive theorem load-bears on: pacing_rate +
  // filter width W. Same abstraction as the Lean PatchedFilter module.

  datatype AckEvent = AckEvent(
    burstSize: nat,
    delivered: nat,
    wallClock: real
  )

  datatype PatchedState = PatchedState(
    W: nat,
    pacingRate: real
  )

  ghost predicate WellFormed(s: PatchedState) {
    s.W >= 1 && s.pacingRate >= 0.0
  }

  // ── Burst-normalized sample ─────────────────────────────────────────

  function Sample(a: AckEvent): real
    ensures Sample(a) >= 0.0
  {
    var burst := if a.burstSize >= 1 then a.burstSize else 1;
    var num := (a.delivered as real);
    var den := (a.wallClock + 1.0) * (burst as real);
    if den > 0.0 then
      // delivered >= 0 and den > 0 so the quotient is >= 0.
      num / den
    else
      0.0
  }

  // ── EWMA one-step update ────────────────────────────────────────────

  function Alpha(W: nat): real
    requires W >= 1
    ensures 0.0 < Alpha(W) <= 1.0
  {
    1.0 / (W as real)
  }

  function BandwidthUpdatePatched(s: PatchedState, a: AckEvent): PatchedState
    requires WellFormed(s)
    requires s.W >= 2
    ensures WellFormed(BandwidthUpdatePatched(s, a))
    ensures BandwidthUpdatePatched(s, a).W == s.W
    // Core invariant: EWMA preserves strict positivity of pacing_rate.
    ensures s.pacingRate > 0.0 ==> BandwidthUpdatePatched(s, a).pacingRate > 0.0
  {
    var alpha := Alpha(s.W);
    var sample := Sample(a);
    var newRate := alpha * sample + (1.0 - alpha) * s.pacingRate;
    // alpha*sample >= 0, (1-alpha) > 0 (because W >= 2 => alpha = 1/W <= 1/2 < 1),
    // so (1-alpha)*prior > 0 when prior > 0; newRate is >= both terms.
    assert 0.0 < alpha <= 0.5;
    assert 0.0 < 1.0 - alpha;
    assert alpha * sample >= 0.0;
    assert (1.0 - alpha) * s.pacingRate >= 0.0;
    assert newRate >= 0.0;
    s.(pacingRate := newRate)
  }

  // ── Transition step ────────────────────────────────────────────────

  function Step(s: PatchedState, a: AckEvent): PatchedState
    requires WellFormed(s)
    requires s.W >= 2
    ensures WellFormed(Step(s, a))
    ensures Step(s, a).W == s.W
    ensures s.pacingRate > 0.0 ==> Step(s, a).pacingRate > 0.0
  {
    BandwidthUpdatePatched(s, a)
  }

  // ── Trace unrolling ────────────────────────────────────────────────

  function StepN(s: PatchedState, schedule: seq<AckEvent>, n: nat): PatchedState
    requires WellFormed(s)
    requires s.W >= 2
    requires n <= |schedule|
    ensures WellFormed(StepN(s, schedule, n))
    ensures StepN(s, schedule, n).W == s.W
    ensures s.pacingRate > 0.0 ==> StepN(s, schedule, n).pacingRate > 0.0
    decreases n
  {
    if n == 0 then s
    else Step(StepN(s, schedule, n - 1), schedule[n - 1])
  }

  // ── Main theorem: no starvation under F* ───────────────────────────
  //
  // For any well-formed PatchedState with W >= 2 and strictly positive
  // initial pacing_rate, and for any finite schedule, the state reached
  // after n ticks has pacing_rate > 0 for every n <= |schedule|.
  //
  // Mirrors the Lean theorem `no_starvation_under_F_star` byte-for-byte
  // in statement (allowing for Dafny <-> Lean syntactic reshaping).

  lemma NoStarvationUnderFStar(
    init: PatchedState,
    schedule: seq<AckEvent>,
    n: nat
  )
    requires WellFormed(init)
    requires init.W >= 2
    requires init.pacingRate > 0.0
    requires n <= |schedule|
    ensures StepN(init, schedule, n).pacingRate > 0.0
  {
    // The ensures follows directly from the ensures clause of StepN,
    // which Dafny's SMT backend carries forward.
  }

  // ── Smoke tests ────────────────────────────────────────────────────
  //
  // These parametric methods exercise the theorem on concrete (W, B, D)
  // tuples. They do not add proof power but verify the SMT backend can
  // dispatch the ensures clauses without additional hints.

  method TestSmallConcreteTuple() {
    var init := PatchedState(W := 10, pacingRate := 1.0);
    var a := AckEvent(burstSize := 5, delivered := 10, wallClock := 2.0);
    var s1 := Step(init, a);
    assert s1.pacingRate > 0.0;
  }

  method TestAfterFiveTicks() {
    var init := PatchedState(W := 10, pacingRate := 1.0);
    var sched := [
      AckEvent(5, 10, 2.0),
      AckEvent(5, 0,  2.0),
      AckEvent(5, 10, 2.0),
      AckEvent(5, 0,  2.0),
      AckEvent(5, 10, 2.0)
    ];
    var s5 := StepN(init, sched, 5);
    assert s5.pacingRate > 0.0;
  }
}
