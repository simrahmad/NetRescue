"""Flask dashboard.  OWNER: M4"""

"""NetRescue dashboard backend (Flask, port 5000).

The browser asks THIS server for data. This server gets the data from:
  - data/mock_metrics.json   (while USE_MOCK is on, the default), or
  - the controller REST API on port 8080 (when USE_MOCK=0).

Run from the repo root:
    python dashboard/app.py                      # mock data
    USE_MOCK=0 python dashboard/app.py           # live controller
"""
import json
import os
from pathlib import Path

from flask import Flask, abort, jsonify, render_template

# Repo root is one folder above dashboard/
ROOT = Path(__file__).resolve().parent.parent
MOCK_FILE = ROOT / "data" / "mock_metrics.json"

USE_MOCK = os.environ.get("USE_MOCK", "1") == "1"
CONTROLLER_URL = os.environ.get("CONTROLLER_URL", "http://localhost:8080")

# The four things the dashboard needs. They match the keys in
# mock_metrics.json and the controller endpoints /topology, /metrics, ...
ENDPOINTS = ("topology", "metrics", "current_route", "events")

app = Flask(__name__)


def load_mock(name):
    with open(MOCK_FILE, encoding="utf-8") as f:
        return json.load(f)[name]


def load_live(name):
    import requests  # only needed in live mode

    resp = requests.get(f"{CONTROLLER_URL}/{name}", timeout=2)
    resp.raise_for_status()
    return resp.json()


@app.route("/")
def index():
    return render_template("index.html", use_mock=USE_MOCK)


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
