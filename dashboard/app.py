"""Flask dashboard.  OWNER: M4

Phase 1: read data/mock_metrics.json (works on any OS, no Mininet needed).
Phase 2: call the controller API at http://localhost:8080 (see docs/api_contract.md).
"""
import json
from pathlib import Path

from flask import Flask, jsonify, render_template

app = Flask(__name__)
MOCK_FILE = Path(__file__).resolve().parent.parent / "data" / "mock_metrics.json"
USE_MOCK = True  # TODO: switch to False when the real API is ready


def load_mock():
    with open(MOCK_FILE, encoding="utf-8") as f:
        return json.load(f)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/<name>")
def api(name):
    """Serve topology, metrics, current_route, or events to the page's JavaScript.

    TODO: if USE_MOCK return load_mock()[name], otherwise fetch from the controller
    with requests.get(f"http://localhost:8080/{name}"). Return 404 for unknown names.
    """
    return jsonify({"todo": name})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)