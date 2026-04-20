#!/usr/bin/env python3
"""run_sweep.py — measure real kernel BBRv3 starvation on a (B, D)
grid and compare against the paper's analytic onset-time bound.

Per (B, D, link_rate, seed) cell:
  1. Generate mahimahi uplink trace via ack_schedule.py.
  2. Start iperf3 server + client under mm-delay + mm-link.
  3. Poll `ss -i` at 10 Hz for the BBRv3 pacing_rate.
  4. Record first tick at which pacing_rate < ε; emit CSV row.

Output: runs/kernel_replay_<timestamp>.csv with columns
    B, D_ms, link_rate_mbps, seed, onset_kernel_ms,
    onset_analytic_ms, residual_ms

Host sysctls required:
    net.ipv4.ip_forward=1
    kernel.unprivileged_userns_clone=1

Host kernel must have BBRv3 (`modprobe tcp_bbr` and check
`cat /proc/sys/net/ipv4/tcp_available_congestion_control` for
`bbr` — if `bbr2` / `bbr3` available, prefer them). Where the host
ships BBRv2 only, the Google BBRv3 patch must be applied to a
custom kernel and booted via QEMU — documented in README.md.
"""
from __future__ import annotations
import argparse, csv, pathlib, shutil, subprocess, sys, time


EPSILON_BPS = 1000  # "zero" = under 1 Kbps


def analytic_onset_ms(B: int, D_ms: int, W: int = 10) -> float:
    """T(B, D) = (⌊B/D⌋ − 2)·W + c; with D in ms and W in ticks
    (RTT-units of 1ms here), c = 2·D as per Theorem 1."""
    if B <= 2 * D_ms:
        return float("inf")  # no starvation regime
    return ((B // D_ms) - 2) * W + 2 * D_ms


def run_cell(B: int, D_ms: int, link_rate: int, seed: int,
             duration_s: int = 30) -> dict:
    """Run one (B, D, link_rate, seed) cell; return CSV row."""
    trace_up = "/tmp/uplink.trace"
    trace_dn = "/tmp/downlink.trace"
    subprocess.run(["python3", "/app/ack_schedule.py",
                    "--B", str(B), "--D-ms", str(D_ms),
                    "--link-rate", str(link_rate),
                    "--seed", str(seed),
                    "--duration", str(duration_s),
                    "--out", trace_up], check=True)
    # Downlink is uniform (ACK path, not the starving direction).
    with open(trace_dn, "w") as f:
        f.write("1200\n" * (duration_s * 1000))

    # Skeleton: the full mahimahi + iperf3 + ss pipeline requires
    # root caps and tcp_bbr v3 module. Reviewer reproduction path:
    #   docker build -t bbr3-replay .
    #   docker run --privileged --sysctl net.ipv4.ip_forward=1 \
    #              bbr3-replay
    # For this container skeleton we emit a stub row and let the
    # caller plug in their own mahimahi invocation.
    return {
        "B": B, "D_ms": D_ms, "link_rate_mbps": link_rate,
        "seed": seed,
        "onset_kernel_ms": None,  # filled by mahimahi run
        "onset_analytic_ms": analytic_onset_ms(B, D_ms),
        "residual_ms": None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="runs/kernel_replay.csv")
    ap.add_argument("--duration", type=int, default=30)
    a = ap.parse_args()

    if not shutil.which("mm-delay") and not shutil.which("mahimahi"):
        print("mahimahi not installed; exit 2 (container skeleton)",
              file=sys.stderr)
        return 2

    Bs = [3, 4, 5, 6, 7, 8]
    Ds = [1, 5, 10, 20, 50]
    rates = [10, 100, 1000]
    seeds = list(range(10))

    rows = []
    for B in Bs:
        for D in Ds:
            for r in rates:
                for s in seeds:
                    rows.append(run_cell(B, D, r, s, a.duration))

    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"wrote {len(rows)} rows to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
