#!/bin/busybox sh
export PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/hostroot/bin:/hostroot/sbin:/hostroot/usr/bin:/hostroot/usr/sbin:/hostroot/usr/local/bin
/bin/busybox --install -s /bin 2>/dev/null

mount -t proc none /proc
mount -t sysfs none /sys
mount -t devtmpfs none /dev 2>/dev/null
mount -t tmpfs none /tmp
mount -t tmpfs none /run

mkdir -p /hostroot
mount -t 9p -o trans=virtio,version=9p2000.L,msize=104857600,ro hostroot /hostroot || {
  echo "9p hostroot mount failed"; exec /bin/sh
}

mkdir -p /results
mount -t 9p -o trans=virtio,version=9p2000.L,msize=104857600,rw results /results || {
  echo "9p results mount failed"
}

# Strategy: DO NOT bind-mount /bin, /usr. Instead, add hostroot paths
# to LD_LIBRARY_PATH and PATH. Link dynamic loader explicitly.

mkdir -p /lib64
# Symlink the dynamic loader so host binaries can find it
ln -sf /hostroot/lib64/ld-linux-x86-64.so.2 /lib64/ld-linux-x86-64.so.2 2>/dev/null

export LD_LIBRARY_PATH=/hostroot/lib/x86_64-linux-gnu:/hostroot/lib64:/hostroot/usr/lib/x86_64-linux-gnu:/hostroot/usr/local/lib

# Sysctls
echo 1 > /proc/sys/net/ipv4/ip_forward
ip link set lo up
echo bbr > /proc/sys/net/ipv4/tcp_congestion_control
echo fq > /proc/sys/net/core/default_qdisc

echo "=== BBRv3 QEMU ready ==="
echo "Kernel: $(uname -r)"
echo "Available CC: $(cat /proc/sys/net/ipv4/tcp_available_congestion_control)"
echo "Default CC: $(cat /proc/sys/net/ipv4/tcp_congestion_control)"
echo "Default qdisc: $(cat /proc/sys/net/core/default_qdisc)"

# Helper to invoke host binaries via explicit loader
HIPERF3=/hostroot/usr/bin/iperf3
HSS=/hostroot/usr/bin/ss
HTC=/hostroot/usr/sbin/tc
LD=/hostroot/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2

# Test each binary runs
echo "--- testing binaries ---"
$LD --library-path $LD_LIBRARY_PATH $HIPERF3 --version 2>&1 | head -1
$LD --library-path $LD_LIBRARY_PATH $HSS -V 2>&1 | head -1
$LD --library-path $LD_LIBRARY_PATH $HTC -V 2>&1 | head -1

# Define shortcuts
run_iperf3() { $LD --library-path $LD_LIBRARY_PATH $HIPERF3 "$@"; }
run_ss() { $LD --library-path $LD_LIBRARY_PATH $HSS "$@"; }
run_tc() { $LD --library-path $LD_LIBRARY_PATH $HTC "$@"; }

# ========== Apply ACK-aggregation qdisc on lo ==========
B=4
D=5
LINK_RATE=100
SEED=0
DURATION=30
PORT=25001
MTU=1500
RATE_BPS=$((B * MTU * 8 * 1000 / D))
BURST_BYTES=$((B * MTU))
echo "--- tc qdisc: netem + tbf for ACK aggregation (B=$B, D=$D ms) ---"
# Approach: use fq qdisc (already default) and add netem to enforce
# exactly D-ms delivery granularity. netem's "rate" option + "delay"
# with jitter creates a bursty delivery pattern similar to what the
# paper's adversary imposes. We use a simpler tbf that's loose enough
# to let TCP start but bounds the long-term rate to the B*MTU/D budget.
run_tc qdisc del dev lo root 2>/dev/null
# Use HTB with rate = B*MTU*1000/D and a large burst to let handshake complete
HTB_RATE_KBIT=$(( RATE_BPS / 1000 ))
run_tc qdisc add dev lo root handle 1: htb default 10 2>&1
run_tc class add dev lo parent 1: classid 1:10 htb rate ${HTB_RATE_KBIT}kbit ceil ${HTB_RATE_KBIT}kbit burst 64k 2>&1
# Apply netem as child for per-ms delivery granularity
run_tc qdisc add dev lo parent 1:10 handle 10: netem delay ${D}ms 2>&1
run_tc qdisc show dev lo

# Start iperf3 server
run_iperf3 -s -p $PORT > /tmp/iperf3_server.log 2>&1 &
SPID=$!
sleep 0.5

# Start iperf3 client, force BBR
run_iperf3 -c 127.0.0.1 -p $PORT -t $DURATION -C bbr -J > /tmp/iperf3_client.json 2> /tmp/iperf3_err.log &
CPID=$!
sleep 0.3

W=10
c=$W
T_ANALYTIC_SIGNED=$(( (B/D - 2) * W + c ))
echo "T_analytic (signed floor) = ${T_ANALYTIC_SIGNED} ms"

