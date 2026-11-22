"""Unit tests for routing/ using fake metrics (no Mininet, no Ryu).  OWNER: Zainab"""
import json
import math
import os

import pytest

from routing import AdaptiveRouter, PathSelector, build_graph, shortest_path
from routing.cost import (DEFAULT_WEIGHTS, DOWN_COST, all_link_costs, cost_breakdown,
                          link_cost, normalize)
from routing.graph import (CORE_LINKS, all_path_costs, full_route, link_id,
                           path_cost, path_links)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def link(name, lat=10.0, loss=0.0, util=0.1, status="up"):
    return {"link": name, "latency_ms": lat, "loss_pct": loss, "util": util,
            "capacity_mbps": 10, "status": status}


def snapshot(a_lat=10, a_loss=0.0, a_util=0.1, a_status="up",
             b_lat=24, b_loss=0.0, b_util=0.1, b_status="up"):
    """Healthy diamond by default. Impairments are applied to Path A's first link."""
    return {"timestamp": "2026-11-16T10:30:00Z", "links": [
        link("s1-s2", a_lat, a_loss, a_util, a_status),
        link("s2-s4", 10, 0.0, 0.1),
        link("s1-s3", b_lat, b_loss, b_util, b_status),
        link("s3-s4", 24, 0.0, 0.1),
    ]}


# ---------------------------------------------------------------- cost.py
def test_normalize_clips_and_handles_missing():
    assert normalize(100, 200) == 0.5
    assert normalize(500, 200) == 1.0
    assert normalize(-5, 200) == 0.0
    assert normalize(None, 200) == 1.0
    assert normalize(float("nan"), 200) == 1.0
    with pytest.raises(ValueError):
        normalize(1, 0)


def test_link_cost_formula():
    m = link("s1-s2", lat=100, loss=5, util=0.5)
    # L=0.5, P=0.5, U=0.5 with weights 0.4/0.4/0.2 -> 0.5
    assert link_cost(m) == pytest.approx(0.5)
    b = cost_breakdown(m)
    assert b["latency_term"] + b["loss_term"] + b["util_term"] == pytest.approx(b["cost"])


def test_down_link_is_infinite_and_congested_is_not():
    assert link_cost(link("s1-s2", status="down")) == DOWN_COST
    assert link_cost(link("s1-s2", status="congested", util=0.9)) < math.inf


def test_cost_grows_with_each_metric():
    base = link_cost(link("x"))
    assert link_cost(link("x", lat=100)) > base
    assert link_cost(link("x", loss=3)) > base
    assert link_cost(link("x", util=0.9)) > base


def test_missing_latency_is_worst_case_but_missing_util_is_not():
    m = {"link": "s1-s2", "latency_ms": None, "loss_pct": 100, "status": "up"}
    assert cost_breakdown(m)["L"] == 1.0
    assert cost_breakdown(m)["U"] == 0.0


def test_weights_are_validated():
    with pytest.raises(ValueError):
        link_cost(link("x"), {"alpha": 1, "beta": 1})
    with pytest.raises(ValueError):
        link_cost(link("x"), {"alpha": -1, "beta": 1, "gamma": 1})


def test_all_link_costs_accepts_snapshot_and_list():
    s = snapshot()
    assert set(all_link_costs(s)) == set(CORE_LINKS)
    assert all_link_costs(s["links"]) == all_link_costs(s)


def test_mock_metrics_file_works():
    with open(os.path.join(ROOT, "data", "mock_metrics.json")) as f:
        mock = json.load(f)["metrics"]
    costs = all_link_costs(mock)
    assert set(costs) == set(CORE_LINKS)
    # the mock describes a congested Path A, so B must be cheaper
    paths = all_path_costs(costs)
    assert paths["B"] < paths["A"]


# ---------------------------------------------------------------- graph.py
def test_link_id_is_lower_number_first():
    assert link_id("s4", "s2") == "s2-s4"
    assert link_id("s1", "s3") == "s1-s3"


def test_path_links_and_reverse():
    assert path_links(["s1", "s2", "s4"]) == ["s1-s2", "s2-s4"]
    assert path_links(["s4", "s2", "s1"]) == ["s2-s4", "s1-s2"]


def test_build_graph_is_bidirectional():
    g = build_graph({"s1-s2": 0.3, "s2-s4": 0.2})
    assert g["s1"]["s2"] == g["s2"]["s1"] == 0.3
    assert g["s4"]["s2"] == 0.2
    with pytest.raises(ValueError):
        build_graph({"bad": 1})


def test_path_cost_missing_link_is_infinite():
    assert path_cost({"s1-s2": 0.1}, ["s1", "s2", "s4"]) == math.inf


