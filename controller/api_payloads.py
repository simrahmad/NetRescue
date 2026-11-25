"""Pure response builders for the REST API.  OWNER: Simrah

No Ryu or web imports, so everything here can be tested anywhere.
The formats follow docs/api_contract.md. Input is the dict returned by
AdaptiveController.get_state().
"""
import json
import math

MODES = ("adaptive", "baseline")

TOPOLOGY = {
    "nodes": [
        {"id": "h1", "type": "host"},
        {"id": "h2", "type": "host"},
        {"id": "s1", "type": "switch"},
        {"id": "s2", "type": "switch"},
        {"id": "s3", "type": "switch"},
        {"id": "s4", "type": "switch"},
    ],
    "links": [
        {"id": "h1-s1", "routed": False},
        {"id": "s1-s2", "routed": True},
        {"id": "s1-s3", "routed": True},
        {"id": "s2-s4", "routed": True},
        {"id": "s3-s4", "routed": True},
        {"id": "s4-h2", "routed": False},
    ],
}

PATH_NODES = {
    "A": ["h1", "s1", "s2", "s4", "h2"],
    "B": ["h1", "s1", "s3", "s4", "h2"],
}


def clean(value):
    """Make a value safe for JSON: infinity and NaN become None (null)."""
    if isinstance(value, float) and (math.isinf(value) or math.isnan(value)):
        return None
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    return value


def to_json(payload):
    """Serialize to strict JSON text (never 'Infinity' or 'NaN')."""
    return json.dumps(clean(payload), allow_nan=False)


def topology_payload():
    return TOPOLOGY


def metrics_payload(state):
    """Latest metrics snapshot, or an empty one before any data arrived."""
    return state["metrics"] or {"timestamp": None, "links": []}


def route_payload(state):
    """Current route object; a default one (Path A, no cost yet) before any data."""
    if state["route"]:
        return state["route"]
    name = state["path_name"]
    return {"timestamp": None, "mode": state["mode"],
            "path": PATH_NODES[name], "path_name": name, "cost": None}


def events_payload(state):
    """List of events, newest last."""
    return state["events"]


def mode_payload(state):
    return {"mode": state["mode"]}


def parse_mode_body(raw):
    """Read the mode from a POST body like {"mode": "baseline"}.

    Raises ValueError with a readable message for anything invalid.
    """
    try:
        body = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except (ValueError, UnicodeDecodeError):
        raise ValueError("body must be JSON like {\"mode\": \"baseline\"}")
    if not isinstance(body, dict) or body.get("mode") not in MODES:
        raise ValueError("mode must be one of: %s" % ", ".join(MODES))
    return body["mode"]