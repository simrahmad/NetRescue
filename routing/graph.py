"""Graph model for NetRescue.  OWNER: Zainab Fatima

Input:  list of link-metrics dicts (see docs/api_contract.md)
Output: graph used by dijkstra.py
"""

# The four routed core links. Host links are not routed.
CORE_LINKS = ["s1-s2", "s1-s3", "s2-s4", "s3-s4"]

# The two possible paths between s1 and s4.
PATHS = {
    "A": ["s1", "s2", "s4"],
    "B": ["s1", "s3", "s4"],
}


def build_graph(link_costs):
    """Return an adjacency dict {node: {neighbor: cost}}.

    link_costs: {"s1-s2": 0.35, "s1-s3": 0.20, ...}
    TODO: split each link id on "-" and add both directions.
    """
    raise NotImplementedError


def path_links(path):
    """Return link ids along a node path. ["s1","s2","s4"] -> ["s1-s2","s2-s4"].

    TODO: remember the id format is lower-numbered switch first.
    """
    raise NotImplementedError