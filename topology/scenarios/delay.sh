#!/usr/bin/env bash
# Add or remove extra delay on Path A.  OWNER: Zainab Fatima
# Usage: sudo bash delay.sh add 100ms | sudo bash delay.sh clear | bash delay.sh status
#   value: 100ms, 0.5s, 250us (plain number = ms). Extra delay is ADDED to the
#   link's normal delay (5 ms on Path A), so "add 100ms" gives 105 ms.
#   Link: env NETRESCUE_LINK (default s1-s2). Any loss already set is kept.
#   Verify:  tc qdisc show dev s1-eth2   (or: bash delay.sh status)
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$DIR/common.sh"

usage() { echo "Usage: sudo bash $0 add <delay e.g. 100ms> | clear | status" >&2; exit 2; }
cmd="${1:-}"; [ -n "$cmd" ] || usage

nr_link_ifaces "$NR_LINK"
base_ms="$(nr_base_delay_ms "$NR_LINK")"

case "$cmd" in
  add)
    [ $# -eq 2 ] || usage
    extra_ms="$(nr_to_ms "$2")" || nr_die "bad delay '$2' (examples: 100ms, 0.5s)"
    nr_require_root "$@"; nr_require_iface "$NR_IF_DATA"
    nr_read_netem "$NR_IF_DATA"
    total="$(awk -v b="$base_ms" -v e="$extra_ms" 'BEGIN{printf "%.3f", b+e}')"
    nr_apply_netem "$NR_IF_DATA" "$total" "$NR_NETEM_LOSS"
    nr_event delay_add "$NR_LINK" "+${extra_ms}ms total=${total}ms"
    ;;
  clear)
    nr_require_root "$@"; nr_require_iface "$NR_IF_DATA"
    nr_read_netem "$NR_IF_DATA"
    nr_apply_netem "$NR_IF_DATA" "$base_ms" "$NR_NETEM_LOSS"
    nr_netem_remove_if_idle "$NR_IF_DATA" "$base_ms"
    nr_event delay_clear "$NR_LINK" "total=${base_ms}ms"
    ;;
  status)
    nr_require_iface "$NR_IF_DATA"; nr_show_tc "$NR_IF_DATA" ;;
  *) usage ;;
esac
