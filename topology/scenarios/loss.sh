#!/usr/bin/env bash
# Add or remove packet loss on Path A.  OWNER: Zainab Fatima
# Usage: sudo bash loss.sh add 5% | sudo bash loss.sh clear | bash loss.sh status
#   value: 5%, 2.5 (the % sign is optional), 0-100. Applied with tc netem on
#   the h1->h2 direction, so ping loss is about the given percentage.
#   Link: env NETRESCUE_LINK (default s1-s2). The link's normal delay is kept.
#   Verify:  tc qdisc show dev s1-eth2   (or: bash loss.sh status)
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$DIR/common.sh"

usage() { echo "Usage: sudo bash $0 add <loss e.g. 5%> | clear | status" >&2; exit 2; }
cmd="${1:-}"; [ -n "$cmd" ] || usage

nr_link_ifaces "$NR_LINK"
base_ms="$(nr_base_delay_ms "$NR_LINK")"

case "$cmd" in
  add)
    [ $# -eq 2 ] || usage
    pct="${2%\%}"
    echo "$pct" | grep -Eq '^[0-9]+(\.[0-9]+)?$' || nr_die "bad loss '$2' (example: 5%)"
    awk -v p="$pct" 'BEGIN{exit !(p+0 >= 0 && p+0 <= 100)}' || nr_die "loss must be 0-100"
    nr_require_root "$@"; nr_require_iface "$NR_IF_DATA"
    nr_read_netem "$NR_IF_DATA"
    # keep whatever delay is currently set (base or base+extra)
    delay="$NR_NETEM_DELAY_MS"
    [ "$NR_NETEM_PRESENT" = "1" ] || delay="$base_ms"
    nr_apply_netem "$NR_IF_DATA" "$delay" "$pct"
    nr_event loss_add "$NR_LINK" "${pct}%"
    ;;
  clear)
    nr_require_root "$@"; nr_require_iface "$NR_IF_DATA"
    nr_read_netem "$NR_IF_DATA"
    delay="$NR_NETEM_DELAY_MS"
    [ "$NR_NETEM_PRESENT" = "1" ] || delay="$base_ms"
    nr_apply_netem "$NR_IF_DATA" "$delay" 0
    nr_netem_remove_if_idle "$NR_IF_DATA" "$base_ms"
    nr_event loss_clear "$NR_LINK" "0%"
    ;;
  status)
    nr_require_iface "$NR_IF_DATA"; nr_show_tc "$NR_IF_DATA" ;;
  *) usage ;;
esac
