"""Graph model for NetRescue.  OWNER: Zainab Fatima

Input:  link costs {"s1-s2": 0.35, ...} (from routing/cost.py)
Output: graph used by dijkstra.py, and per-path costs for the PathSelector
"""
import re

INF = float("inf")

# The four routed core links. Host links are not routed.
CORE_LINKS = ["s1-s2", "s1-s3", "s2-s4", "s3-s4"]

# The two possible paths between s1 and s4.
PATHS = {
    "A": ["s1", "s2", "s4"],
    "B": ["s1", "s3", "s4"],
}

# Hosts at the two ends of every route (used to build the full h1..h2 path).
SRC_HOST, DST_HOST = "h1", "h2"
SRC_SWITCH, DST_SWITCH = "s1", "s4"


def _switch_number(name):
    match = re.search(r"(\d+)$", name)
    return int(match.group(1)) if match else None


def link_id(a, b):
    """Return the canonical link id for two nodes: lower-numbered switch first.

    link_id("s4", "s2") -> "s2-s4"
    """
    na, nb = _switch_number(a), _switch_number(b)
    if na is not None and nb is not None:
        first, second = (a, b) if na <= nb else (b, a)
    else:
        first, second = sorted((a, b))
    return "%s-%s" % (first, second)


def _split_link(link):
    parts = link.split("-")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("bad link id %r (expected like 's1-s2')" % (link,))
    return parts[0], parts[1]


def build_graph(link_costs):
    """Return an adjacency dict {node: {neighbor: cost}}.

    link_costs: {"s1-s2": 0.35, "s1-s3": 0.20, ...}
    Every link is added in both directions. Links with infinite cost (down)
    stay in the graph; dijkstra.shortest_path ignores them.
    """
    graph = {}
    for link, cost in link_costs.items():
        a, b = _split_link(link)
        graph.setdefault(a, {})[b] = cost
        graph.setdefault(b, {})[a] = cost
    return graph


def path_links(path):
    """Return link ids along a node path. ["s1","s2","s4"] -> ["s1-s2","s2-s4"].

    The id format is lower-numbered switch first, so a reversed path gives the
    same ids: ["s4","s2","s1"] -> ["s2-s4","s1-s2"].
    """
    return [link_id(a, b) for a, b in zip(path, path[1:])]


def path_cost(link_costs, path):
    """Sum of link costs along a node path. A missing link counts as infinity
    (no measurement yet means the link cannot be trusted)."""
    total = 0.0
    for link in path_links(path):
        total += link_costs.get(link, INF)
    return total


def all_path_costs(link_costs, paths=None):
    """Return {"A": cost, "B": cost} for the named paths (default PATHS)."""
    paths = PATHS if paths is None else paths
    return {name: path_cost(link_costs, nodes) for name, nodes in paths.items()}


def full_route(path_name):
    """Host-to-host node list for a named path: "B" -> [h1, s1, s3, s4, h2]."""
    return [SRC_HOST] + list(PATHS[path_name]) + [DST_HOST]


def path_name_of(nodes):
    """Return "A"/"B" for a switch node list (e.g. from Dijkstra), else None."""
    nodes = list(nodes)
    for name, switches in PATHS.items():
        if nodes == switches:
            return name
    return None
