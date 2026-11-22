"""One-call adaptive routing decision.  OWNER: Zainab Fatima

This is the single entry point Simrah's adaptive controller needs:

    from routing.engine import AdaptiveRouter
    router = AdaptiveRouter()
    decision = router.decide(snapshot)     # snapshot = metrics snapshot (contract)
    if decision["changed"]:
        ...reinstall OpenFlow rules for decision["path_name"] ...

It chains: metrics snapshot -> link costs (cost.py) -> graph (graph.py)
-> Dijkstra (dijkstra.py) -> hysteresis (PathSelector).

Everything returned is JSON-safe: an unusable (down) path or link has cost None.
Pure Python, no Ryu or Mininet imports, so it can be unit-tested anywhere.
"""
from datetime import datetime, timezone

from .cost import DEFAULT_WEIGHTS, all_link_costs, check_weights, cost_breakdown
from .dijkstra import INF, PathSelector, shortest_path
from .graph import (CORE_LINKS, DST_SWITCH, PATHS, SRC_SWITCH, all_path_costs,
                    build_graph, full_route, path_links, path_name_of)


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_cost(value):
    return None if value is None or value == INF else round(value, 4)


class AdaptiveRouter:
    """Stateful router: keeps the hysteresis state between readings."""

    def __init__(self, weights=None, margin=0.20, confirmations=3, cooldown=0):
        self.weights = dict(DEFAULT_WEIGHTS if weights is None else weights)
        check_weights(self.weights)
        self.selector = PathSelector(margin=margin, confirmations=confirmations,
                                     cooldown=cooldown)
        self._last_status = {}

    # -- state --------------------------------------------------------------
    @property
    def current(self):
        """Name of the path currently in use ("A"/"B") or None before the first reading."""
        return self.selector.current

    @property
    def route_changes(self):
        """Number of path switches so far (routing overhead metric)."""
        return self.selector.switches

    def reset(self):
        """Forget all state (call between experiment runs)."""
        self.selector.reset()
        self._last_status = {}

    # -- main entry point ---------------------------------------------------
    def decide(self, snapshot, now=None):
        """Process one metrics snapshot and return a decision dict:

        path_name   "A" or "B", the path traffic should use now
        path        ["h1", "s1", "s3", "s4", "h2"]
        cost        cost of that path (None if unusable)
        changed     True if path_name differs from the previous decision
        from_path   previous path name (None on the very first decision)
        reason      human-readable text for the events log
        best_path   Dijkstra's cheapest path name, ignoring hysteresis
        path_costs  {"A": 0.88, "B": 0.41}   (None = unusable)
        link_costs  {"s1-s2": 0.64, ...}     (None = down)
        events      [{"type", "from_path", "to_path", "reason", "timestamp"}]
                    link_down / link_up / congestion / route_change; the
                    controller adds the running "id".
        timestamp   ISO 8601 UTC
        """
        timestamp = now or (snapshot.get("timestamp") if isinstance(snapshot, dict) else None) \
            or _utc_now()
        links = snapshot.get("links", []) if isinstance(snapshot, dict) else snapshot
        by_id = {l.get("link"): l for l in links or [] if l.get("link")}

        raw_costs = {k: v for k, v in all_link_costs(links, self.weights).items()
                     if k in CORE_LINKS}
        graph = build_graph(raw_costs)
        d_cost, d_nodes = shortest_path(graph, SRC_SWITCH, DST_SWITCH)
        best_path = path_name_of(d_nodes)

        raw_path_costs = all_path_costs(raw_costs)
        previous = self.selector.current
        chosen = self.selector.update(raw_path_costs)
        changed = previous is not None and chosen != previous

        events = self._link_events(by_id, chosen, timestamp)
        if previous is None:
            reason = "initial route, lowest cost"
        elif changed:
            reason = self._change_reason(previous, chosen, raw_path_costs, by_id)
        else:
            reason = "keeping path %s" % chosen
        if previous is None or changed:
            events.append({"type": "route_change", "from_path": previous,
                           "to_path": chosen, "reason": reason, "timestamp": timestamp})

        return {
            "timestamp": timestamp,
            "path_name": chosen,
            "path": full_route(chosen),
            "cost": _json_cost(raw_path_costs.get(chosen)),
            "changed": changed,
            "from_path": previous,
            "reason": reason,
            "best_path": best_path,
            "path_costs": {k: _json_cost(v) for k, v in raw_path_costs.items()},
            "link_costs": {k: _json_cost(v) for k, v in raw_costs.items()},
            "events": events,
        }

    # -- helpers ------------------------------------------------------------
    def route_object(self, decision, mode="adaptive"):
        """Format a decision as the 'Route' object from docs/api_contract.md."""
        return {"timestamp": decision["timestamp"], "mode": mode,
                "path": decision["path"], "path_name": decision["path_name"],
                "cost": decision["cost"]}

    def _worst_link(self, path_name, by_id):
        """Link on a path contributing the most cost, with a readable summary."""
        worst, worst_cost = None, -1.0
        for link in path_links(PATHS[path_name]):
            metrics = by_id.get(link)
            if metrics is None:
                continue
            cost = cost_breakdown(metrics, self.weights)["cost"]
            cost = 1e9 if cost == INF else cost
            if cost > worst_cost:
                worst, worst_cost = link, cost
        if worst is None:
            return ""
        m = by_id[worst]
        if str(m.get("status", "")).lower() == "down":
            return "link %s is down" % worst
        parts = []
        if m.get("loss_pct") is not None:
            parts.append("loss %.1f percent" % m["loss_pct"])
        if m.get("util") is not None:
            parts.append("utilization %.2f" % m["util"])
        if m.get("latency_ms") is not None:
            parts.append("latency %.0f ms" % m["latency_ms"])
        return "%s on %s" % (", ".join(parts), worst)

    def _change_reason(self, old, new, path_costs, by_id):
        if path_costs.get(old, INF) == INF:
            return "path %s unavailable (%s); switched to path %s" % (
                old, self._worst_link(old, by_id) or "no data", new)
        return "path %s cost %.2f is above path %s cost %.2f (%s)" % (
            old, path_costs[old], new, path_costs[new],
            self._worst_link(old, by_id) or "no detail")

    def _link_events(self, by_id, current_path, timestamp):
        """Status transitions per link -> link_down / link_up / congestion."""
        events = []
        for link in CORE_LINKS:
            metrics = by_id.get(link)
            if metrics is None:
                continue
            status = str(metrics.get("status", "up")).lower()
            old = self._last_status.get(link)
            self._last_status[link] = status
            if old is None or old == status:
                continue
            if status == "down":
                kind, text = "link_down", "link %s went down" % link
            elif old == "down":
                kind, text = "link_up", "link %s is back (%s)" % (link, status)
            elif status == "congested":
                kind = "congestion"
                text = "utilization %.2f and loss %.1f percent on %s" % (
                    metrics.get("util") or 0.0, metrics.get("loss_pct") or 0.0, link)
            else:
                continue            # congested -> up is not worth an event
            events.append({"type": kind, "from_path": current_path,
                           "to_path": current_path, "reason": text,
                           "timestamp": timestamp})
        return events
