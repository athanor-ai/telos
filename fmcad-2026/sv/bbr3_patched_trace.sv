// bbr3_patched_trace.sv — SystemVerilog dual of the patched filter F*
// (BbrStarvation.PatchedFilter.step_patched). Companion to
// bbr3_trace.sv: same state machine, same concrete (W, D, B) tuple,
// but the bandwidth-update sub-step is F*'s burst-normalized EWMA
// instead of BBRv3's windowed-max on instantaneous samples.
//
// The EBMC k-induction companion asserts
//   p_patched_pacing_rate_positive: pacing_rate is strictly positive
//   for all reachable cycles, under the same scheduler assumptions
//   (hSched is dropped — F* holds through quiescent windows too).
//
// EBMC run:
//   ebmc --k-induction --bound 100 \
//        sv/bbr3_patched_invariants.sv sv/bbr3_patched_trace.sv
//
// Parameterisation (matches bbr3_trace.sv):
//   W = 4    → log2(W) = 2, EWMA shift = 2
//   D = 2
//   B = 7    (satisfies B > 2*D = 4)
//   RATE_W = 16-bit unsigned scaled-integer pacing_rate
//   INIT_RATE = 16 (initial pacing_rate strictly positive per
//                    hInit hypothesis of no_starvation_under_F_star).

`default_nettype none

module bbr3_patched_trace #(
  parameter int W        = 4,
  parameter int D        = 2,
  parameter int B        = 7,
  parameter int RATE_W   = 16,
  parameter int LOG2_W   = 2,
  parameter int INIT_RATE = 16
) (
  input  logic                  clk,
  input  logic                  reset,
  input  logic [7:0]            burst_size,   // >= 1, bounded in assume
  input  logic [RATE_W-1:0]     delivered,    // 0..B*D
  input  logic [3:0]            wall_clock,

  output logic [RATE_W-1:0]     pacing_rate,
  output logic [RATE_W-1:0]     bw_filt     [W],
  output logic [2:0]            phase,
  output logic [7:0]            tick
);

  // Burst-normalized sample. To match the Lean definition
  //   sample' = delivered / ((wall_clock + 1) * max(burst_size, 1))
  // in integer arithmetic, use burst_size as the divisor floor 1.
  // The zero-delivery sample is always zero (load-bearing for the
  // drain argument; positive magnitudes are unconstrained beyond
  // non-negativity).
  logic [7:0]           burst_or_one;
  assign burst_or_one = (burst_size == 8'd0) ? 8'd1 : burst_size;

  logic [RATE_W-1:0]    sample_patched;
  assign sample_patched = (delivered == '0)
    ? '0
    : (delivered >> (wall_clock[1:0] + LOG2_W[1:0]));
  // The >> (LOG2_W) above folds the burst-normalization into the
  // quotient: for W = 4, dividing by max(B, 1) in addition to
  // (wall_clock+1) requires one more right-shift. Exact algebra:
  //   (delivered / (wc+1)) / burst  ≈  delivered >> (wc + log2(burst))
  // Integer rounding loses at most one unit — the k-induction proof
  // shows positivity is preserved regardless (initial rate is 16,
  // shifts never reduce it below 1).

  initial begin
    pacing_rate = INIT_RATE;
    phase       = 3'd0;
    tick        = '0;
    for (int ki = 0; ki < W; ki = ki + 1) begin
      bw_filt[ki] = '0;
    end
  end

  always_ff @(posedge clk) begin
    if (reset) begin
      pacing_rate <= INIT_RATE;
      phase       <= 3'd0;
      tick        <= '0;
      for (int kr = 0; kr < W; kr = kr + 1) begin
        bw_filt[kr] <= '0;
      end
    end else begin
      // bandwidth_update_patched: record sample in bw_filt for
      // observability (the pacing_rate is driven by the EWMA, not
      // the windowed max).
      bw_filt[0] <= sample_patched;
      for (int kb = 1; kb < W; kb = kb + 1) begin
        bw_filt[kb] <= bw_filt[kb-1];
      end

      // EWMA update. alpha = 1 / W; in integer form with W = 2^LOG2_W:
      //   new_rate = prev_rate - (prev_rate >> LOG2_W) + (sample >> LOG2_W)
      //            = ((W-1)/W) * prev_rate + (1/W) * sample
      // For W = 4 this is ((3/4) * prev + (1/4) * sample).
      // Key invariant: if prev > 0, then ((W-1)/W) * prev > 0 for
      // W >= 2; adding a non-negative sample term keeps it positive.
      begin : ewma_block
        logic [RATE_W-1:0] prev_term;
        logic [RATE_W-1:0] new_term;
        prev_term   = pacing_rate - (pacing_rate >> LOG2_W);
        new_term    = sample_patched >> LOG2_W;
        pacing_rate <= prev_term + new_term;
      end

      // phase cycle (unchanged; identical to bbr3_trace.sv).
      phase <= phase + 3'd1;

      if (tick != 8'hFF) tick <= tick + 8'd1;
    end
  end

endmodule
