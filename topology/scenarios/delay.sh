#!/usr/bin/env bash
# Add or remove extra delay on Path A.  OWNER: Zainab Fatima
# Usage: sudo bash delay.sh add 100ms | sudo bash delay.sh clear
# TODO: use `tc qdisc add dev s1-eth2 root netem delay <value>`
#       and `tc qdisc del dev s1-eth2 root` for clear. Verify with `tc qdisc show`.
echo "delay.sh not implemented yet"