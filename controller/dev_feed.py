#!/usr/bin/env python3
"""Development tool: write a fake metrics snapshot for the adaptive controller.

NOT the monitoring code (that is Member 3's monitoring/ folder). This only lets
Simrah test the controller before live metrics exist.

  python controller/dev_feed.py normal    both paths healthy (Path A is cheaper)
  python controller/dev_feed.py congest   Path A link s1-s2 congested (loss, delay, load)
  python controller/dev_feed.py fail      Path A link s1-s2 down
  python controller/dev_feed.py recover   same as normal

The controller re-reads the file every second, so a state held for 3 seconds
counts as 3 consecutive readings (hysteresis needs 3).
Output file: $NETRESCUE_DEV_FEED or /tmp/netrescue_feed.json
"""
import argparse
import json
import os
from datetime import datetime, timezone

DEFAULT_FILE = "/tmp/netrescue_feed.json"


def _link(link, latency, loss, util, status="up", capacity=10):
    return {"link": link, "latency_ms": latency, "loss_pct": loss,
            "throughput_mbps": round(util * capacity, 2), "util": util,
            "capacity_mbps": capacity, "status": status}


def snapshot(scenario, now=None):
    """Return a metrics snapshot dict following docs/api_contract.md."""
    a1 = _link("s1-s2", 10.0, 0.0, 0.10)
    a2 = _link("s2-s4", 10.0, 0.0, 0.10)
    b1 = _link("s1-s3", 24.0, 0.0, 0.05, capacity=5)
    b2 = _link("s3-s4", 24.0, 0.0, 0.05, capacity=5)
    if scenario == "congest":
        a1 = _link("s1-s2", 145.0, 4.2, 0.92, "congested")
    elif scenario == "fail":
        a1 = _link("s1-s2", None, 100.0, 0.0, "down")
    elif scenario not in ("normal", "recover"):
        raise ValueError("unknown scenario %r" % (scenario,))
    stamp = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"timestamp": stamp, "links": [a1, a2, b1, b2]}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("scenario", choices=["normal", "congest", "fail", "recover"])
    parser.add_argument("--file", default=os.environ.get("NETRESCUE_DEV_FEED", DEFAULT_FILE))
    args = parser.parse_args()
    tmp = args.file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(snapshot(args.scenario), f, indent=2)
    os.replace(tmp, args.file)           # atomic: the controller never reads half a file
    print("wrote %s scenario to %s" % (args.scenario, args.file))


if __name__ == "__main__":
    main()