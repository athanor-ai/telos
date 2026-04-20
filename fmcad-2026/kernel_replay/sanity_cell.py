#!/usr/bin/env python3
"""sanity_cell.py — single BBRv3 starvation cell measurement.

Runs ONE (B, D, link_rate, seed) cell end-to-end:
  1. Generate mahimahi uplink trace via ack_schedule.
  2. Launch iperf3 server inside mm-link shell.
  3. Launch iperf3 client inside mm-link shell, BBR-paced.
  4. Poll `ss -tin` at 10 Hz; record first sample where pacing_rate
     drops below EPSILON_BPS = 1000 bytes/sec.
  5. Emit one CSV row:
       B, D, link_rate, seed, T_kernel_ms, T_analytic_ms, residual_ms.

Requires: host kernel with tcp_bbr module loadable (BBRv3).
         mahimahi installed (mm-link, mm-delay in PATH).
         iperf3, ss (iproute2) in PATH.

Usage: sudo python3 sanity_cell.py --B 4 --D 5 --link-rate 100 --seed 0
"""
from __future__ import annotations
import argparse, csv, os, pathlib, re, signal, subprocess, sys, time


EPSILON_BPS = 1000  # "zero pacing" threshold, bytes/sec
DEFAULT_DURATION_S = 30
POLL_HZ = 10
W = 10  # RTT-ticks per bandwidth-probe cycle (paper constant)


def analytic_onset_ms(B: int, D_ms: int, W: int = 10) -> float:
    """T_analytic(B,D) = (floor(B/D) - 2)*W + c ;
    with c = W per the upper-bound form used in paper Theorem 1."""
    if B <= 2 * D_ms:
        return float("inf")
    c = W
    return ((B // D_ms) - 2) * W + c


PACING_RE = re.compile(r"pacing_rate\s+([\d.]+)([KMG]?)bps")


def parse_pacing_rate_bytes_per_s(ss_out: str) -> float | None:
    """Extract pacing_rate from `ss -tin` output, return bytes/sec."""
    m = PACING_RE.search(ss_out)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2)
    multiplier = {"": 1, "K": 1e3, "M": 1e6, "G": 1e9}[unit]
    # ss reports bits/sec; convert to bytes/sec
    return val * multiplier / 8.0


def run_cell(B: int, D_ms: int, link_rate: int, seed: int,
             duration_s: int, port: int, workdir: pathlib.Path) -> dict:
    trace_up = workdir / f"uplink_B{B}_D{D_ms}.trace"
    trace_dn = workdir / "downlink_uniform.trace"
    # 1. Build uplink trace (bursty ACK schedule)
    subprocess.run([
        sys.executable, str(pathlib.Path(__file__).parent / "ack_schedule.py"),
        "--B", str(B), "--D-ms", str(D_ms),
        "--link-rate", str(link_rate),
        "--seed", str(seed),
        "--duration", str(duration_s),
        "--out", str(trace_up),
    ], check=True)
    # Downlink: steady per-ms bytes at link_rate
    bpms = link_rate * 125
    with trace_dn.open("w") as f:
        for _ in range(duration_s * 1000):
            f.write(f"{bpms}\n")

    # 2. Launch iperf3 server in foreground shell (host side, outside
    #    mahimahi). Client runs inside mm-link and connects back to
    #    host over the virtual link. This matches the canonical
    #    mahimahi usage.
    srv = subprocess.Popen(
        ["iperf3", "-s", "-p", str(port), "-1"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(0.5)

    # 3. Inside mm-link, run iperf3 client with BBR congestion control.
    # mm-link's default gateway IP (100.64.0.1) is the host endpoint.
    # The `-Z` (zerocopy) and `-C bbr` flag sets the CC on the client.
    inner = (
        f"iperf3 -c 100.64.0.1 -p {port} -t {duration_s} -C bbr "
        f"-J > /tmp/iperf3_client.json 2>&1 & "
        f"CPID=$!; "
        f"sleep 0.2; "
        f"while kill -0 $CPID 2>/dev/null; do "
        f"  ss -tin dst 100.64.0.1 dport = :{port} 2>&1; "
        f"  echo '---SS-SEP---'; "
        f"  sleep {1.0 / POLL_HZ}; "
        f"done; "
        f"wait $CPID"
    )
    mm_cmd = ["mm-link", str(trace_up), str(trace_dn),
              "--", "bash", "-c", inner]
    t0 = time.time()
    proc = subprocess.Popen(mm_cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)

    # 4. Parse ss output in real time
    onset_kernel_ms = None
    buf = []
    assert proc.stdout is not None
    for line in proc.stdout:
        buf.append(line)
        if "---SS-SEP---" in line:
            chunk = "".join(buf); buf = []
            rate = parse_pacing_rate_bytes_per_s(chunk)
            if rate is not None and rate < EPSILON_BPS and onset_kernel_ms is None:
                onset_kernel_ms = int((time.time() - t0) * 1000)
    proc.wait(timeout=duration_s + 10)
    try:
        srv.wait(timeout=2)
    except subprocess.TimeoutExpired:
        srv.kill()

    T_analytic = analytic_onset_ms(B, D_ms, W)
    residual = (onset_kernel_ms - T_analytic) if onset_kernel_ms is not None else None

    return {
        "B": B, "D": D_ms, "link_rate": link_rate, "seed": seed,
        "T_kernel_ms": onset_kernel_ms if onset_kernel_ms is not None else "",
        "T_analytic_ms": T_analytic if T_analytic != float("inf") else "inf",
        "residual_ms": residual if residual is not None else "",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=4)
    ap.add_argument("--D", type=int, default=5, help="D in ms")
    ap.add_argument("--link-rate", type=int, default=100, help="Mbps")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--duration", type=int, default=DEFAULT_DURATION_S)
    ap.add_argument("--port", type=int, default=25001)
    ap.add_argument("--out", default=str(
        pathlib.Path(__file__).parent / "results" / "sanity_cell.csv"))
    a = ap.parse_args()

    # Precondition: BBR CC available on host.
    cc = pathlib.Path("/proc/sys/net/ipv4/tcp_available_congestion_control").read_text()
    if "bbr" not in cc:
        print(f"FATAL: tcp_bbr not loaded. Available: {cc.strip()}",
              file=sys.stderr)
        print("Run: sudo modprobe tcp_bbr", file=sys.stderr)
        return 2

    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    workdir = pathlib.Path("/tmp/bbr3_sanity_cell")
    workdir.mkdir(exist_ok=True)
    row = run_cell(a.B, a.D, a.link_rate, a.seed, a.duration, a.port, workdir)

    fieldnames = ["B", "D", "link_rate", "seed",
                  "T_kernel_ms", "T_analytic_ms", "residual_ms"]
    write_header = not out.exists()
    with out.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            w.writeheader()
        w.writerow(row)
    print(f"CSV row: {row}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
