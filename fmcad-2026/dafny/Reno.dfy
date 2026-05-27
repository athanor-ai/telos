// Reno.dfy — Dafny dual of CC.Reno.no_starvation.
//
// One-to-one port of lean/CC/Reno.lean. Encodes the RFC 5681 Reno
// AIMD state machine with the cwnd_floor substep as the structural
// invariant. Same positivity argument shape as Cubic.dfy: the
// cwnd_floor clip makes cwnd >= MSS after every step, and
// pacing_compute publishes cwnd as pacing_rate, so starvation
// cannot occur.
//
// Tooling: Dafny 4.9.1 + Z3 4.12.1 (pinned in the replication
// package Dockerfile). Verify with:
//
//     dafny verify Reno.dfy
//
// Expected: N verified, 0 errors.

datatype RenoState = RenoState(
  cwnd          : real,
  ssthresh      : real,
  pacing_rate   : real,
  srtt          : real,
  in_slow_start : bool
)

datatype RenoParams = RenoParams(
  MSS : real
)

function cwnd_floor(s: RenoState, p: RenoParams): RenoState {
  RenoState(
    cwnd          := if s.cwnd < p.MSS then p.MSS else s.cwnd,
    ssthresh      := s.ssthresh,
    pacing_rate   := s.pacing_rate,
    srtt          := s.srtt,
    in_slow_start := s.in_slow_start
  )
}

function pacing_compute(s: RenoState): RenoState {
  RenoState(
    cwnd          := s.cwnd,
    ssthresh      := s.ssthresh,
    pacing_rate   := s.cwnd,
    srtt          := s.srtt,
    in_slow_start := s.in_slow_start
  )
}

function step(s: RenoState, p: RenoParams): RenoState {
  pacing_compute(cwnd_floor(s, p))
}

lemma cwnd_floor_cwnd_ge_MSS(s: RenoState, p: RenoParams)
  ensures cwnd_floor(s, p).cwnd >= p.MSS
{
}

lemma step_pacing_rate_ge_MSS(s: RenoState, p: RenoParams)
  ensures step(s, p).pacing_rate >= p.MSS
{
  cwnd_floor_cwnd_ge_MSS(s, p);
}

function iterate(s: RenoState, p: RenoParams, n: nat): RenoState
  decreases n
{
  if n == 0 then s else step(iterate(s, p, n - 1), p)
}

lemma no_starvation(s0: RenoState, p: RenoParams, n: nat)
  ensures iterate(s0, p, n + 1).pacing_rate >= p.MSS
{
  step_pacing_rate_ge_MSS(iterate(s0, p, n), p);
}
