"""Link utilization from port byte counters.  OWNER: M3

Each core link is measured on the switch interface that carries the h1 -> h2
direction (the same interfaces the scenario scripts impair, docs/architecture.md).
"""

DATA_IFACE = {"s1-s2": "s1-eth2", "s1-s3": "s1-eth3",
              "s2-s4": "s2-eth2", "s3-s4": "s3-eth2"}
DATA_PORT = {(1, 2): "s1-s2", (1, 3): "s1-s3",       # (dpid, OpenFlow port) -> link
             (2, 2): "s2-s4", (3, 2): "s3-s4"}
CAPACITY_MBPS = {"s1-s2": 10, "s2-s4": 10, "s1-s3": 5, "s3-s4": 5}  # topology/diamond_topo.py
DOWN_STATES = ("down", "lowerlayerdown", "notpresent")


def throughput_mbps(prev_bytes, curr_bytes, interval_s):
    """Mbps sent between two counter readings. A counter reset (curr < prev) gives 0."""
    if interval_s <= 0 or curr_bytes < prev_bytes:
        return 0.0
    return (curr_bytes - prev_bytes) * 8 / interval_s / 1e6


def compute_utilization(prev_bytes, curr_bytes, interval_s, capacity_mbps):
    """Return utilization as a fraction 0.0..1.0."""
    if capacity_mbps <= 0:
        return 0.0
    util = throughput_mbps(prev_bytes, curr_bytes, interval_s) / capacity_mbps
    return min(max(util, 0.0), 1.0)


def read_tx_bytes(iface):
    """Transmit byte counter of a switch interface (Mininet switches are in the root namespace)."""
    with open("/sys/class/net/%s/statistics/tx_bytes" % iface) as f:
        return int(f.read())


def iface_is_down(iface):
    """True if the interface is down (e.g. after topology/scenarios/link_fail.sh down)."""
    try:
        with open("/sys/class/net/%s/operstate" % iface) as f:
            return f.read().strip() in DOWN_STATES
    except OSError:
        return True


def request_port_stats(datapath):
    """Ask a switch for port statistics (call from the Ryu controller).

    The reply arrives as ofp_event.EventOFPPortStatsReply; pass
    ev.msg.datapath.id and ev.msg.body to tx_bytes_from_reply().
    """
    parser = datapath.ofproto_parser
    datapath.send_msg(parser.OFPPortStatsRequest(datapath, 0, datapath.ofproto.OFPP_ANY))


def tx_bytes_from_reply(dpid, body):
    """Port stats reply body -> {link: tx_bytes} for the core links on that switch."""
    return {DATA_PORT[(dpid, s.port_no)]: s.tx_bytes
            for s in body if (dpid, s.port_no) in DATA_PORT}
