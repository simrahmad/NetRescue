"""Active probes.  OWNER: M3

`host` is anything with a .cmd(command) -> output method: a Mininet host
(net.get("h1")) or publisher.NamespaceHost("h1") from a separate process.
The parse_* functions need no Mininet, so they are unit-tested on fake output.
"""
import json
import re

LOSS_RE = re.compile(r"([\d.]+)% packet loss")
RTT_RE = re.compile(r"min/avg/max/mdev = [\d.]+/([\d.]+)/")


def parse_ping(output):
    """Ping summary text -> {"latency_ms": avg RTT or None, "loss_pct": 0..100}."""
    loss = LOSS_RE.search(output)
    if loss is None:                      # ping did not run at all
        return {"latency_ms": None, "loss_pct": 100.0}
    loss_pct = float(loss.group(1))
    rtt = RTT_RE.search(output)
    latency = float(rtt.group(1)) if rtt and loss_pct < 100 else None
    return {"latency_ms": latency, "loss_pct": loss_pct}


def ping_probe(host, target_ip, count=5, interval_s=0.2, tos=None):
    """Return {"latency_ms": float, "loss_pct": float}.

    If every packet is lost, loss_pct is 100 and latency_ms is None.
    tos sets the IP ToS byte (ping -Q) so the controller can pin the probe to a path.
    """
    tos_opt = " -Q %d" % tos if tos is not None else ""
    out = host.cmd("ping -q -n -c %d -i %s -W 1%s %s"
                   % (count, interval_s, tos_opt, target_ip))
    return parse_ping(out)


def parse_iperf(output):
    """iperf3 -J text -> received throughput in Mbps, or None on error."""
    try:
        data = json.loads(output)
        if "error" in data:
            return None
        return data["end"]["sum_received"]["bits_per_second"] / 1e6
    except (ValueError, KeyError):
        return None


def iperf_probe(client_host, server_ip, seconds=3):
    """Return throughput in Mbps (needs `iperf3 -s -D` running on the server host)."""
    return parse_iperf(client_host.cmd("iperf3 -c %s -t %d -J" % (server_ip, seconds)))
