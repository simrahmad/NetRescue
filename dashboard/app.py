"""NetRescue dashboard backend (Flask, port 5000).

The browser asks THIS server for data. This server gets the data from:
  - data/mock_metrics.json   (while USE_MOCK is on, the default), or
  - the controller REST API on port 8080 (when USE_MOCK=0).

Run from the repo root:
    python dashboard/app.py                      # mock data
    USE_MOCK=0 python dashboard/app.py           # live controller
"""
import copy
import csv
import json
import os
import random
import statistics
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, jsonify, render_template

# Repo root is one folder above dashboard/
ROOT = Path(__file__).resolve().parent.parent
MOCK_FILE = ROOT / "data" / "mock_metrics.json"

USE_MOCK = os.environ.get("USE_MOCK", "1") == "1"
CONTROLLER_URL = os.environ.get("CONTROLLER_URL", "http://localhost:8080")
# In mock mode, add small random changes to the metrics so the live charts move.
# Turn off with MOCK_JITTER=0 to get exactly the numbers in mock_metrics.json.
MOCK_JITTER = os.environ.get("MOCK_JITTER", "1") == "1"

# Experiment results (written by Member 5). If no CSV files exist yet, the
# comparison page falls back to the sample file next to this script.
RESULTS_DIR = ROOT / "experiments" / "results"
SAMPLE_RESULTS = Path(__file__).resolve().parent / "sample_results.csv"
METRIC_FIELDS = ("recovery_time_s", "packets_lost", "avg_latency_ms",
                 "throughput_mbps", "route_changes")

# The four things the dashboard needs. They match the keys in
# mock_metrics.json and the controller endpoints /topology, /metrics, ...
ENDPOINTS = ("topology", "metrics", "current_route", "events")

app = Flask(__name__)


def add_jitter(metrics):
    """Return a copy of the metrics snapshot with small random changes."""
    metrics = copy.deepcopy(metrics)
    metrics["timestamp"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for link in metrics["links"]:
        link["latency_ms"] = round(max(0.1, link["latency_ms"] * random.uniform(0.9, 1.1)), 1)
        link["loss_pct"] = round(min(100.0, max(0.0, link["loss_pct"] * random.uniform(0.8, 1.2))), 2)
        link["util"] = round(min(1.0, max(0.0, link["util"] + random.uniform(-0.03, 0.03))), 2)
        link["throughput_mbps"] = round(link["util"] * link["capacity_mbps"], 1)
    return metrics


def load_mock(name):
    with open(MOCK_FILE, encoding="utf-8") as f:
        data = json.load(f)[name]
    if name == "metrics" and MOCK_JITTER:
        data = add_jitter(data)
    return data


def load_live(name):
    import requests  # only needed in live mode

    resp = requests.get(f"{CONTROLLER_URL}/{name}", timeout=2)
    resp.raise_for_status()
    return resp.json()


def read_result_rows():
    """Return (rows, is_sample). Reads every CSV in experiments/results/."""
    files = sorted(RESULTS_DIR.glob("*.csv")) if RESULTS_DIR.is_dir() else []
    is_sample = not files
    if is_sample:
        files = [SAMPLE_RESULTS]
    rows = []
    for path in files:
        with open(path, newline="", encoding="utf-8") as f:
            rows.extend(csv.DictReader(f))
    return rows, is_sample


def summarize(rows):
    """Group runs by (scenario, mode) and compute mean and standard deviation."""
    groups = {}
    for row in rows:
        scenario, mode = row.get("scenario"), row.get("mode")
        if scenario and mode:
            groups.setdefault((scenario, mode), []).append(row)

    summary = []
    for (scenario, mode), items in groups.items():
        entry = {"scenario": scenario, "mode": mode, "n": len(items)}
        for field in METRIC_FIELDS:
            values = []
            for item in items:
                try:
                    values.append(float(item[field]))
                except (KeyError, TypeError, ValueError):
                    pass  # skip empty or broken cells
            if values:
                sd = statistics.stdev(values) if len(values) > 1 else 0.0
                entry[field] = {"mean": round(statistics.mean(values), 3), "sd": round(sd, 3)}
            else:
                entry[field] = {"mean": None, "sd": None}
        summary.append(entry)
    return summary


@app.route("/")
def index():
    return render_template("index.html", use_mock=USE_MOCK)


@app.route("/comparison")
def comparison():
    return render_template("comparison.html")


@app.route("/api/results")
def api_results():
    try:
        rows, is_sample = read_result_rows()
        return jsonify({"sample": is_sample, "summary": summarize(rows)})
    except Exception as err:  # missing sample file, bad CSV
        return jsonify({"error": str(err)}), 500


@app.route("/api/<name>")
def api(name):
    if name not in ENDPOINTS:
        abort(404)
    try:
        data = load_mock(name) if USE_MOCK else load_live(name)
    except Exception as err:  # controller down, file missing, bad JSON
        return jsonify({"error": str(err)}), 502
    return jsonify(data)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)