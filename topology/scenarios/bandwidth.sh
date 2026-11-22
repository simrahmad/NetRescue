#!/usr/bin/env bash
# Limit bandwidth on Path A.  OWNER: Zainab Fatima
# Usage: sudo bash bandwidth.sh add 2mbit | sudo bash bandwidth.sh clear | bash bandwidth.sh status
#   rate: <number>kbit|mbit|gbit (example 2mbit). "clear" restores the original
#   rate (10 Mbit on Path A, 5 Mbit on Path B).
#   Link: env NETRESCUE_LINK (default s1-s2).
#
# Implementation note: the stub suggested tbf, but Mininet's TCLink already
# rate-limits every link with an htb class, and tbf cannot sit beside it. So we
# change the rate of that existing htb class (tc class change ...).
#
# NOTE for monitoring (M3): after the cap the link is saturated at a rate far
# below its nominal capacity. If utilization is computed against the NOMINAL
# 10 Mbps it will stay low (e.g. 0.2). The cap still shows up as higher latency
# (the queue fills) and loss, which the cost formula uses.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$DIR/common.sh"

usage() { echo "Usage: sudo bash $0 add <rate e.g. 2mbit> | clear | status" >&2; exit 2; }
cmd="${1:-}"; [ -n "$cmd" ] || usage

nr_link_ifaces "$NR_LINK"
base_rate="$(nr_base_rate_mbit "$NR_LINK")mbit"

# Finds the htb class of a device; sets NR_CLASSID and NR_CLASS_PARENT.
nr_find_htb_class() {
  local line
  line="$("$TC" class show dev "$1" 2>/dev/null | grep -m1 '^class htb' || true)"
  [ -n "$line" ] || nr_die "no htb class on $1: was the topology built with TCLink and bw=...?"
  NR_CLASSID="$(echo "$line" | awk '{print $3}')"
  NR_CLASS_PARENT="$(echo "$line" | awk -v id="$(echo "$line" | awk '{print $3}')" \
    '{for(i=1;i<=NF;i++) if($i=="parent"){print $(i+1); exit} split(id,a,":"); print a[1] ":"}')"
}

set_rate() {  # set_rate <dev> <rate>
  nr_find_htb_class "$1"
  "$TC" class change dev "$1" parent "$NR_CLASS_PARENT" classid "$NR_CLASSID" \
        htb rate "$2" ceil "$2"
}

case "$cmd" in
  add)
    [ $# -eq 2 ] || usage
    rate="$(echo "$2" | tr 'A-Z' 'a-z')"
    echo "$rate" | grep -Eq '^[0-9]+(\.[0-9]+)?(kbit|mbit|gbit)$' \
      || nr_die "bad rate '$2' (examples: 500kbit, 2mbit)"
    nr_require_root "$@"; nr_require_iface "$NR_IF_DATA"
    set_rate "$NR_IF_DATA" "$rate"
    nr_event bandwidth_add "$NR_LINK" "$rate"
    ;;
  clear)
    nr_require_root "$@"; nr_require_iface "$NR_IF_DATA"
    set_rate "$NR_IF_DATA" "$base_rate"
    nr_event bandwidth_clear "$NR_LINK" "$base_rate"
    ;;
  status)
    nr_require_iface "$NR_IF_DATA"; nr_show_tc "$NR_IF_DATA" ;;
  *) usage ;;
esac
