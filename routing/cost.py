"""Link cost formula.  OWNER: Zainab Fatima

C = alpha * L + beta * P + gamma * U
  L = normalized latency, P = normalized loss, U = utilization (0..1)
Each term is scaled to the range 0..1 so the weights are comparable.

Inputs follow docs/api_contract.md ("Link metrics"):
  latency_ms (RTT, ms), loss_pct (0..100), util (0..1), status (up/congested/down)

Rules
  * "down"      -> cost is infinity, so the link can never be selected.
  * "congested" -> still usable. It is NOT penalised separately: its high
                   latency, loss and utilization already raise the formula.
  * Missing latency (every probe lost) is treated as the worst value (1.0).
  * Missing loss or utilization is treated as 0.0 (no evidence of a problem).
"""
import math

DEFAULT_WEIGHTS = {"alpha": 0.4, "beta": 0.4, "gamma": 0.2}

# Normalization caps. Justification (see docs/report):
#  * Latency is the probe RTT. Healthy links in the diamond are 10 ms (Path A)
#    and 24 ms (Path B). The delay scenario adds up to ~100 ms, so a 200 ms cap
#    keeps every scenario below saturation and the measurements distinguishable.
#  * Loss: 10 percent already makes TCP unusable, so anything above it is
#    equally bad and is clipped to 1.
MAX_LATENCY_MS = 200.0
MAX_LOSS_PCT = 10.0
DOWN_COST = float("inf")  # a "down" link must never be selected


def _is_number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and not math.isnan(value))


def normalize(value, cap):
    """Scale value into 0..1 (values above cap are clipped to 1).

    None or NaN (no measurement) is treated as the worst case, 1.0.
    Negative values are clipped to 0.
    """
    if cap <= 0:
        raise ValueError("cap must be positive")
    if not _is_number(value):
        return 1.0
    return min(max(float(value) / cap, 0.0), 1.0)


def check_weights(weights):
    """Raise ValueError unless weights has non-negative alpha, beta, gamma."""
    for key in ("alpha", "beta", "gamma"):
        if key not in weights:
            raise ValueError("weights is missing '%s'" % key)
        if not _is_number(weights[key]) or weights[key] < 0:
            raise ValueError("weight '%s' must be a number >= 0" % key)


def _status(link_metrics):
    return str(link_metrics.get("status", "up")).lower()


def cost_breakdown(link_metrics, weights=DEFAULT_WEIGHTS):
    """Return every term of the cost formula for one link (for logs/dashboard).

    {"link", "status", "L", "P", "U", "latency_term", "loss_term",
     "util_term", "cost"}   (cost is DOWN_COST for a down link)
    """
    check_weights(weights)
    status = _status(link_metrics)
    latency = link_metrics.get("latency_ms")
    loss = link_metrics.get("loss_pct")
    util = link_metrics.get("util")

    L = normalize(latency, MAX_LATENCY_MS)
    P = normalize(loss if _is_number(loss) else 0.0, MAX_LOSS_PCT)
    U = normalize(util if _is_number(util) else 0.0, 1.0)

    terms = {
        "link": link_metrics.get("link"),
        "status": status,
        "L": L, "P": P, "U": U,
        "latency_term": weights["alpha"] * L,
        "loss_term": weights["beta"] * P,
        "util_term": weights["gamma"] * U,
    }
    if status == "down":
        terms["cost"] = DOWN_COST
    else:
        terms["cost"] = terms["latency_term"] + terms["loss_term"] + terms["util_term"]
    return terms


def link_cost(link_metrics, weights=DEFAULT_WEIGHTS):
    """Return the cost of one link from a link-metrics dict.

    If link_metrics["status"] == "down", return DOWN_COST.
    Otherwise C = alpha*L + beta*P + gamma*U, a float in 0..(alpha+beta+gamma).
    """
    return cost_breakdown(link_metrics, weights)["cost"]


def all_link_costs(snapshot, weights=DEFAULT_WEIGHTS):
    """Map a metrics snapshot to {"s1-s2": cost, ...}.

    snapshot is the contract object {"timestamp": ..., "links": [...]}.
    A bare list of link-metrics dicts is accepted too.
    """
    links = snapshot.get("links", []) if isinstance(snapshot, dict) else snapshot
    costs = {}
    for link in links or []:
        link_id = link.get("link")
        if link_id:
            costs[link_id] = link_cost(link, weights)
    return costs