echo "t_ms pacing_bps cwnd rtt_ms raw_pacing" > /tmp/ss_trace.txt
T0_S=$(date +%s)
T0_NS=$(date +%N 2>/dev/null)
if [ -z "$T0_NS" ] || [ "$T0_NS" = "%N" ]; then T0_NS=0; fi
# Strip leading zeros (octal risk)
T0_NS=$(printf '%d' "${T0_NS#0}")
T0_MS=$(( T0_S * 1000 + T0_NS / 1000000 ))
ONSET_MS=""
EPS_BPS=8000
PEAK_PACING_BPS=0
while kill -0 $CPID 2>/dev/null; do
  NOW_S=$(date +%s)
  NOW_NS=$(date +%N 2>/dev/null)
  if [ -z "$NOW_NS" ] || [ "$NOW_NS" = "%N" ]; then NOW_NS=0; fi
  NOW_NS=$(printf '%d' "${NOW_NS#0}")
  NOW_MS=$(( NOW_S * 1000 + NOW_NS / 1000000 ))
  MS=$(( NOW_MS - T0_MS ))
  SSOUT=$(run_ss -tin "( dport = :$PORT or sport = :$PORT )" 2>/dev/null)
  SSLINE=$(echo "$SSOUT" | tr '\n' ' ')
  PR=$(echo "$SSLINE" | grep -oE "pacing_rate [0-9.]+[KMG]?bps" | head -1 | awk '{print $2}')
  CWND=$(echo "$SSLINE" | grep -oE "cwnd:[0-9]+" | head -1 | sed 's/cwnd://')
  RTT=$(echo "$SSLINE" | grep -oE "rtt:[0-9.]+/" | head -1 | sed 's/rtt://;s|/||')
  PR_BPS=""
  if [ -n "$PR" ]; then
    NUM=$(echo "$PR" | grep -oE "^[0-9.]+")
    UNIT=$(echo "$PR" | grep -oE "[KMG]?bps$" | sed 's/bps//')
    case "$UNIT" in
      K) PR_BPS=$(awk -v n="$NUM" 'BEGIN{printf "%.0f", n*1000}') ;;
      M) PR_BPS=$(awk -v n="$NUM" 'BEGIN{printf "%.0f", n*1000000}') ;;
      G) PR_BPS=$(awk -v n="$NUM" 'BEGIN{printf "%.0f", n*1000000000}') ;;
      *) PR_BPS=$(awk -v n="$NUM" 'BEGIN{printf "%.0f", n}') ;;
    esac
    if [ -n "$PR_BPS" ]; then
      if [ "$PR_BPS" -gt "$PEAK_PACING_BPS" ] 2>/dev/null; then PEAK_PACING_BPS=$PR_BPS; fi
    fi
  fi
  echo "$MS ${PR_BPS:-NA} ${CWND:-NA} ${RTT:-NA} ${PR:-none}" >> /tmp/ss_trace.txt
  if [ -n "$PR_BPS" ] && [ -z "$ONSET_MS" ] && [ "$PEAK_PACING_BPS" -gt 100000 ] 2>/dev/null; then
    # Only flag onset AFTER we've seen a legitimate high pacing rate
    CMP=$(awk -v p="$PR_BPS" -v e="$EPS_BPS" 'BEGIN{print (p<e)?1:0}')
    if [ "$CMP" = "1" ]; then
      ONSET_MS=$MS
      echo "*** ONSET at t=${MS}ms (pacing=${PR_BPS}bps) ***"
    fi
  fi
  usleep 100000
done
wait $CPID 2>/dev/null
kill $SPID 2>/dev/null

echo "--- ss trace tail (last 30) ---"
tail -30 /tmp/ss_trace.txt
echo "--- line count ---"
wc -l /tmp/ss_trace.txt
echo "peak_pacing_bps = $PEAK_PACING_BPS"

cp /tmp/ss_trace.txt /results/ss_trace_B${B}_D${D}_s${SEED}_t${DURATION}.txt 2>/dev/null
cp /tmp/iperf3_client.json /results/iperf3_B${B}_D${D}_s${SEED}_t${DURATION}.json 2>/dev/null

T_KERNEL=""
RESIDUAL=""
if [ -n "$ONSET_MS" ]; then
  T_KERNEL=$ONSET_MS
  RESIDUAL=$((T_KERNEL - T_ANALYTIC_SIGNED))
fi

CSV=/results/sanity_cell.csv
if [ ! -w /results ]; then CSV=/tmp/sanity_cell.csv; fi
if [ ! -f "$CSV" ]; then
  echo "B,D,link_rate,seed,T_kernel_ms,T_analytic_ms,residual_ms" > "$CSV"
fi
echo "$B,$D,$LINK_RATE,$SEED,${T_KERNEL:-NA},$T_ANALYTIC_SIGNED,${RESIDUAL:-NA}" >> "$CSV"
echo "--- $CSV ---"
cat "$CSV"

echo "--- iperf3 err ---"
cat /tmp/iperf3_err.log 2>&1 | head -20
echo "--- iperf3 client (end) ---"
tail -50 /tmp/iperf3_client.json 2>&1

sync
echo "=== DONE ==="
poweroff -f
