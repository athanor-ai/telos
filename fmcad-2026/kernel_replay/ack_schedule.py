#!/usr/bin/env python3
"""ack_schedule.py — clocked-ACK aggregation schedule generator.

Given (B, D, link_rate_mbps, seed, duration_s), emit a mahimahi
link-shell trace where ACKs arrive in clustered bursts of B packets
every D milliseconds with zero delivered packets in between. This is
the adversarial schedule under which the paper's onset theorem
asserts pacing_rate -> 0 within (floor(B/D) - 2)*W + c ticks.

Mahimahi uplink/downlink trace format (from mm-link man page and
traces/ATT-LTE-driving.up): one line per 1500-byte packet delivery,
each line = integer millisecond timestamp at which that packet is
delivered. Monotonically non-decreasing. K entries at the same ms =
a burst of K*MTU bytes delivered in that 1ms window.

We emit B MTU-deliveries at t = 0, D, 2D, ..., each packed into the
same millisecond (adversarial burst), with zero delivered packets in
between. This precisely realises the (B, D) schedule from Sec. 3.
"""
from __future__ import annotations
import argparse, random, sys


MTU_BYTES = 1500  # mahimahi fixes packet size at 1500B per delivery tick


def generate_trace(
    B: int, D_ms: int, link_rate_mbps: int,
    seed: int, duration_s: int, out: str,
) -> None:
    _ = random.Random(seed)  # seed reserved for future jitter; adversary is deterministic
    total_ms = duration_s * 1000
    # Adversarial schedule: at t = 0, D, 2D, ... emit B packets in that
    # same millisecond; otherwise no deliveries. This is the "clocked-
    # ACK aggregation" schedule from the paper (Section 3).
    #
    # Note: link_rate_mbps is kept for CSV bookkeeping and for callers
    # that want to sanity-check B*MTU*1000/D <= link_rate*125000; we do
    # NOT modulate the trace by link_rate because mahimahi's trace is
    # itself the link capacity envelope.
    with open(out, "w") as f:
        t = 0
        while t < total_ms:
            for _k in range(B):
                f.write(f"{t}\n")
            t += D_ms
    # Peak burst check (informational).
    peak_bps = B * MTU_BYTES * 8 * (1000 // D_ms)
    link_bps = link_rate_mbps * 1_000_000
    msg = (f"wrote {out} (B={B}, D={D_ms}ms, {total_ms} ms, peak={peak_bps/1e6:.1f} Mbps, "
           f"link={link_bps/1e6:.0f} Mbps)")
    print(msg, file=sys.stderr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, required=True)
    ap.add_argument("--D-ms", type=int, required=True)
    ap.add_argument("--link-rate", type=int, default=100,
                    help="link rate in Mbps (informational)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--duration", type=int, default=60,
                    help="seconds")
    ap.add_argument("--out", default="uplink.trace")
    a = ap.parse_args()
    generate_trace(a.B, a.D_ms, a.link_rate, a.seed, a.duration, a.out)
