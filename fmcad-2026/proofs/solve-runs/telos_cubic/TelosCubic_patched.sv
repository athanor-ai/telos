// Telos-seeded CUBIC CCA trace (2026-04-20 dogfood).
//
// Upstream spec: telos/examples/cubic.yaml — concave cubic growth +
// multiplicative decrease beta=0.70 (scaled ×100 for EBMC integers).
// Principled bug planted: the loss branch applies beta*cwnd/100 but
// forgets the cwnd_floor = 1 safety rail, so cwnd can reach 0 from a
// small starting window. Breaks p_cwnd_ge_mss.
//
// The agent's job is to detect the missing floor and reintroduce it.
module cubic_cca(
  input              clk,
  input              reset,
  input              ack,
  input              loss,
  output reg [9:0]   cwnd
);
  initial cwnd = 10'd1;

  // Simple concave approximation of cubic growth: cwnd += cwnd >> 2
  // (i.e. +25% per ACK below W_max); stays well-defined for BMC bound.
  always @(posedge clk) begin
    if (reset)
      cwnd <= 10'd1;
    else if (loss)
      // Beta=0.7 scaled: cwnd := cwnd * 7 / 10, clamped to at least 1 MSS.
      cwnd <= ((cwnd * 10'd7) / 10'd10 >= 10'd1) ? (cwnd * 10'd7) / 10'd10 : 10'd1;
    else if (ack && cwnd < 10'd512)
      cwnd <= cwnd + (cwnd >> 2) + 10'd1;
  end

  // Safety: once initialised, cwnd never underflows below 1 MSS.
  p_cwnd_ge_mss:
    assert property (@(posedge clk) !reset |=> cwnd >= 10'd1);

  // Growth: ACK below ceiling strictly grows cwnd.
  p_cwnd_grows_on_ack:
    assert property (@(posedge clk)
      !reset && ack && !loss && cwnd < 10'd512 |=> cwnd > $past(cwnd));

  // Decrease: loss reduces cwnd by at least (1 - beta) = 30%.
  p_cwnd_multiplicative_decrease:
    assert property (@(posedge clk)
      !reset && loss |=> cwnd <= ($past(cwnd) * 10'd7) / 10'd10 + 10'd1);
endmodule
