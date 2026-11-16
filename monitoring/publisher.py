"""Builds and publishes metrics snapshots.  OWNER: M3

Output format: docs/api_contract.md ("Metrics snapshot").
"""

PUBLISH_INTERVAL_S = 1.5
SMOOTHING_WINDOW = 3          # moving average over the last N readings
DOWN_AFTER_MISSED_PROBES = 3  # mark "down" after N missed probes in a row
CONGESTED_UTIL = 0.8          # TODO: agree thresholds with Zainab
CONGESTED_LOSS_PCT = 2.0


def moving_average(values, window=SMOOTHING_WINDOW):
    """Return the average of the last `window` values.  TODO."""
    raise NotImplementedError


def classify_status(latency_ms, loss_pct, util, missed_probes):
    """Return "up", "congested", or "down". Keep congestion and failure separate.  TODO."""
    raise NotImplementedError


def build_snapshot():
    """Collect all four core links and return the snapshot dict.  TODO."""
    raise NotImplementedError


def run_forever():
    """Every PUBLISH_INTERVAL_S seconds call build_snapshot() and hand it
    to the controller (agree the mechanism with Simrah: shared object or POST).  TODO."""
    raise NotImplementedError