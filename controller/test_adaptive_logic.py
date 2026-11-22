"""Tests for Simrah's controller logic (no Ryu or Mininet needed)."""
import pytest

from controller.dev_feed import snapshot
from controller.flow_plan import H1_IP, H2_IP, changed_rules, plan_for
from routing.engine import AdaptiveRouter


# --- forwarding plan ---------------------------------------------------------
def test_plan_a_matches_baseline_table():
    assert plan_for("A") == {
        1: {H2_IP: 2, H1_IP: 1},
        2: {H2_IP: 2, H1_IP: 1},
        3: {H2_IP: 2, H1_IP: 1},
        4: {H2_IP: 3, H1_IP: 1},
    }


def test_plan_b_changes_only_the_branch_points():
    assert changed_rules(plan_for("A"), plan_for("B")) == [(1, H2_IP, 3), (4, H1_IP, 2)]
    assert changed_rules(plan_for("B"), plan_for("A")) == [(1, H2_IP, 2), (4, H1_IP, 1)]


def test_no_change_for_same_path():
    assert changed_rules(plan_for("A"), plan_for("A")) == []


def test_unknown_path_rejected():
    with pytest.raises(ValueError):
        plan_for("C")


# --- decisions on the fake scenarios ---------------------------------------
def _run(router, scenario, seconds):
    last = None
    for _ in range(seconds):
        last = router.decide(snapshot(scenario))
    return last


def test_normal_stays_on_path_a():
    router = AdaptiveRouter()
    assert _run(router, "normal", 5)["path_name"] == "A"
    assert router.route_changes == 0


def test_congestion_moves_to_b_after_three_readings_then_back():
    router = AdaptiveRouter()
    _run(router, "normal", 2)
    assert _run(router, "congest", 2)["path_name"] == "A"      # hysteresis: not yet
    assert _run(router, "congest", 1)["path_name"] == "B"      # third reading switches
    assert _run(router, "recover", 2)["path_name"] == "B"
    assert _run(router, "recover", 1)["path_name"] == "A"
    assert router.route_changes == 2


def test_failure_switches_immediately():
    router = AdaptiveRouter()
    _run(router, "normal", 2)
    decision = router.decide(snapshot("fail"))
    assert decision["path_name"] == "B" and decision["changed"]
    assert any(e["type"] == "link_down" for e in decision["events"])