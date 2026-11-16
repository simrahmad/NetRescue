"""Link cost formula.  OWNER: Zainab Fatima

C = alpha * L + beta * P + gamma * U
  L = normalized latency, P = normalized loss, U = utilization (0..1)
Each term must be scaled to the range 0..1 so the weights are comparable.
"""

DEFAULT_WEIGHTS = {"alpha": 0.4, "beta": 0.4, "gamma": 0.2}  # TODO: tune in experiments
MAX_LATENCY_MS = 200.0   # TODO: choose a justified cap for normalization
MAX_LOSS_PCT = 10.0      # TODO: choose a justified cap for normalization
DOWN_COST = float("inf")  # a "down" link must never be selected


def normalize(value, cap):
    """Scale value into 0..1 (values above cap are clipped to 1).  TODO."""
    raise NotImplementedError


def link_cost(link_metrics, weights=DEFAULT_WEIGHTS):
    """Return the cost of one link from a link-metrics dict.

    If link_metrics["status"] == "down", return DOWN_COST.
    TODO: apply the formula and return a float.
    """
    raise NotImplementedError


def all_link_costs(snapshot, weights=DEFAULT_WEIGHTS):
    """Map a metrics snapshot to {"s1-s2": cost, ...}.  TODO."""
    raise NotImplementedError