#!/usr/bin/env bash
# Shared helpers for the NetRescue scenario scripts.  OWNER: Zainab Fatima
# Sourced by delay.sh, loss.sh, bandwidth.sh, link_fail.sh, clear_all.sh.
#
# WHY NOT "tc qdisc add ... root netem"?
#   Mininet's TCLink already installed, on every core interface:
#       root  htb  5:      (rate limit from bw=...)
#       child netem 10:    (delay from delay=...)   parent 5:1
#   "add root" would fail with "File exists". These scripts CHANGE the existing
#   netem qdisc / htb class instead, and restore the original values on "clear".
#   If a link has no netem (topology built without TCLink delay) a root netem is
#   created and removed again on clear.
#
# Impaired link:  env NETRESCUE_LINK (default s1-s2, the first hop of Path A).
#   Delay, loss and bandwidth are applied to the interface that carries the
#   h1 -> h2 direction (the lower-numbered switch), so "delay add 100ms" raises
#   the ping RTT by 100 ms and "loss add 5%" gives about 5 percent ping loss.
#   link_fail takes both ends of the link down.
#
# Event line printed by every scenario (M5: parse this for recovery time):
#   EVENT <epoch_seconds.nanoseconds> <event_name> <link> <detail>
#   also appended to $NR_STATE_DIR/events.log
#
# Test hooks: TC, IP (command names), NR_SKIP_ROOT_CHECK=1, NR_STATE_DIR.

TC="${TC:-tc}"
IP="${IP:-ip}"
NR_STATE_DIR="${NR_STATE_DIR:-/tmp/netrescue_scenarios}"
NR_LINK="${NETRESCUE_LINK:-s1-s2}"

# Original (healthy) link properties. MUST match topology/diamond_topo.py
# (PATH_A / PATH_B); tests/test_scenarios.py checks this.
#   link   base delay (ms)   base rate
nr_base_delay_ms() {
  case "$1" in s1-s2|s2-s4) echo 5 ;; s1-s3|s3-s4) echo 12 ;; *) return 1 ;; esac
}
nr_base_rate_mbit() {
  case "$1" in s1-s2|s2-s4) echo 10 ;; s1-s3|s3-s4) echo 5 ;; *) return 1 ;; esac
}

nr_die() { echo "ERROR: $*" >&2; exit 1; }

nr_require_root() {
  [ "${NR_SKIP_ROOT_CHECK:-0}" = "1" ] && return 0
  [ "$(id -u)" -eq 0 ] || nr_die "must run as root:  sudo bash $0 $*"
}

# Sets NR_IF_DATA (carries h1->h2 traffic) and NR_IF_PEER (other end).
nr_link_ifaces() {
  case "$1" in
    s1-s2) NR_IF_DATA=s1-eth2; NR_IF_PEER=s2-eth1 ;;
    s1-s3) NR_IF_DATA=s1-eth3; NR_IF_PEER=s3-eth1 ;;
    s2-s4) NR_IF_DATA=s2-eth2; NR_IF_PEER=s4-eth1 ;;
    s3-s4) NR_IF_DATA=s3-eth2; NR_IF_PEER=s4-eth2 ;;
    *) nr_die "unknown link '$1' (use s1-s2, s1-s3, s2-s4 or s3-s4)" ;;
  esac
}

nr_require_iface() {
  "$IP" link show dev "$1" >/dev/null 2>&1 \
    || nr_die "interface $1 not found. Is Mininet running? (make topo)"
}

nr_now() { date +%s.%N; }

nr_event() {  # nr_event <name> <link> <detail>
  local line="EVENT $(nr_now) $1 $2 ${3:-}"
  mkdir -p "$NR_STATE_DIR" 2>/dev/null && echo "$line" >> "$NR_STATE_DIR/events.log" 2>/dev/null
  echo "$line"
}

# nr_to_ms 100ms | 0.5s | 250us | 40  -> milliseconds (plain number = ms)
nr_to_ms() {
  echo "$1" | awk '{
    if (match($0, /^[0-9]+(\.[0-9]+)?(us|ms|s)?$/) == 0) { exit 1 }
    v = $0; unit = "ms"
    if (v ~ /us$/) { unit = "us"; sub(/us$/, "", v) }
    else if (v ~ /ms$/) { sub(/ms$/, "", v) }
    else if (v ~ /s$/) { unit = "s"; sub(/s$/, "", v) }
    if (unit == "us") v = v / 1000
    if (unit == "s")  v = v * 1000
    printf "%.3f\n", v }'
}

