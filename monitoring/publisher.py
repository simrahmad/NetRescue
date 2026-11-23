"""Builds and publishes metrics snapshots.  OWNER: M3

Run on the VM while the network is up (make topo in another terminal), from the repo root:
    sudo venv/bin/python -m monitoring.publisher
Every PUBLISH_INTERVAL_S seconds the latest snapshot (docs/api_contract.md,
"Metrics snapshot") is written to METRICS_FILE; the controller reads it with read_latest().

How each value is measured
  latency, loss     ping h1 -> h2 once per path. Each probe carries a ToS mark
                    (PROBE_TOS) so the controller can pin it to Path A or B,
                    whichever path data is using. The path RTT and loss are split
                    equally over the path's two links, so link values add up to
                    the measured path values.
  throughput, util  tx byte counters of the interface carrying h1 -> h2 (port_stats.py).
  down              the link's interface is down, or DOWN_AFTER_MISSED_PROBES
                    probes in a row on its path got no reply at all.
  congested         still usable: util or loss above the thresholds below.
"""
import json
import os
import subprocess
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from monitoring.port_stats import (CAPACITY_MBPS, DATA_IFACE, compute_utilization,
                                   iface_is_down, read_tx_bytes, throughput_mbps)
from monitoring.probe import ping_probe
from routing.graph import CORE_LINKS, PATHS, path_links

PUBLISH_INTERVAL_S = 1.5
SMOOTHING_WINDOW = 3          # moving average over the last N readings
DOWN_AFTER_MISSED_PROBES = 3  # mark "down" after N missed probes in a row
CONGESTED_UTIL = 0.8          # TODO: agree thresholds with Zainab
CONGESTED_LOSS_PCT = 2.0

METRICS_FILE = "/tmp/netrescue/metrics.json"
TARGET_IP = "10.0.0.2"        # h2
PROBE_COUNT = 10
PROBE_INTERVAL_S = 0.1
PROBE_TOS = {"A": 0x20, "B": 0x40}   # DSCP 8 -> Path A, DSCP 16 -> Path B


def moving_average(values, window=SMOOTHING_WINDOW):
    """Average of the last `window` values, ignoring None. None if nothing is left."""
    recent = [v for v in list(values)[-window:] if v is not None]
    return sum(recent) / len(recent) if recent else None


def classify_status(latency_ms, loss_pct, util, missed_probes, iface_down=False):
    """Return "up", "congested", or "down". Down is checked first and only from
    missing replies or a dead interface, never from high load."""
    if iface_down or missed_probes >= DOWN_AFTER_MISSED_PROBES:
        return "down"
    if (util or 0.0) >= CONGESTED_UTIL or (loss_pct or 0.0) >= CONGESTED_LOSS_PCT:
        return "congested"
    return "up"


class MonitorState:
    """What the publisher remembers between readings."""

    def __init__(self):
        self.history = defaultdict(lambda: deque(maxlen=SMOOTHING_WINDOW))  # (link, field)
        self.missed = {name: 0 for name in PATHS}                           # per path
        self.prev_bytes = {}                                                # per link


def _round(value, digits):
    return None if value is None else round(value, digits)


def build_snapshot(state, path_results, tx_bytes, down_links, interval_s, now=None):
    """Turn one round of raw readings into the contract snapshot (pure, no Mininet).

    path_results  {"A": {"latency_ms", "loss_pct"}, "B": {...}}  from ping_probe
    tx_bytes      {"s1-s2": bytes, ...}                          from read_tx_bytes
    down_links    set of links whose interface is down
    interval_s    seconds since the previous tx_bytes reading
    """
    links = []
    for name, nodes in PATHS.items():
        result = path_results[name]
        state.missed[name] = state.missed[name] + 1 if result["loss_pct"] >= 100 else 0
        hops = path_links(nodes)
        for link in hops:
            h = state.history
            lat = result["latency_ms"]
            h[link, "latency_ms"].append(None if lat is None else lat / len(hops))
            h[link, "loss_pct"].append(result["loss_pct"] / len(hops))
            prev = state.prev_bytes.get(link, tx_bytes[link])
            h[link, "throughput_mbps"].append(throughput_mbps(prev, tx_bytes[link], interval_s))
            h[link, "util"].append(compute_utilization(prev, tx_bytes[link], interval_s,
                                                       CAPACITY_MBPS[link]))
            state.prev_bytes[link] = tx_bytes[link]

            m = {f: moving_average(h[link, f])
                 for f in ("latency_ms", "loss_pct", "throughput_mbps", "util")}
            links.append({
                "link": link,
                "latency_ms": _round(m["latency_ms"], 2),
                "loss_pct": _round(m["loss_pct"], 2),
                "throughput_mbps": _round(m["throughput_mbps"], 2),
                "util": _round(m["util"], 3),
                "capacity_mbps": CAPACITY_MBPS[link],
                "status": classify_status(m["latency_ms"], m["loss_pct"], m["util"],
                                          state.missed[name], link in down_links),
            })
    now = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"timestamp": now, "links": links}


class NamespaceHost:
    """Runs commands inside a running Mininet host from this separate process."""

    def __init__(self, name):
        pids = subprocess.run(["pgrep", "-f", "mininet:%s$" % name],
                              capture_output=True, text=True).stdout.split()
        if not pids:
            raise RuntimeError("Mininet host %s not found. Is `make topo` running?" % name)
        self.pid = pids[0]

    def cmd(self, command):
        return subprocess.run(["mnexec", "-a", self.pid, "sh", "-c", command],
                              capture_output=True, text=True).stdout


def write_snapshot(snapshot, path=METRICS_FILE):
    """Write atomically, so a reader never sees a half-written file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w") as f:
        json.dump(snapshot, f)
    os.replace(path + ".tmp", path)


def read_latest(path=METRICS_FILE):
    """Latest snapshot for the controller / API, or None if nothing is published yet."""
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def run_forever():
    """Every PUBLISH_INTERVAL_S seconds probe, build the snapshot and write it."""
    h1 = NamespaceHost("h1")
    state = MonitorState()
    last = time.monotonic()
    with ThreadPoolExecutor(len(PATHS)) as pool:
        while True:
            futures = {name: pool.submit(ping_probe, h1, TARGET_IP, PROBE_COUNT,
                                         PROBE_INTERVAL_S, PROBE_TOS[name])
                       for name in PATHS}
            results = {name: f.result() for name, f in futures.items()}
            tx = {link: read_tx_bytes(DATA_IFACE[link]) for link in CORE_LINKS}
            now = time.monotonic()
            down = {link for link in CORE_LINKS if iface_is_down(DATA_IFACE[link])}
            snapshot = build_snapshot(state, results, tx, down, now - last)
            last = now
            write_snapshot(snapshot)
            print(snapshot["timestamp"], "  ".join(
                "%s %s %s %s%% u=%s" % (l["link"], l["status"],
                                        "-" if l["latency_ms"] is None else "%sms" % l["latency_ms"],
                                        l["loss_pct"], l["util"])
                for l in snapshot["links"]), flush=True)
            time.sleep(max(0.0, PUBLISH_INTERVAL_S - (time.monotonic() - now)))


if __name__ == "__main__":
    run_forever()
