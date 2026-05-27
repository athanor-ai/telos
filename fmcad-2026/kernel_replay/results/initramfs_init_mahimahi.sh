#!/bin/busybox sh
export PATH=/usr/local/bin:/usr/sbin:/bin:/sbin:/usr/bin
/bin/busybox --install -s /bin 2>/dev/null

mount -t proc none /proc
mount -t sysfs none /sys
mount -t devtmpfs none /dev 2>/dev/null
mount -t tmpfs none /tmp
mount -t tmpfs none /run
mkdir -p /var/log /var/run /var/tmp

mkdir -p /hostroot /results
mount -t 9p -o trans=virtio,version=9p2000.L,msize=104857600,ro hostroot /hostroot || {
  echo "9p hostroot mount failed"; exec /bin/sh
}
mount -t 9p -o trans=virtio,version=9p2000.L,msize=104857600,rw results /results || {
  echo "9p results mount failed"
}

# Do NOT create self-symlink for /lib64/ld-linux-x86-64.so.2 — it's already a real file in cpio.

mkdir -p /usr/bin
for b in iperf3 ss; do
  [ -x /hostroot/usr/bin/$b ] && ln -sf /hostroot/usr/bin/$b /usr/bin/$b
done

export LD_LIBRARY_PATH=/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu:/hostroot/lib/x86_64-linux-gnu:/hostroot/lib64:/hostroot/usr/lib/x86_64-linux-gnu:/hostroot/usr/local/lib
export XTABLES_LIBDIR=/usr/lib/x86_64-linux-gnu/xtables

echo 1 > /proc/sys/net/ipv4/ip_forward
echo 1 > /proc/sys/net/ipv6/conf/all/forwarding 2>/dev/null
ip link set lo up
echo bbr > /proc/sys/net/ipv4/tcp_congestion_control
echo fq > /proc/sys/net/core/default_qdisc
chmod 1777 /tmp

echo "=== BBRv3 + mahimahi QEMU ready ==="
uname -r
echo "CC: $(cat /proc/sys/net/ipv4/tcp_available_congestion_control)"
echo "default: $(cat /proc/sys/net/ipv4/tcp_congestion_control)"

B=$(grep -oE 'bbr_B=[0-9]+' /proc/cmdline | cut -d= -f2)
D=$(grep -oE 'bbr_D=[0-9]+' /proc/cmdline | cut -d= -f2)
LINK_RATE=$(grep -oE 'bbr_R=[0-9]+' /proc/cmdline | cut -d= -f2)
SEED=$(grep -oE 'bbr_S=[0-9]+' /proc/cmdline | cut -d= -f2)
DURATION=$(grep -oE 'bbr_T=[0-9]+' /proc/cmdline | cut -d= -f2)
PORT=25001
B=${B:-8}; D=${D:-2}; LINK_RATE=${LINK_RATE:-100}; SEED=${SEED:-0}; DURATION=${DURATION:-30}
echo "CELL: B=$B D=$D link=$LINK_RATE seed=$SEED duration=${DURATION}s"

TRACE_UP=/tmp/up.trace
TRACE_DN=/tmp/dn.trace
TOTAL_MS=$(( DURATION * 1000 ))
{
  t=0
  while [ $t -lt $TOTAL_MS ]; do
    k=0
    while [ $k -lt $B ]; do echo $t; k=$((k+1)); done
    t=$((t + D))
  done
} > $TRACE_UP
DN_PER_MS=$(( LINK_RATE / 12 ))
[ $DN_PER_MS -lt 1 ] && DN_PER_MS=1
{
  t=0
  while [ $t -lt $TOTAL_MS ]; do
    k=0
    while [ $k -lt $DN_PER_MS ]; do echo $t; k=$((k+1)); done
    t=$((t + 1))
  done
} > $TRACE_DN
echo "traces: up=$(wc -l < $TRACE_UP) dn=$(wc -l < $TRACE_DN)"

iperf3 -s -p $PORT -1 > /tmp/iperf3_server.log 2>&1 &
SPID=$!
sleep 0.3

