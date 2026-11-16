"""Automated experiment runner.  OWNER: M5

Run each scenario at least 5 times in each mode under identical conditions.
Results: one CSV row per run in experiments/results/ (columns in docs/api_contract.md).
"""
import csv  # noqa: F401

SCENARIOS = ["delay", "loss", "bandwidth", "link_fail"]
MODES = ["baseline", "adaptive"]
REPEATS = 5
RESULT_COLUMNS = [
    "run_id", "scenario", "mode", "repeat", "recovery_time_s",
    "packets_lost", "avg_latency_ms", "throughput_mbps", "route_changes",
]


def run_once(scenario, mode, repeat):
    """Run one experiment and return a dict with RESULT_COLUMNS keys.

    TODO: 1) set controller mode (POST /mode), 2) start ping and iperf3 traffic,
    3) apply the scenario script from topology/scenarios/, 4) measure recovery time
    and packet loss, 5) clear the scenario, 6) wait for the network to settle.
    """
    raise NotImplementedError


def main():
    """Loop over SCENARIOS x MODES x REPEATS and append rows to a CSV.  TODO."""
    raise NotImplementedError


if __name__ == "__main__":
    main()