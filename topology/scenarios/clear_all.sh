#!/usr/bin/env bash
# Undo every scenario on every core link: delay, loss, bandwidth, link state.
# OWNER: Zainab Fatima.  Usage: sudo bash clear_all.sh
# Run it between experiment repeats so each run starts from the same network.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$DIR/common.sh"
nr_require_root "$@"

for link in s1-s2 s1-s3 s2-s4 s3-s4; do
  export NETRESCUE_LINK="$link"
  bash "$DIR/link_fail.sh" up
  bash "$DIR/delay.sh" clear
  bash "$DIR/loss.sh" clear
  bash "$DIR/bandwidth.sh" clear
done
