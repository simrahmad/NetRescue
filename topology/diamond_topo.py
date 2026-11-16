#!/usr/bin/env python3
"""Baseline Mininet topology for NetRescue.  OWNER: Simrah (extended by Zainab)

    h1 -- s1 -- s2 -- s4 -- h2     Path A: 10 Mbps, 5 ms per link
           \\         /
            -- s3 --              Path B:  5 Mbps, 12 ms per link

Port map (fixed by the order of addLink calls below):
  s1: 1=h1  2=s2  3=s3        s2: 1=s1  2=s4
  s4: 1=s2  2=s3  3=h2        s3: 1=s1  2=s4

Usage (on the Ubuntu VM):  sudo venv/bin/python topology/diamond_topo.py
Other code can import build_net() to create the same network.
"""
import argparse

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.net import Mininet
from mininet.node import OVSKernelSwitch, RemoteController

PATH_A = dict(bw=10, delay="5ms")
PATH_B = dict(bw=5, delay="12ms")
EDGE = dict(bw=100)  # host links: fast, no extra delay


def build_net(controller_ip="127.0.0.1", controller_port=6653):
    """Create (but do not start) the diamond network and return it."""
    net = Mininet(
        controller=None,
        switch=OVSKernelSwitch,
        link=TCLink,
        autoSetMacs=True,     # h1 = 00:00:00:00:00:01, h2 = 00:00:00:00:00:02
        autoStaticArp=True,   # no ARP broadcasts in a network with a loop
    )
    net.addController("c0", controller=RemoteController,
                      ip=controller_ip, port=controller_port)

    h1 = net.addHost("h1", ip="10.0.0.1/24")
    h2 = net.addHost("h2", ip="10.0.0.2/24")

    # secure: with no controller the switches drop traffic instead of looping it
    sw = {name: net.addSwitch(name, protocols="OpenFlow13", failMode="secure")
          for name in ("s1", "s2", "s3", "s4")}

    # ORDER MATTERS: it fixes the interface names, e.g. s1-eth2 is the s1-s2 link.
    net.addLink(h1, sw["s1"], **EDGE)
    net.addLink(sw["s1"], sw["s2"], **PATH_A)
    net.addLink(sw["s1"], sw["s3"], **PATH_B)
    net.addLink(sw["s2"], sw["s4"], **PATH_A)
    net.addLink(sw["s3"], sw["s4"], **PATH_B)
    net.addLink(sw["s4"], h2, **EDGE)
    return net


def main():
    parser = argparse.ArgumentParser(description="NetRescue diamond topology")
    parser.add_argument("--controller-ip", default="127.0.0.1")
    parser.add_argument("--controller-port", type=int, default=6653)
    parser.add_argument("--no-cli", action="store_true",
                        help="start, print a summary, and stop")
    args = parser.parse_args()

    setLogLevel("info")
    net = build_net(args.controller_ip, args.controller_port)
    net.start()
    info("*** Topology up. Controller expected at %s:%d\n"
         % (args.controller_ip, args.controller_port))
    if not args.no_cli:
        CLI(net)
    net.stop()


if __name__ == "__main__":
    main()