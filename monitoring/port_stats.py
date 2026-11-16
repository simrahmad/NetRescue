"""Link utilization from OpenFlow port counters.  OWNER: M3"""


def compute_utilization(prev_bytes, curr_bytes, interval_s, capacity_mbps):
    """Return utilization as a fraction 0.0..1.0.

    util = ((curr_bytes - prev_bytes) * 8 / interval_s / 1e6) / capacity_mbps
    TODO: clip to 0..1 and handle counter resets (curr < prev).
    """
    raise NotImplementedError


def request_port_stats(datapath):
    """Ask a switch for port statistics (call from the Ryu controller).

    TODO: send an OFPPortStatsRequest and handle the reply event.
    Coordinate with Simrah, who owns the Ryu app.
    """
    raise NotImplementedError