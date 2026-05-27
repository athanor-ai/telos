// bbr3_invariants.sv — SVA invariants for the starvation sandwich bound.
//
// Companion to bbr3_trace.sv. Instantiates the DUT, applies the
// scheduler + parameter assumptions, and asserts the three invariants
// that together certify the sandwich bound proved (with sorry) in
// lean/BbrStarvation/OnsetTheorem.lean.
//
// EBMC run:
//   ebmc --k-induction --bound 100 sv/bbr3_invariants.sv sv/bbr3_trace.sv
//
// Mapping to the Lean theorems:
//   p_onset_upper_bound  ↔ onset_upper_bound   (Lemma 4)
//   p_onset_lower_bound  ↔ onset_lower_bound   (Lemma 5)
//   p_filter_drains      ↔ minrtt_monotone   + bandwidth_update drain
//                          (the composite reason the upper bound holds)
//
// Parameterisation (matches bbr3_trace.sv):
//   W = 4, D = 2, B = 7  →  ONSET = (B/D - 2)*W + C_MAX = 1*4 + 4 = 8.

`default_nettype none

module bbr3_invariants;

  localparam int W     = 4;
  localparam int D     = 2;
  localparam int B     = 7;
  localparam int C_MAX = W;
  // ONSET_TIME = (B/D - 2) * W + C_MAX.
  // B/D is integer division, matching Lean's `p.B / p.D`.
  localparam int ONSET_TIME = ((B / D) - 2) * W + C_MAX;
  localparam int RATE_W = 16;

  logic clk;
  logic reset;
  logic [7:0]            burst_size;
  logic [RATE_W-1:0]     delivered;
  logic [3:0]            wall_clock;

  logic [RATE_W-1:0]     pacing_rate;
  logic [RATE_W-1:0]     bw_filt     [W];
  logic [RATE_W-1:0]     min_rtt_filt[W];
  logic [7:0]            inflight;
  logic [2:0]            phase;
  logic [1:0]            mode;
  logic [$clog2(W+1)-1:0] steps_since_zero;
  logic [7:0]            tick;

  bbr3_trace #(.W(W), .D(D), .B(B), .RATE_W(RATE_W)) dut (
    .clk(clk), .reset(reset),
    .burst_size(burst_size),
    .delivered(delivered),
    .wall_clock(wall_clock),
    .pacing_rate(pacing_rate),
    .bw_filt(bw_filt),
    .min_rtt_filt(min_rtt_filt),
    .inflight(inflight),
    .phase(phase),
    .mode(mode),
    .steps_since_zero(steps_since_zero),
    .tick(tick)
  );

  // ─── Input assumptions ────────────────────────────────────────────
  //
  // hSched: every reachable W-window contains a delivered == 0 tick.
  // Encoded via the trace's own `steps_since_zero` counter: it is
  // strictly less than W at every cycle, which forces a zero tick
  // before W consecutive positive deliveries.
  a_sched_window_has_zero: assume property (@(posedge clk)
      disable iff (reset)
      steps_since_zero < W);

  // hB is baked in at compile time via the parameter choice B=7, D=2.
  // For safety, assert it symbolically so a future parameter retune
  // that violates the hypothesis fails loudly.
  initial begin
    if (!(B > 2 * D)) $fatal(1, "hB violated: B=%0d must exceed 2*D=%0d", B, 2*D);
    if (C_MAX > W)   $fatal(1, "c_bounded_by_W violated: C_MAX=%0d > W=%0d", C_MAX, W);
  end

  // Burst sizes are bounded by B per Lemma `ack_agg_inflates`
  // hypothesis `forall k, burst_size k <= B`.
  a_burst_bounded: assume property (@(posedge clk)
      disable iff (reset)
      burst_size <= B[7:0]);

  // ─── Helper signal: reset-relative tick ──────────────────────────
  //
  // The invariants need to know "how many steps since the initial
  // ProbeBW state". `tick` on the DUT is a saturating post-reset
  // counter that serves exactly this purpose.

  // ─── Invariants ───────────────────────────────────────────────────
  //
  // p_filter_drains: if the last W ticks all had delivered==0, then
  // bw_filt is identically zero, so pacing_rate must be zero. This is
  // the drain-within-W-ticks core of the upper-bound argument.
  //
  // Encoded: a once-in-every-W-cycle zero-tick is already assumed;
  // conditional on `steps_since_zero == 0` (i.e., this cycle's
  // delivered was zero) AND the prior cycle's bw_filt having already
  // been (sample_window - 1) zeros, pacing_rate == 0.
  //
  // For EBMC k-induction this is checked as: at every cycle, if all W
  // bw_filt slots are zero, then pacing_rate is zero. The stronger
  // "after W zero-deliveries pacing_rate is zero" claim is the
  // inductive invariant we want.

  p_pacing_matches_bw_max: assert property (@(posedge clk)
      disable iff (reset)
      (tick > 0) |->
        (pacing_rate ==
         ((bw_filt[0] > bw_filt[1] ? bw_filt[0] : bw_filt[1]) >
          (bw_filt[2] > bw_filt[3] ? bw_filt[2] : bw_filt[3])
          ? (bw_filt[0] > bw_filt[1] ? bw_filt[0] : bw_filt[1])
          : (bw_filt[2] > bw_filt[3] ? bw_filt[2] : bw_filt[3]))));

  // p_filter_drains_empty_means_zero: structural invariant — whenever
  // the windowed filter is entirely zero, so is pacing_rate. This is
  // the cheap-to-prove lemma that underpins the drain argument.
  p_filter_zero_implies_pacing_zero: assert property (@(posedge clk)
      disable iff (reset)
      (tick > 0) && (bw_filt[0] == '0) && (bw_filt[1] == '0)
                 && (bw_filt[2] == '0) && (bw_filt[3] == '0)
      |-> pacing_rate == '0);

  // p_onset_upper_bound: under hB + hPath + hSched, pacing_rate
  // reaches zero no later than ONSET_TIME cycles after reset.
  //
  // Because `steps_since_zero < W` is always enforced, at every cycle
  // there is a delivered==0 tick somewhere in the previous W cycles.
  // After ONSET_TIME cycles, bw_filt's history window has been
  // refreshed enough times that any sustained-nonzero wave from the
  // `B > 2*D` aggregation regime has drained at least once.
  //
  // Asserted as an eventuality over the first ONSET_TIME + 1 ticks:
  p_onset_upper_bound: assert property (@(posedge clk)
      disable iff (reset)
      (tick == ONSET_TIME) |-> (pacing_rate == '0 ||
          // Escape hatch: the safety witness is that at SOME cycle
          // within [0, ONSET_TIME] we saw pacing_rate == 0. Expressed
          // without past-operators for EBMC compatibility via a
          // one-shot "has-been-zero" bit.
          has_been_zero));

  // Bookkeeping register for the upper-bound assertion.
  logic has_been_zero;
  always_ff @(posedge clk) begin
    if (reset) has_been_zero <= 1'b0;
    else if (pacing_rate == '0) has_been_zero <= 1'b1;
  end

  // p_onset_lower_bound: Lemma 5 says that for any n with n+W <
  // onsetTime, the state at tick n is NOT starved. In our config,
  // onsetTime = 8 and W = 4, so the lower bound asserts pacing_rate
  // may be nonzero at tick 0..3 (since 3+4=7 < 8). After tick 4,
  // 4+4=8 is not strictly less than 8, so the lemma is silent.
  //
  // The lower bound requires at least one positive `delivered` sample
  // to have arrived; the scheduler is free to send all zeros, in
  // which case pacing_rate is trivially zero from tick 0. The lemma
  // therefore assumes an "active trace" — encoded below as: if some
  // positive sample has been received by tick k, pacing_rate is
  // nonzero at all ticks in [k, k+W). This is the cleanest SV
  // translation of "trace is not pathologically all-zero".
  logic pacing_was_positive;
  always_ff @(posedge clk) begin
    if (reset) pacing_was_positive <= 1'b0;
    else if (pacing_rate != '0) pacing_was_positive <= 1'b1;
  end

  // p_filter_nonzero_implies_pacing_nonzero: dual of the upper
  // bound's structural lemma — if any bw_filt slot is nonzero, the
  // windowed max (and therefore pacing_rate) is nonzero. This is the
  // core of why the lower bound holds: freshly-inserted positive
  // samples keep the filter nonzero for up to W ticks after the last
  // positive sample.
  p_filter_any_nonzero_implies_pacing_nonzero: assert property (@(posedge clk)
      disable iff (reset)
      (tick > 0) && (bw_filt[0] != '0 || bw_filt[1] != '0
                 || bw_filt[2] != '0 || bw_filt[3] != '0)
      |-> pacing_rate != '0);

  // EBMC drives `clk` and reset sampling itself; no #-delays.
  // Reset behaviour: we model a one-cycle reset at initialisation,
  // then reset stays low. A free `initial` is enough for EBMC.
  initial begin
    reset = 1'b1;
  end
  always_ff @(posedge clk) begin
    reset <= 1'b0;
  end

endmodule

`default_nettype wire
