// Telos-seeded Reno CCA trace (2026-04-20 dogfood).
//
// Upstream spec: telos/examples/reno.yaml — AIMD + cwnd_floor.
// Principled bug planted for solve/sysverilog: the loss branch halves
// cwnd without enforcing the cwnd_floor = 1, so the post-loss cwnd can
// drop to 0 when starting from cwnd==1. That breaks p_cwnd_ge_mss.
//
// The agent's job is to detect the missing floor and reintroduce it.
module reno_cca(
  input              clk,
  input              reset,
  input              ack,     // delivered ACK arrived this tick
  input              loss,    // loss signal this tick (ECN or timeout)
  output reg [7:0]   cwnd     // congestion window in MSS units
);
  initial cwnd = 8'd1;

  always @(posedge clk) begin
    if (reset)
      cwnd <= 8'd1;
    else if (loss)
      cwnd <= (cwnd <= 8'd1) ? 8'd1 : (cwnd >> 1);  // floor at 1 MSS
    else if (ack && cwnd != 8'hFF)
      cwnd <= cwnd + 8'd1;     // AIMD: +1 MSS per ACK (slow-start-free form).
  end

  // Safety: cwnd must stay above MSS once initialised.
  p_cwnd_ge_mss:
    assert property (@(posedge clk) !reset |=> cwnd >= 8'd1);

  // Liveness: a steady stream of ACKs without loss strictly grows cwnd
  // until the saturation point.
  p_cwnd_grows_on_ack:
    assert property (@(posedge clk)
      !reset && ack && !loss && cwnd < 8'hFF |=> cwnd == $past(cwnd) + 8'd1);

  // On loss the window must at least halve (multiplicative-decrease).
  p_cwnd_halves_on_loss:
    assert property (@(posedge clk)
      !reset && loss |=> cwnd <= ($past(cwnd) >> 1) + 8'd1);
endmodule
