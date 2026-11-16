"""Active probes.  OWNER: M3

Run from inside Mininet hosts (e.g. net.get("h1").cmd("ping ...")).
"""


def ping_probe(host, target_ip, count=5):
    """Return {"latency_ms": float, "loss_pct": float}.

    TODO: run `ping -c <count> <target_ip>`, parse the "rtt min/avg/max" line
    for the average and the "packet loss" percentage. If every packet is lost,
    return loss_pct 100 and latency_ms None.
    """
    raise NotImplementedError


def iperf_probe(client_host, server_ip, seconds=3):
    """Return throughput in Mbps.

    TODO: run `iperf3 -c <server_ip> -t <seconds> -J` and read the JSON result.
    """
    raise NotImplementedError