def test_full_route():
    assert full_route("B") == ["h1", "s1", "s3", "s4", "h2"]


# ------------------------------------------------------------- dijkstra.py
def test_dijkstra_picks_cheapest():
    g = build_graph({"s1-s2": 0.3, "s2-s4": 0.3, "s1-s3": 0.1, "s3-s4": 0.1})
    cost, nodes = shortest_path(g, "s1", "s4")
    assert nodes == ["s1", "s3", "s4"] and cost == pytest.approx(0.2)


def test_dijkstra_tie_prefers_path_a():
    g = build_graph({"s1-s2": 0.2, "s2-s4": 0.2, "s1-s3": 0.2, "s3-s4": 0.2})
    assert shortest_path(g, "s1", "s4")[1] == ["s1", "s2", "s4"]


def test_dijkstra_ignores_down_links():
    inf = math.inf
    g = build_graph({"s1-s2": inf, "s2-s4": 0.1, "s1-s3": 0.5, "s3-s4": 0.5})
    assert shortest_path(g, "s1", "s4")[1] == ["s1", "s3", "s4"]


def test_dijkstra_no_path_and_unknown_nodes():
    inf = math.inf
    g = build_graph({"s1-s2": inf, "s2-s4": 0.1, "s1-s3": inf, "s3-s4": 0.5})
    assert shortest_path(g, "s1", "s4") == (inf, [])
    assert shortest_path(g, "s1", "s9") == (inf, [])
    assert shortest_path(g, "s1", "s1") == (0.0, ["s1"])


def test_dijkstra_rejects_negative_cost():
    with pytest.raises(ValueError):
        shortest_path(build_graph({"s1-s2": -1, "s2-s4": 1}), "s1", "s4")


# ------------------------------------------------------------ PathSelector
def test_selector_first_reading_picks_cheapest():
    assert PathSelector().update({"A": 0.9, "B": 0.4}) == "B"
    assert PathSelector().update({"A": 0.4, "B": 0.4}) == "A"


def test_selector_needs_consecutive_confirmations():
    s = PathSelector(margin=0.2, confirmations=3)
    s.update({"A": 0.2, "B": 0.5})                    # start on A
    assert s.update({"A": 0.9, "B": 0.4}) == "A"      # 1st reading
    assert s.update({"A": 0.9, "B": 0.4}) == "A"      # 2nd
    assert s.update({"A": 0.9, "B": 0.4}) == "B"      # 3rd -> switch
    assert s.switches == 1


def test_selector_streak_resets_when_condition_breaks():
    s = PathSelector(margin=0.2, confirmations=3)
    s.update({"A": 0.2, "B": 0.5})
    s.update({"A": 0.9, "B": 0.4})
    s.update({"A": 0.9, "B": 0.4})
    s.update({"A": 0.3, "B": 0.4})                    # spike over: streak reset
    assert s.update({"A": 0.9, "B": 0.4}) == "A"
    assert s.switches == 0


def test_selector_margin_blocks_small_gains():
    s = PathSelector(margin=0.2, confirmations=1)
    s.update({"A": 0.5, "B": 0.9})
    assert s.update({"A": 0.5, "B": 0.45}) == "A"     # only 10% cheaper
    assert s.update({"A": 0.5, "B": 0.39}) == "B"     # 22% cheaper


def test_selector_failure_switches_immediately():
    s = PathSelector(margin=0.2, confirmations=5, cooldown=10)
    s.update({"A": 0.2, "B": 0.5})
    assert s.update({"A": math.inf, "B": 0.5}) == "B"
    assert s.switches == 1


def test_selector_all_paths_down_keeps_current_and_recovers():
    s = PathSelector()
    s.update({"A": 0.2, "B": 0.5})
    assert s.update({"A": math.inf, "B": math.inf}) == "A"
    assert s.update({"A": math.inf, "B": 0.5}) == "B"


def test_selector_starts_on_default_when_nothing_usable():
    s = PathSelector()
    assert s.update({"A": math.inf, "B": math.inf}) == "A"
    assert s.update({"A": math.inf, "B": 0.4}) == "B"


def test_selector_cooldown_delays_cost_based_switch():
    s = PathSelector(margin=0.1, confirmations=1, cooldown=3)
    s.update({"A": 0.9, "B": 0.1})                    # starts on B
    s.update({"A": 0.1, "B": 0.9})                    # allowed: nothing switched yet
    assert s.current == "A"
    for _ in range(3):                                # within cooldown
        assert s.update({"A": 0.9, "B": 0.1}) == "A"
    assert s.update({"A": 0.9, "B": 0.1}) == "B"


