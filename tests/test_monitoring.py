"""Unit tests for monitoring/ with fake output (no Mininet, no Ryu).  OWNER: M3"""
import json
from types import SimpleNamespace

import pytest

from monitoring.port_stats import compute_utilization, throughput_mbps, tx_bytes_from_reply
from monitoring.probe import parse_iperf, parse_ping, ping_probe
from monitoring.publisher import MonitorState, build_snapshot, classify_status, moving_average
from routing import AdaptiveRouter

PING_OK = """PING 10.0.0.2 (10.0.0.2) 56(84) bytes of data.

--- 10.0.0.2 ping statistics ---
10 packets transmitted, 9 received, 10% packet loss, time 912ms
rtt min/avg/max/mdev = 20.112/20.874/22.301/0.611 ms
"""
PING_DEAD = """--- 10.0.0.2 ping statistics ---
10 packets transmitted, 0 received, 100% packet loss, time 921ms
"""


def test_parse_ping():
    assert parse_ping(PING_OK) == {"latency_ms": 20.874, "loss_pct": 10.0}
    assert parse_ping(PING_DEAD) == {"latency_ms": None, "loss_pct": 100.0}
    assert parse_ping("connect: Network is unreachable") == {"latency_ms": None,
                                                             "loss_pct": 100.0}


def test_ping_probe_builds_command():
    host = SimpleNamespace(cmd=lambda c: (host.calls.append(c), PING_OK)[1], calls=[])
    assert ping_probe(host, "10.0.0.2", count=10, interval_s=0.1, tos=0x20)["loss_pct"] == 10.0
    assert host.calls == ["ping -q -n -c 10 -i 0.1 -W 1 -Q 32 10.0.0.2"]


def test_parse_iperf():
    ok = json.dumps({"end": {"sum_received": {"bits_per_second": 9.4e6}}})
    assert parse_iperf(ok) == pytest.approx(9.4)
    assert parse_iperf(json.dumps({"error": "unable to connect"})) is None
    assert parse_iperf("not json") is None


def test_utilization():
    assert throughput_mbps(0, 1_250_000, 1.0) == pytest.approx(10.0)  # 1.25 MB/s = 10 Mbps
    assert compute_utilization(0, 625_000, 1.0, 10) == pytest.approx(0.5)
    assert compute_utilization(0, 10_000_000, 1.0, 10) == 1.0          # clipped
    assert compute_utilization(500, 100, 1.0, 10) == 0.0               # counter reset
    assert compute_utilization(0, 100, 0, 10) == 0.0                   # no time passed


def test_tx_bytes_from_reply():
    body = [SimpleNamespace(port_no=1, tx_bytes=5), SimpleNamespace(port_no=2, tx_bytes=7),
            SimpleNamespace(port_no=3, tx_bytes=9)]
    assert tx_bytes_from_reply(1, body) == {"s1-s2": 7, "s1-s3": 9}


def test_moving_average():
    assert moving_average([1, 2, 3, 4], window=3) == 3
    assert moving_average([10, None, 20]) == 15
    assert moving_average([None, None]) is None


def test_classify_status_keeps_congested_and_down_separate():
    assert classify_status(10, 0, 0.1, 0) == "up"
    assert classify_status(10, 0, 0.95, 0) == "congested"
    assert classify_status(10, 5.0, 0.1, 0) == "congested"
    assert classify_status(None, 100, 0, 3) == "down"
    assert classify_status(10, 0, 0.1, 0, iface_down=True) == "down"
    assert classify_status(None, 100, 0, 2) == "congested"   # 2 misses: not down yet


def run_rounds(rounds, a, b, a_bytes_per_round=0, down=()):
    state, snap = MonitorState(), None
    for i in range(rounds):
        tx = {"s1-s2": i * a_bytes_per_round, "s2-s4": i * a_bytes_per_round,
              "s1-s3": 0, "s3-s4": 0}
        snap = build_snapshot(state, {"A": a, "B": b}, tx, set(down), 1.0,
                              now="2026-11-22T10:00:00Z")
    return {l["link"]: l for l in snap["links"]}


HEALTHY_A = {"latency_ms": 20.0, "loss_pct": 0.0}
HEALTHY_B = {"latency_ms": 48.0, "loss_pct": 0.0}
DEAD = {"latency_ms": None, "loss_pct": 100.0}


def test_snapshot_matches_contract():
    links = run_rounds(1, HEALTHY_A, HEALTHY_B)
    assert sorted(links) == ["s1-s2", "s1-s3", "s2-s4", "s3-s4"]
    assert set(links["s1-s2"]) == {"link", "latency_ms", "loss_pct", "throughput_mbps",
                                   "util", "capacity_mbps", "status"}
    assert links["s1-s2"]["latency_ms"] == 10.0      # path RTT split over 2 links
    assert links["s1-s3"]["latency_ms"] == 24.0
    assert all(l["status"] == "up" for l in links.values())


def test_snapshot_congestion_and_failure():
    busy = run_rounds(4, HEALTHY_A, HEALTHY_B, a_bytes_per_round=1_200_000)
    assert busy["s1-s2"]["util"] == pytest.approx(0.96)
    assert busy["s1-s2"]["status"] == "congested"

    assert run_rounds(2, DEAD, HEALTHY_B)["s1-s2"]["status"] != "down"
    assert run_rounds(3, DEAD, HEALTHY_B)["s1-s2"]["status"] == "down"
    assert run_rounds(1, DEAD, HEALTHY_B, down={"s1-s2"})["s1-s2"]["status"] == "down"


def test_router_moves_to_b_when_a_is_lossy():
    state, router = MonitorState(), AdaptiveRouter()
    tx = dict.fromkeys(["s1-s2", "s2-s4", "s1-s3", "s3-s4"], 0)
    for _ in range(3):
        router.decide(build_snapshot(state, {"A": HEALTHY_A, "B": HEALTHY_B}, tx, set(), 1.0))
    assert router.current == "A"
    for _ in range(6):
        snap = build_snapshot(state, {"A": {"latency_ms": 22.0, "loss_pct": 10.0},
                                      "B": HEALTHY_B}, tx, set(), 1.0)
        router.decide(snap)
    assert router.current == "B"