# ---- netem (delay / loss) ---------------------------------------------------
# Reads the live netem qdisc of a device into:
#   NR_NETEM_PRESENT (0/1) NR_NETEM_PARENT NR_NETEM_HANDLE NR_NETEM_LIMIT
#   NR_NETEM_DELAY_MS NR_NETEM_LOSS (percent number, 0 if none)
nr_read_netem() {
  local dev="$1" line
  line="$("$TC" qdisc show dev "$dev" 2>/dev/null | grep -m1 '^qdisc netem' || true)"
  NR_NETEM_PRESENT=0; NR_NETEM_PARENT=root; NR_NETEM_HANDLE=""
  NR_NETEM_LIMIT=""; NR_NETEM_DELAY_MS=0; NR_NETEM_LOSS=0
  [ -z "$line" ] && return 0
  NR_NETEM_PRESENT=1
  NR_NETEM_HANDLE="$(echo "$line" | awk '{print $3}')"
  NR_NETEM_PARENT="$(echo "$line" | awk '{for(i=1;i<=NF;i++) if($i=="parent"){print $(i+1); exit} print "root"}')"
  NR_NETEM_LIMIT="$(echo "$line" | awk '{for(i=1;i<=NF;i++) if($i=="limit"){print $(i+1); exit}}')"
  local d
  d="$(echo "$line" | awk '{for(i=1;i<=NF;i++) if($i=="delay"){print $(i+1); exit}}')"
  [ -n "$d" ] && NR_NETEM_DELAY_MS="$(nr_to_ms "$d" || echo 0)"
  NR_NETEM_LOSS="$(echo "$line" | awk '{for(i=1;i<=NF;i++) if($i=="loss"){v=$(i+1); if(v=="random") v=$(i+2); sub(/%$/,"",v); print v; exit} print 0}')"
}

# nr_apply_netem <dev> <delay_ms> <loss_percent>
nr_apply_netem() {
  local dev="$1" delay_ms="$2" loss="$3" args
  delay_ms="$(awk -v d="$delay_ms" 'BEGIN{printf "%g", d+0}')"   # 105.000 -> 105
  args="netem"
  [ -n "$NR_NETEM_LIMIT" ] && args="$args limit $NR_NETEM_LIMIT"
  args="$args delay ${delay_ms}ms"
  if awk -v l="$loss" 'BEGIN{exit !(l+0 > 0)}'; then args="$args loss ${loss}%"; fi
  if [ "$NR_NETEM_PRESENT" = "1" ]; then
    if [ "$NR_NETEM_PARENT" = "root" ]; then
      # shellcheck disable=SC2086
      "$TC" qdisc change dev "$dev" root handle "$NR_NETEM_HANDLE" $args
    else
      # shellcheck disable=SC2086
      "$TC" qdisc change dev "$dev" parent "$NR_NETEM_PARENT" handle "$NR_NETEM_HANDLE" $args
    fi
  else
    # no netem yet: create one on the root (removed again by nr_netem_remove_if_idle)
    # shellcheck disable=SC2086
    "$TC" qdisc replace dev "$dev" root $args
  fi
}

# After a clear: if we had to create a root netem and nothing is impaired, remove it.
nr_netem_remove_if_idle() {
  local dev="$1" base_ms="$2"
  nr_read_netem "$dev"
  if [ "$NR_NETEM_PRESENT" = "1" ] && [ "$NR_NETEM_PARENT" = "root" ] \
     && awk -v d="$NR_NETEM_DELAY_MS" -v b="$base_ms" -v l="$NR_NETEM_LOSS" \
          'BEGIN{exit !((d+0) <= (b+0) && (l+0) == 0)}' \
     && [ "$("$TC" qdisc show dev "$dev" 2>/dev/null | grep -c htb || true)" = "0" ]; then
    "$TC" qdisc del dev "$dev" root 2>/dev/null || true
  fi
}

# Print the tc state of a device (used by every "status" command).
nr_show_tc() {
  echo "--- tc qdisc show dev $1"; "$TC" qdisc show dev "$1" 2>&1
  echo "--- tc class show dev $1"; "$TC" class show dev "$1" 2>&1
}
