"""Tests for the REST API response builders (no Ryu needed)."""
import json

import pytest

from controller.api_payloads import (PATH_NODES, TOPOLOGY, clean, events_payload,
                                     metrics_payload, mode_payload, parse_mode_body,
                                     route_payload, to_json)


def _state(**over):
    state = {"mode": "adaptive", "path_name": "A", "route": None, "metrics": None,
             "events": [], "route_changes": 0}
    state.update(over)
    return state


def test_topology_matches_mock_file():
    from pathlib import Path
    mock = json.loads((Path(__file__).resolve().parent.parent / "data" / "mock_metrics.json")
                      .read_text(encoding="utf-8"))
    assert TOPOLOGY == mock["topology"]


def test_empty_state_gives_safe_defaults():
    state = _state()
    assert metrics_payload(state) == {"timestamp": None, "links": []}
    route = route_payload(state)
    assert route["path"] == PATH_NODES["A"] and route["cost"] is None
    assert events_payload(state) == []
    assert mode_payload(state) == {"mode": "adaptive"}


def test_existing_data_is_passed_through():
    snap = {"timestamp": "t", "links": [{"link": "s1-s2"}]}
    route = {"timestamp": "t", "mode": "adaptive", "path": PATH_NODES["B"],
             "path_name": "B", "cost": 0.1}
    state = _state(metrics=snap, route=route, events=[{"id": 1}])
    assert metrics_payload(state) is snap
    assert route_payload(state) is route
    assert events_payload(state) == [{"id": 1}]


def test_infinity_never_reaches_json():
    text = to_json({"cost": float("inf"), "x": [float("nan"), 1.5]})
    assert json.loads(text) == {"cost": None, "x": [None, 1.5]}
    assert clean(3) == 3


def test_parse_mode_body():
    assert parse_mode_body(b'{"mode": "baseline"}') == "baseline"
    assert parse_mode_body('{"mode": "adaptive"}') == "adaptive"
    for bad in (b"", b"not json", b'{"mode": "fast"}', b'{"x": 1}', b"[1]"):
        with pytest.raises(ValueError):
            parse_mode_body(bad)