"""Path selection with hysteresis.  OWNER: Zainab Fatima

Unit-test this file with fake metrics BEFORE it touches Mininet
(tests/test_routing.py does exactly that).
"""
import heapq
import math

INF = float("inf")


def shortest_path(graph, src, dst):
    """Return (cost, [nodes]) for the cheapest path, or (inf, []) if none.

    graph: {node: {neighbor: cost}} as built by routing.graph.build_graph.
    Edges with infinite (or NaN) cost are treated as absent, so a failed link
    is never used. Ties are broken by node order, which makes the result
    deterministic (equal-cost paths pick the lower-numbered switch: Path A).
    """
    if src not in graph or dst not in graph:
        return INF, []
    if src == dst:
        return 0.0, [src]

    best = {src: 0.0}
    done = set()
    heap = [(0.0, [src])]            # (cost so far, path so far)
    while heap:
        cost, path = heapq.heappop(heap)
        node = path[-1]
        if node in done:
            continue
        if node == dst:
            return cost, path
        done.add(node)
        for neighbor, weight in sorted(graph[node].items()):
            if neighbor in done:
                continue
            if weight is None or math.isnan(weight) or weight == INF:
                continue
            if weight < 0:
                raise ValueError("negative link cost on %s-%s" % (node, neighbor))
            new_cost = cost + weight
            if new_cost < best.get(neighbor, INF):
                best[neighbor] = new_cost
                heapq.heappush(heap, (new_cost, path + [neighbor]))
    return INF, []


class PathSelector:
    """Chooses between paths and avoids flapping.

    Switch only if the candidate path is cheaper than the current one by at
    least `margin` (e.g. 0.20 = 20 percent) for `confirmations` readings in a row.

    Extras (defaults keep the behaviour described in the project guide):
      cooldown : readings to wait after a switch before another cost-based
                 switch is allowed (0 = off). Failure switches ignore it.
      default  : path used before the first reading, if every path is unusable.
    """

    def __init__(self, margin=0.20, confirmations=3, cooldown=0, default="A"):
        if not 0 <= margin < 1:
            raise ValueError("margin must be in [0, 1)")
        if confirmations < 1:
            raise ValueError("confirmations must be >= 1")
        if cooldown < 0:
            raise ValueError("cooldown must be >= 0")
        self.margin = margin
        self.confirmations = confirmations
        self.cooldown = cooldown
        self.default = default
        self.current = None      # "A" or "B"
        self.switches = 0        # number of path changes (routing overhead)
        self._streak = 0
        self._candidate = None
        self._since_switch = cooldown

    def reset(self):
        """Forget all state (call between experiment runs)."""
        self.current = None
        self.switches = 0
        self._streak = 0
        self._candidate = None
        self._since_switch = self.cooldown

    @staticmethod
    def _usable(path_costs):
        return {name: cost for name, cost in path_costs.items()
                if cost is not None and not math.isnan(cost) and cost < INF}

    def _switch_to(self, name):
        self.current = name
        self.switches += 1
        self._streak = 0
        self._candidate = None
        self._since_switch = 0

    def update(self, path_costs):
        """path_costs: {"A": 0.88, "B": 0.41}. Return the path name to use.

        * First call: pick the cheapest usable path (ties -> alphabetical).
        * Current path down (infinite cost): switch immediately to the
          cheapest usable path (no margin, no confirmations, no cooldown).
        * Otherwise switch only when another path is at least `margin`
          cheaper for `confirmations` consecutive readings.
        * If no path is usable, keep the current one.
        """
        usable = self._usable(path_costs)
        self._since_switch += 1

        if self.current is None:
            if usable:
                self.current = min(usable, key=lambda n: (usable[n], n))
            else:
                self.current = self.default
            return self.current

        if not usable:
            return self.current

        best = min(usable, key=lambda n: (usable[n], n))

        if self.current not in usable:            # current path failed
            self._switch_to(best)
            return self.current

        current_cost = usable[self.current]
        better = best != self.current and usable[best] < current_cost * (1 - self.margin)
        if not better or self._since_switch <= self.cooldown:
            self._streak = 0
            self._candidate = None
            return self.current

        if best == self._candidate:
            self._streak += 1
        else:
            self._candidate, self._streak = best, 1
        if self._streak >= self.confirmations:
            self._switch_to(best)
        return self.current
