"""REST API on port 8080 serving the endpoints in docs/api_contract.md.  OWNER: Simrah

Runs inside the Ryu controller process (Ryu's built-in web server), so it reads the
controller state directly. The response contents are built in api_payloads.py.

  GET  /topology        nodes and links
  GET  /metrics         latest metrics snapshot
  GET  /current_route   path in use and its cost
  GET  /events          route changes and alerts, newest last
  GET  /mode            {"mode": "adaptive"}
  POST /mode            body {"mode": "baseline"} or {"mode": "adaptive"}
"""
from ryu.app.wsgi import ControllerBase, route
from webob import Response

from controller.api_payloads import (events_payload, metrics_payload, mode_payload,
                                     parse_mode_body, route_payload, to_json,
                                     topology_payload)

API_NAME = "netrescue_api"


def json_response(payload, status=200):
    return Response(status=status, content_type="application/json",
                    body=to_json(payload).encode("utf-8"))


class NetRescueApi(ControllerBase):
    def __init__(self, req, link, data, **config):
        super().__init__(req, link, data, **config)
        self.app = data["app"]          # the AdaptiveController

    @route(API_NAME, "/topology", methods=["GET"])
    def get_topology(self, req, **kwargs):
        return json_response(topology_payload())

    @route(API_NAME, "/metrics", methods=["GET"])
    def get_metrics(self, req, **kwargs):
        return json_response(metrics_payload(self.app.get_state()))

    @route(API_NAME, "/current_route", methods=["GET"])
    def get_current_route(self, req, **kwargs):
        return json_response(route_payload(self.app.get_state()))

    @route(API_NAME, "/events", methods=["GET"])
    def get_events(self, req, **kwargs):
        return json_response(events_payload(self.app.get_state()))

    @route(API_NAME, "/mode", methods=["GET"])
    def get_mode(self, req, **kwargs):
        return json_response(mode_payload(self.app.get_state()))

    @route(API_NAME, "/mode", methods=["POST"])
    def post_mode(self, req, **kwargs):
        try:
            mode = parse_mode_body(req.body)
        except ValueError as exc:
            return json_response({"error": str(exc)}, status=400)
        self.app.set_mode(mode)
        return json_response(mode_payload(self.app.get_state()))