def test_selector_reset_and_validation():
    s = PathSelector()
    s.update({"A": 0.1, "B": 0.2})
    s.reset()
    assert s.current is None and s.switches == 0
    for bad in (dict(margin=1.0), dict(margin=-0.1), dict(confirmations=0), dict(cooldown=-1)):
        with pytest.raises(ValueError):
            PathSelector(**bad)


def test_no_flapping_under_noise():
    """Costs jittering around equal values must not cause route changes."""
    s = PathSelector(margin=0.2, confirmations=3)
    s.update({"A": 0.40, "B": 0.42})
    for i in range(50):
        wobble = 0.03 if i % 2 else -0.03
        s.update({"A": 0.40 + wobble, "B": 0.42 - wobble})
    assert s.switches == 0


# ------------------------------------------------------------ AdaptiveRouter
def run(router, snap, n):
    return [router.decide(snap) for _ in range(n)]


def test_router_starts_on_path_a_when_healthy():
    r = AdaptiveRouter()
    d = r.decide(snapshot())
    assert d["path_name"] == "A" and d["best_path"] == "A"
    assert d["path"] == ["h1", "s1", "s2", "s4", "h2"]
    assert d["changed"] is False and d["from_path"] is None
    assert d["events"][0]["type"] == "route_change"


@pytest.mark.parametrize("scenario", [
    dict(a_lat=110),                      # delay +100 ms on Path A
    dict(a_loss=5.0),                     # 5 percent loss on Path A
    dict(a_util=0.95, a_lat=60),          # saturated Path A
])
def test_router_reroutes_on_degradation(scenario):
    r = AdaptiveRouter(confirmations=3)
    r.decide(snapshot())
    decisions = run(r, snapshot(**scenario), 3)
    assert [d["changed"] for d in decisions] == [False, False, True]
    assert decisions[-1]["path_name"] == "B"
    assert decisions[-1]["best_path"] == "B"
    assert r.route_changes == 1
    assert "path A cost" in decisions[-1]["reason"]


def test_router_failure_is_immediate_and_reports_link_down():
    r = AdaptiveRouter(confirmations=5)
    r.decide(snapshot())
    d = r.decide(snapshot(a_status="down"))
    assert d["changed"] and d["path_name"] == "B"
    types = [e["type"] for e in d["events"]]
    assert "link_down" in types and "route_change" in types
    assert "unavailable" in d["reason"] and d["path_costs"]["A"] is None


def test_router_congestion_is_not_failure():
    r = AdaptiveRouter(confirmations=3)
    r.decide(snapshot())
    d = r.decide(snapshot(a_status="congested", a_util=0.85))
    assert d["path_name"] == "A"          # congestion alone: hysteresis holds
    assert [e["type"] for e in d["events"]] == ["congestion"]


def test_router_switches_back_after_restoration_only_when_cheaper():
    r = AdaptiveRouter(confirmations=2)
    r.decide(snapshot())
    r.decide(snapshot(a_status="down"))                # failover to B
    assert r.current == "B"
    run(r, snapshot(), 2)                              # A is back and cheaper
    assert r.current == "A"
    assert r.route_changes == 2


def test_router_decisions_are_json_safe():
    r = AdaptiveRouter()
    d = r.decide(snapshot(a_status="down", b_status="down"))
    json.dumps(d, allow_nan=False)                     # no Infinity/NaN anywhere
    json.dumps(r.route_object(d), allow_nan=False)


def test_router_route_object_matches_contract():
    r = AdaptiveRouter()
    obj = r.route_object(r.decide(snapshot()))
    assert set(obj) == {"timestamp", "mode", "path", "path_name", "cost"}
    assert obj["mode"] == "adaptive"


def test_router_tolerates_missing_links_and_reset():
    r = AdaptiveRouter()
    d = r.decide({"links": [link("s1-s2")]})           # incomplete snapshot
    assert d["path_name"] == "A"                       # default path, no crash
    r.reset()
    assert r.current is None and r.route_changes == 0


def test_router_dijkstra_always_agrees_with_cheapest_path():
    import random
    rnd = random.Random(7)
    for _ in range(200):
        snap = snapshot(a_lat=rnd.uniform(5, 300), a_loss=rnd.uniform(0, 20),
                        a_util=rnd.random(), b_lat=rnd.uniform(5, 300),
                        b_loss=rnd.uniform(0, 20), b_util=rnd.random())
        d = AdaptiveRouter().decide(snap)
        costs = d["path_costs"]
        assert d["best_path"] == min(costs, key=lambda n: (costs[n], n))
