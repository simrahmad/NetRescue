"""Ryu app: hop-count shortest-path routing (the BASELINE).  OWNER: Simrah

Routes IPv4 traffic by fewest hops. Both paths in the diamond have 2 hops, so
ties are broken by the lowest switch number: the baseline always uses Path A
(h1 - s1 - s2 - s4 - h2) and never reacts to congestion, loss, or delay.

Run:  make controller      (then start the network with: make topo)
"""
from collections import deque

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3

# Static lab topology, kept in sync with docs/architecture.md
SWITCHES = [1, 2, 3, 4]
SWITCH_PORTS = {            # (switch, neighbor switch) -> port on that switch
    (1, 2): 2, (1, 3): 3,
    (2, 1): 1, (2, 4): 2,
    (3, 1): 1, (3, 4): 2,
    (4, 2): 1, (4, 3): 2,
}
HOSTS = {                   # host IP -> (attached switch, port)
    "10.0.0.1": (1, 1),     # h1
    "10.0.0.2": (4, 3),     # h2
}
ETH_TYPE_IPV4 = 0x0800
ROUTE_PRIORITY = 10


def neighbors(sw):
    """Neighbor switches of sw, lowest number first (this is the tie-break)."""
    return sorted(n for (s, n) in SWITCH_PORTS if s == sw)


def hop_distances(target):
    """Breadth-first search: hop count from every switch to the target switch."""
    dist = {target: 0}
    queue = deque([target])
    while queue:
        sw = queue.popleft()
        for nb in neighbors(sw):
            if nb not in dist:
                dist[nb] = dist[sw] + 1
                queue.append(nb)
    return dist


def build_flow_table():
    """Return {switch: {host_ip: output_port}} using hop-count shortest paths."""
    table = {sw: {} for sw in SWITCHES}
    for ip, (dst_sw, host_port) in HOSTS.items():
        dist = hop_distances(dst_sw)
        for sw in SWITCHES:
            if sw == dst_sw:
                table[sw][ip] = host_port
                continue
            next_hop = min(n for n in neighbors(sw) if dist[n] == dist[sw] - 1)
            table[sw][ip] = SWITCH_PORTS[(sw, next_hop)]
    return table


class BaselineController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.flow_table = build_flow_table()
        self.logger.info("Baseline routes (hop count): %s", self.flow_table)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def on_switch_features(self, ev):
        """A switch connected: install its routes."""
        self._install_routes(ev.msg.datapath)

    def _install_routes(self, dp):
        ofp = dp.ofproto
        parser = dp.ofproto_parser
        routes = self.flow_table.get(dp.id, {})
        for ip, port in routes.items():
            match = parser.OFPMatch(eth_type=ETH_TYPE_IPV4, ipv4_dst=ip)
            actions = [parser.OFPActionOutput(port)]
            inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
            dp.send_msg(parser.OFPFlowMod(
                datapath=dp, priority=ROUTE_PRIORITY, match=match, instructions=inst))
        self.logger.info("s%s connected: installed %d route(s)", dp.id, len(routes))