cat > /tmp/inner.sh <<'INNER'
#!/bin/sh
export PATH=/usr/bin:/usr/local/bin:/bin:/sbin:/usr/sbin
export LD_LIBRARY_PATH=/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu:/hostroot/lib/x86_64-linux-gnu:/hostroot/lib64:/hostroot/usr/lib/x86_64-linux-gnu:/hostroot/usr/local/lib
PORT=25001
DURATION="$1"
echo "[inner] uid=$(id -u)"
echo "[inner] ip addr:"; ip addr 2>&1 | head -20
echo "[inner] ip route:"; ip route 2>&1
iperf3 -c 10.0.0.1 -p $PORT -t $DURATION -C bbr -J > /tmp/iperf3_client.json 2>/tmp/iperf3_err.log &
CPID=$!
sleep 0.2
T0_S=$(date +%s); T0_NS=$(date +%N)
T0_NS=$(printf '%d' "${T0_NS#0}" 2>/dev/null || echo 0)
T0_MS=$(( T0_S * 1000 + T0_NS / 1000000 ))
echo "t_ms pacing_bps cwnd rtt_ms raw" > /tmp/ss_trace.txt
PEAK=0
ONSET=""
while kill -0 $CPID 2>/dev/null; do
  NOW_S=$(date +%s); NOW_NS=$(date +%N)
  NOW_NS=$(printf '%d' "${NOW_NS#0}" 2>/dev/null || echo 0)
  NOW_MS=$(( NOW_S * 1000 + NOW_NS / 1000000 ))
  MS=$(( NOW_MS - T0_MS ))
  LINE=$(ss -tin "( dport = :$PORT or sport = :$PORT or sport = :$PORT )" 2>/dev/null | tr '\n' ' ')
  PR=$(echo "$LINE" | grep -oE "pacing_rate [0-9.]+[KMG]?bps" | head -1 | awk '{print $2}')
  CWND=$(echo "$LINE" | grep -oE "cwnd:[0-9]+" | head -1 | sed 's/cwnd://')
  RTT=$(echo "$LINE" | grep -oE "rtt:[0-9.]+/" | head -1 | sed 's/rtt://;s|/||')
  PR_BPS=""
  if [ -n "$PR" ]; then
    N=$(echo "$PR" | grep -oE "^[0-9.]+")
    U=$(echo "$PR" | grep -oE "[KMG]?bps$" | sed 's/bps//')
    case "$U" in
      K) PR_BPS=$(awk -v n="$N" 'BEGIN{printf "%.0f", n*1000}') ;;
      M) PR_BPS=$(awk -v n="$N" 'BEGIN{printf "%.0f", n*1000000}') ;;
      G) PR_BPS=$(awk -v n="$N" 'BEGIN{printf "%.0f", n*1000000000}') ;;
      *) PR_BPS=$(awk -v n="$N" 'BEGIN{printf "%.0f", n}') ;;
    esac
    if [ -n "$PR_BPS" ] && [ "$PR_BPS" -gt "$PEAK" ] 2>/dev/null; then PEAK=$PR_BPS; fi
  fi
  echo "$MS ${PR_BPS:-NA} ${CWND:-NA} ${RTT:-NA} ${PR:-none}" >> /tmp/ss_trace.txt
  if [ -n "$PR_BPS" ] && [ -z "$ONSET" ] && [ "$PEAK" -gt 100000 ] 2>/dev/null; then
    CMP=$(awk -v p="$PR_BPS" -v e="8000" 'BEGIN{print (p<e)?1:0}')
    if [ "$CMP" = "1" ]; then
      ONSET=$MS
      echo "*** ONSET t=${MS}ms pr=${PR_BPS}bps ***"
    fi
  fi
  usleep 100000
done
wait $CPID 2>/dev/null
echo "PEAK=$PEAK ONSET=${ONSET:-NA}"
[ -n "$ONSET" ] && echo "$ONSET" > /tmp/onset_ms.txt
echo "$PEAK" > /tmp/peak_bps.txt
INNER
chmod +x /tmp/inner.sh
chown mmuser:mmuser /tmp/inner.sh /tmp/up.trace /tmp/dn.trace 2>/dev/null
chmod 666 /tmp/up.trace /tmp/dn.trace 2>/dev/null

echo "--- running mm-link as mmuser ---"
MML_LOG=/tmp/mm-link.log
busybox su mmuser -s /bin/sh -c \
  "export XTABLES_LIBDIR=/usr/lib/x86_64-linux-gnu/xtables; export LD_LIBRARY_PATH=/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu:/hostroot/lib/x86_64-linux-gnu:/hostroot/lib64:/hostroot/usr/lib/x86_64-linux-gnu:/hostroot/usr/local/lib; /usr/local/bin/mm-link $TRACE_UP $TRACE_DN --uplink-log=/tmp/up.log --downlink-log=/tmp/dn.log -- /bin/sh /tmp/inner.sh $DURATION" \
  > $MML_LOG 2>&1 &
MMPID=$!
W=$(( DURATION + 20 ))
waited=0
while kill -0 $MMPID 2>/dev/null && [ $waited -lt $W ]; do
  sleep 1
  waited=$((waited+1))
done
if kill -0 $MMPID 2>/dev/null; then
  echo "mm-link timeout after ${W}s; killing"
  kill -9 $MMPID 2>/dev/null
fi
wait $MMPID 2>/dev/null
kill $SPID 2>/dev/null

echo "--- mm-link log (last 100) ---"
tail -100 $MML_LOG 2>/dev/null

echo "--- ss_trace tail ---"
tail -15 /tmp/ss_trace.txt 2>/dev/null
echo "--- onset ---"
cat /tmp/onset_ms.txt 2>/dev/null || echo "(none)"
echo "--- peak ---"
cat /tmp/peak_bps.txt 2>/dev/null || echo "(none)"

W=10
T_ANALYTIC=$(( (B/D - 2) * W + W ))
ONSET_MS=$(cat /tmp/onset_ms.txt 2>/dev/null)
PEAK_BPS=$(cat /tmp/peak_bps.txt 2>/dev/null)
T_KERNEL=${ONSET_MS:-NA}
RES=NA
if [ "$T_KERNEL" != "NA" ] && [ -n "$T_KERNEL" ]; then
  RES=$(( T_KERNEL - T_ANALYTIC ))
fi

CSV=/results/mm_cell.csv
if [ ! -f "$CSV" ]; then
  echo "B,D,link_rate,seed,T_kernel_ms,T_analytic_ms,residual_ms,peak_bps,method" > "$CSV"
fi
echo "$B,$D,$LINK_RATE,$SEED,$T_KERNEL,$T_ANALYTIC,$RES,${PEAK_BPS:-NA},mahimahi" >> "$CSV"

cp /tmp/ss_trace.txt /results/mm_ss_trace_B${B}_D${D}.txt 2>/dev/null
cp /tmp/iperf3_client.json /results/mm_iperf3_B${B}_D${D}.json 2>/dev/null
cp /tmp/mm-link.log /results/mm_link_B${B}_D${D}.log 2>/dev/null
cp /tmp/iperf3_err.log /results/mm_iperf3_err_B${B}_D${D}.log 2>/dev/null
cp /tmp/up.log /results/mm_up_B${B}_D${D}.log 2>/dev/null

echo "--- $CSV ---"
cat "$CSV"
sync
echo "=== DONE ==="
poweroff -f
