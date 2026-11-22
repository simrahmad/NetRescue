"""Ryu app: cost-based adaptive routing.  OWNER: Simrah

Receives metrics snapshots (docs/api_contract.md), asks routing.engine.AdaptiveRouter
which path to use, and rewrites the two OpenFlow rules that decide the path.

Metrics input
  * Step 13 (development): set NETRESCUE_DEV_FEED=/tmp/netrescue_feed.json and write
    snapshots with controller/dev_feed.py. The file is re-read every second, like a
    real publisher would send one reading per second.
  * Step 14/15: the REST API and the monitoring publisher call handle_snapshot().

State for the REST API: get_state(). Mode switch (experiments): set_mode().

Run (from the repo root):  make adaptive      (or: make adaptive-dev)
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))      # so "routing" and "controller" can be imported

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import (CONFIG_DISPATCHER, DEAD_DISPATCHER,
                                    MAIN_DISPATCHER, set_ev_cls)
from ryu.lib import hub
from ryu.ofproto import ofproto_v1_3

from controller.flow_plan import changed_rules, plan_for, probe_rules
from routing.engine import AdaptiveRouter

ETH_TYPE_IPV4 = 0x0800
ROUTE_PRIORITY = 10
PROBE_PRIORITY = 20
FEED_INTERVAL_S = 1.0
MAX_EVENTS = 200
MODES = ("adaptive", "baseline")


class AdaptiveController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.router = AdaptiveRouter()
        self.datapaths = {}                 # switch number -> datapath
        self.mode = "adaptive"
        self.path_name = "A"                # path in use (A until told otherwise)
        self.plan = plan_for("A")
        self.latest_snapshot = None
        self.latest_route = None
        self.events = []
        self._event_id = 0
        feed = os.environ.get("NETRESCUE_DEV_FEED")
        if feed:
            self.logger.info("Dev feed enabled: reading %s every %.1f s", feed, FEED_INTERVAL_S)
            hub.spawn(self._dev_feed_loop, feed)

    # ------------------------------------------------------------------ switches
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def on_switch_features(self, ev):
        """A switch connected: remember it and install route and probe rules."""
        dp = ev.msg.datapath
        self.datapaths[dp.id] = dp
        rules = self.plan.get(dp.id, {})
        for ip, port in rules.items():
            self._send_rule(dp, ip, port)
        probes = 0
        for sw, ip, dscp, port in probe_rules():
            if sw == dp.id:
                self._send_probe_rule(dp, ip, dscp, port)
                probes += 1
        self.logger.info("s%s connected: %d route rule(s), %d probe rule(s), path %s",
                         dp.id, len(rules), probes, self.path_name)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def on_state_change(self, ev):
        if ev.state == DEAD_DISPATCHER and ev.datapath is not None:
            if self.datapaths.pop(ev.datapath.id, None) is not None:
                self.logger.info("s%s disconnected", ev.datapath.id)

    def _send_rule(self, dp, ip, port):
        """Add (or overwrite) the rule 'IPv4 to ip -> output port'."""
        ofp, parser = dp.ofproto, dp.ofproto_parser
        match = parser.OFPMatch(eth_type=ETH_TYPE_IPV4, ipv4_dst=ip)
        actions = [parser.OFPActionOutput(port)]
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        dp.send_msg(parser.OFPFlowMod(datapath=dp, priority=ROUTE_PRIORITY,
                                      match=match, instructions=inst))

    def _send_probe_rule(self, dp, ip, dscp, port):
        """Pin ICMP with this DSCP value to one output port (higher priority)."""
        ofp, parser = dp.ofproto, dp.ofproto_parser
        match = parser.OFPMatch(eth_type=ETH_TYPE_IPV4, ip_proto=1,
                                ipv4_dst=ip, ip_dscp=dscp)
        actions = [parser.OFPActionOutput(port)]
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        dp.send_msg(parser.OFPFlowMod(datapath=dp, priority=PROBE_PRIORITY,
                                      match=match, instructions=inst))    

    def _apply_path(self, path_name):
        """Rewrite only the rules that differ between the old and the new path."""
        new_plan = plan_for(path_name)
        for sw, ip, port in changed_rules(self.plan, new_plan):
            dp = self.datapaths.get(sw)
            if dp is not None:
                self._send_rule(dp, ip, port)
            self.logger.info("rule on s%s: traffic to %s -> port %s", sw, ip, port)
        self.plan = new_plan
        self.path_name = path_name

    # ------------------------------------------------------------------- routing
    def handle_snapshot(self, snapshot):
        """Process one metrics snapshot. Returns the routing decision (or None in baseline mode)."""
        self.latest_snapshot = snapshot
        if self.mode == "baseline":
            return None
        decision = self.router.decide(snapshot)
        for event in decision["events"]:
            self._add_event(event)
        if decision["path_name"] != self.path_name:
            self.logger.info("ROUTE CHANGE %s -> %s: %s", self.path_name,
                             decision["path_name"], decision["reason"])
            self._apply_path(decision["path_name"])
        self.latest_route = self.router.route_object(decision, self.mode)
        return decision

    def set_mode(self, mode):
        """Switch between 'adaptive' and 'baseline' (hop count: always Path A)."""
        if mode not in MODES:
            raise ValueError("mode must be one of %s" % (MODES,))
        self.mode = mode
        self.router.reset()                 # clean hysteresis state for every run
        if mode == "baseline":
            self._apply_path("A")
        self.latest_route = None
        self.logger.info("mode set to %s (path %s)", mode, self.path_name)

    def get_state(self):
        """Everything the REST API needs (Step 14)."""
        return {
            "mode": self.mode,
            "path_name": self.path_name,
            "route": self.latest_route,
            "metrics": self.latest_snapshot,
            "events": list(self.events),
            "route_changes": self.router.route_changes,
        }

    def _add_event(self, event):
        self._event_id += 1
        entry = dict(event)
        entry["id"] = self._event_id
        self.events.append(entry)
        del self.events[:-MAX_EVENTS]

    # ----------------------------------------------------------------- dev feed
    def _dev_feed_loop(self, path):
        """Development only: read a snapshot file once per second (see dev_feed.py)."""
        last_error = None
        while True:
            try:
                with open(path, encoding="utf-8") as f:
                    self.handle_snapshot(json.load(f))
                last_error = None
            except FileNotFoundError:
                pass
            except Exception as exc:                      # keep the loop alive
                if str(exc) != last_error:
                    self.logger.warning("dev feed error: %s", exc)
                    last_error = str(exc)
            hub.sleep(FEED_INTERVAL_S)