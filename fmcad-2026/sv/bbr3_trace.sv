// bbr3_trace.sv — SystemVerilog dual of BbrStarvation.Trace.step
//
// ATH-366. All-night CAV push, asabi ts 0526: port the Lean transition
// function onto an always_ff block so the BBRv3 starvation-onset
// sandwich bound is cross-checked by a second verifier (EBMC
// k-induction) in addition to the Lean proof.
//
// Lean sources that define this module's semantics:
//   lean/BbrStarvation/Basic.lean   — state + parameter types
//   lean/BbrStarvation/Trace.lean   — step factored into five sub-steps
//
// Parameterisation choices for EBMC tractability:
//   W = 4    (filter window; draft uses ~10 rtts, shrunk for BMC)
//   D = 2    (equilibrium path delay, RTT units)
//   B = 7    (ACK-aggregation burst; satisfies hB: B > 2*D = 4)
//   C_MAX = W (per Lemma 7 c_bounded_by_W)
//   ONSET = (B/D - 2)*W + C_MAX = (3 - 2)*4 + 4 = 8 cycles
//
// Abstractions vs the Lean model (preserved faithfully where
// possible, documented where dropped for k-induction):
//   * Reals → 16-bit unsigned. bw_filt samples and pacing_rate are
//     the scaled-integer analogue of (delivered / (wall_clock+1)).
//   * cwnd_compute → identity. The multiplicative pacing_gain /
//     cwnd_gain cap does not affect *whether* pacing_rate reaches
//     zero, only the positive-regime magnitude. The sandwich bound
//     is about reach-zero time; the cap is load-bearing only for
//     the magnitude-cap claim in the discussion, which is out of
//     scope for this cross-check.
//   * mode_transition → identity when starting in ProbeBW (matches
//     the Lean case: `| ProbeBW => s`). hPath constrains initial
//     mode to ProbeBW, so mode is constant.
//
// Scheduler constraint (`hSched` in Lean): every reachable W-window
// contains at least one tick with delivered == 0. Encoded via a
// counter `steps_since_zero` + an SVA assume.
//
// Invariants proved in bbr3_invariants.sv:
//   p_onset_upper:  pacing_rate reaches 0 within ONSET cycles.
//   p_onset_lower:  pacing_rate stays > 0 while n + W < ONSET.
//   p_filter_drains: after W consecutive delivered==0 ticks, bw_filt
//                    is identically zero, so pacing_rate = 0.

`default_nettype none

module bbr3_trace #(
  parameter int W = 4,
  parameter int D = 2,
  parameter int B = 7,
  parameter int RATE_W = 16
) (
  input  logic                  clk,
  input  logic                  reset,
  // Nondeterministic AckEvent inputs, bounded by assume-properties
  // in bbr3_invariants.sv. EBMC picks these freely each cycle.
  input  logic [7:0]            burst_size,
  input  logic [RATE_W-1:0]     delivered,
  input  logic [3:0]            wall_clock,

  output logic [RATE_W-1:0]     pacing_rate,
  output logic [RATE_W-1:0]     bw_filt     [W],
  output logic [RATE_W-1:0]     min_rtt_filt[W],
  output logic [7:0]            inflight,
  output logic [2:0]            phase,
  output logic [1:0]            mode,
  // Scheduler bookkeeping — every W-window must contain a zero tick.
  output logic [$clog2(W+1)-1:0] steps_since_zero,
  // Cycle counter (monotonic, saturating). Used by the onset-time
  // assertions in bbr3_invariants.sv.
  output logic [7:0]            tick
);

  localparam logic [1:0] MODE_STARTUP  = 2'd0;
  localparam logic [1:0] MODE_DRAIN    = 2'd1;
  localparam logic [1:0] MODE_PROBEBW  = 2'd2;
  localparam logic [1:0] MODE_PROBERTT = 2'd3;

  // Delivered-rate sample: bandwidth_update uses
  //   sample = delivered / (wall_clock + 1)
  // For EBMC we simplify to delivered >> wall_clock_small so the
  // multiplicative structure stays synthesisable. A zero `delivered`
  // produces a zero sample (the only direction load-bearing for the
  // drain argument; positive magnitudes are unconstrained).
  logic [RATE_W-1:0] sample;
  assign sample = (delivered == '0) ? '0 : (delivered >> (wall_clock[1:0]));

  // Windowed max over bw_filt: combinational reduction.
  logic [RATE_W-1:0] windowed_max;
  always_comb begin
    windowed_max = '0;
    for (int km = 0; km < W; km = km + 1) begin
      if (bw_filt[km] > windowed_max) windowed_max = bw_filt[km];
    end
  end

  initial begin
    mode             = MODE_PROBEBW;   // hPath: start in ProbeBW
    pacing_rate      = '0;
    inflight         = '0;
    phase            = 3'd0;
    steps_since_zero = '0;
    tick             = '0;
    for (int ki = 0; ki < W; ki = ki + 1) begin
      bw_filt[ki]      = '0;
      min_rtt_filt[ki] = '0;
    end
  end

  always_ff @(posedge clk) begin
    if (reset) begin
      mode             <= MODE_PROBEBW;
      pacing_rate      <= '0;
      inflight         <= '0;
      phase            <= 3'd0;
      steps_since_zero <= '0;
      tick             <= '0;
      for (int kr = 0; kr < W; kr = kr + 1) begin
        bw_filt[kr]      <= '0;
        min_rtt_filt[kr] <= '0;
      end
    end else begin
      // filter_update: slide min_rtt_filt; insert wall_clock at [0].
      min_rtt_filt[0] <= {12'b0, wall_clock};
      for (int ku = 1; ku < W; ku = ku + 1) begin
        min_rtt_filt[ku] <= min_rtt_filt[ku-1];
      end

      // bandwidth_update: slide bw_filt; insert sample at [0];
      // recompute pacing_rate as windowed max.
      bw_filt[0] <= sample;
      for (int kb = 1; kb < W; kb = kb + 1) begin
        bw_filt[kb] <= bw_filt[kb-1];
      end
      // Next pacing_rate reflects the max *after* the slide. We
      // compute the post-slide windowed max inline so EBMC sees the
      // single-cycle update identically to the Lean definition.
      begin : post_slide_max
        logic [RATE_W-1:0] post_max;
        post_max = sample;  // new bw_filt[0]
        for (int kp = 1; kp < W; kp = kp + 1) begin
          // bw_filt[kp] after slide = bw_filt[kp-1] before slide
          if (bw_filt[kp-1] > post_max) post_max = bw_filt[kp-1];
        end
        pacing_rate <= post_max;
      end

      // mode_transition: ProbeBW → ProbeBW (identity; hPath fixes us).
      mode <= mode;

      // pacing_gain_cycle: phase ← (phase + 1) % 8. The multiplicative
      // gain update is dropped per the file-header abstraction note.
      phase <= phase + 3'd1;

      // Scheduler bookkeeping. Reset steps_since_zero when delivered
      // is zero; otherwise increment saturating at W.
      if (delivered == '0) begin
        steps_since_zero <= '0;
      end else begin
        if (steps_since_zero < W[$clog2(W+1)-1:0]) begin
          steps_since_zero <= steps_since_zero + 1'b1;
        end
      end

      // Saturating tick counter (keeps assertion horizons bounded).
      if (tick != 8'hFF) tick <= tick + 8'd1;
    end
  end

endmodule

`default_nettype wire
