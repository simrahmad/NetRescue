"""Path selection with hysteresis.  OWNER: Zainab Fatima

Unit-test this file with fake metrics BEFORE it touches Mininet.
"""
import heapq  # noqa: F401  (use for the priority queue)


def shortest_path(graph, src, dst):
    """Return (cost, [nodes]) for the cheapest path, or (inf, []) if none.  TODO."""
    raise NotImplementedError


class PathSelector:
    """Chooses between paths and avoids flapping.

    Switch only if the candidate path is cheaper than the current one by at
    least `margin` (e.g. 0.20 = 20 percent) for `confirmations` readings in a row.
    """

    def __init__(self, margin=0.20, confirmations=3):
        self.margin = margin
        self.confirmations = confirmations
        self.current = None      # "A" or "B"
        self._streak = 0

    def update(self, path_costs):
        """path_costs: {"A": 0.88, "B": 0.41}. Return the path name to use.

        TODO: if the current path is down (inf cost) switch immediately,
        otherwise apply the margin and confirmation rule.
        """
        raise NotImplementedError