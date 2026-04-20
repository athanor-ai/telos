// bbr3_patched_invariants.sv — SVA for the patched filter F*.
//
// Asserts: under the same concrete (W, B, D) tuple as the negative
// theorem, and INIT_RATE = 16 (> 0), the patched trace's pacing_rate
// stays strictly positive for every cycle.
//
// Mapping to the Lean theorem:
//   p_patched_pacing_rate_positive  ↔  no_starvation_under_F_star

`default_nettype none

module bbr3_patched_invariants;

  localparam int W         = 4;
  localparam int D         = 2;
  localparam int B         = 7;
  localparam int RATE_W    = 16;
  localparam int LOG2_W    = 2;
  localparam int INIT_RATE = 16;

  logic              clk = 0;
  logic              reset;
  logic [7:0]        burst_size;
  logic [RATE_W-1:0] delivered;
  logic [3:0]        wall_clock;

  logic [RATE_W-1:0] pacing_rate;
  logic [RATE_W-1:0] bw_filt     [W];
  logic [2:0]        phase;
  logic [7:0]        tick;

  bbr3_patched_trace #(
    .W(W), .D(D), .B(B),
    .RATE_W(RATE_W), .LOG2_W(LOG2_W), .INIT_RATE(INIT_RATE)
  ) dut (
    .clk(clk), .reset(reset),
    .burst_size(burst_size),
    .delivered(delivered),
    .wall_clock(wall_clock),
    .pacing_rate(pacing_rate),
    .bw_filt(bw_filt),
    .phase(phase),
    .tick(tick)
  );

  // Scheduler assumes: burst bounded by B, delivered bounded by B*D,
  // wall_clock in [0, 7] so wall_clock[1:0] + LOG2_W fits.
  a_burst_bounded: assume property (@(posedge clk)
    burst_size <= 8'(B) && burst_size >= 8'd1);
  a_delivered_bounded: assume property (@(posedge clk)
    delivered <= RATE_W'(B * D));
  a_wall_bounded: assume property (@(posedge clk)
    wall_clock <= 4'd3);

  // Reset sequence.
  a_reset_once: assume property (@(posedge clk)
    (tick == '0) |-> reset);
  a_no_reset_after: assume property (@(posedge clk)
    (tick > '0) |-> !reset);

  // ── Headline invariant — F* never starves ────────────────────────
  // If INIT_RATE > 0, pacing_rate stays > 0 for every cycle.
  p_patched_pacing_rate_positive: assert property (
    @(posedge clk) disable iff (reset)
    pacing_rate > '0
  );

  // Supporting invariant: the EWMA preserves a lower bound on
  // pacing_rate. After W >= 2 shifts, the prior-term carries at
  // least (W-1)/W of the prior mass. So any positive initial rate
  // gives a geometric lower bound bounded away from zero at any
  // finite horizon.
  p_patched_pacing_rate_lower_bound: assert property (
    @(posedge clk) disable iff (reset)
    pacing_rate >= '1   // at least 1 in the 16-bit scaled-integer view
  );

  // Observability: the EWMA shift by LOG2_W in the trace module
  // must be consistent with W = 2^LOG2_W. This is a type-level check.
  initial begin
    assert ((1 << LOG2_W) == W);
  end

endmodule
