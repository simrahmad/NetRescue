#!/usr/bin/env bash
# Bring a link down or up.  OWNER: Zainab Fatima
# Usage: sudo bash link_fail.sh down | sudo bash link_fail.sh up | bash link_fail.sh status
#   Both ends of the link are switched (default s1-s2, i.e. s1-eth2 and s2-eth1),
#   so the failure is complete in both directions.
#   Link: env NETRESCUE_LINK. The exact time of the change is printed as an
#   "EVENT <epoch> link_down|link_up <link>" line (read it for recovery time).
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$DIR/common.sh"

usage() { echo "Usage: sudo bash $0 down | up | status" >&2; exit 2; }
cmd="${1:-}"; [ -n "$cmd" ] || usage

nr_link_ifaces "$NR_LINK"

case "$cmd" in
  down|up)
    nr_require_root "$@"
    nr_require_iface "$NR_IF_DATA"; nr_require_iface "$NR_IF_PEER"
    "$IP" link set dev "$NR_IF_DATA" "$cmd"
    "$IP" link set dev "$NR_IF_PEER" "$cmd"
    nr_event "link_$cmd" "$NR_LINK" "$NR_IF_DATA,$NR_IF_PEER"
    ;;
  status)
    "$IP" -br link show dev "$NR_IF_DATA"; "$IP" -br link show dev "$NR_IF_PEER" ;;
  *) usage ;;
esac
