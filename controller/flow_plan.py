"""Pure forwarding plan for the diamond topology.  OWNER: Simrah

No Ryu or Mininet imports, so this file can be unit-tested anywhere.

A "plan" is {switch_number: {destination_ip: output_port}} for traffic between
h1 (10.0.0.1) and h2 (10.0.0.2). The two middle switches (s2, s3) always forward
along the diamond, so only two rules ever change when the path changes:
  * s1, traffic for h2 : output port toward s2 (Path A) or s3 (Path B)
  * s4, traffic for h1 : output port toward s2 (Path A) or s3 (Path B)

Port numbers are fixed by diamond_topo.py (see docs/architecture.md).
"""

H1_IP = "10.0.0.1"
H2_IP = "10.0.0.2"

# (switch, neighbour) -> port on that switch; hosts: h1 on s1 port 1, h2 on s4 port 3
SWITCH_PORTS = {
    (1, 2): 2, (1, 3): 3,
    (2, 1): 1, (2, 4): 2,
    (3, 1): 1, (3, 4): 2,
    (4, 2): 1, (4, 3): 2,
}
H1_PORT = 1   # on s1
H2_PORT = 3   # on s4
SWITCHES = (1, 2, 3, 4)
MIDDLE = {"A": 2, "B": 3}   # path name -> middle switch used


def plan_for(path_name):
    """Return {switch: {ip: port}} for Path "A" (via s2) or "B" (via s3)."""
    if path_name not in MIDDLE:
        raise ValueError("unknown path %r (expected 'A' or 'B')" % (path_name,))
    via = MIDDLE[path_name]
    plan = {sw: {} for sw in SWITCHES}
    # h1 -> h2
    plan[1][H2_IP] = SWITCH_PORTS[(1, via)]
    plan[via][H2_IP] = SWITCH_PORTS[(via, 4)]
    plan[4][H2_IP] = H2_PORT
    # h2 -> h1
    plan[4][H1_IP] = SWITCH_PORTS[(4, via)]
    plan[via][H1_IP] = SWITCH_PORTS[(via, 1)]
    plan[1][H1_IP] = H1_PORT
    # the unused middle switch keeps static rules so it can take over instantly
    other = 3 if via == 2 else 2
    plan[other][H2_IP] = SWITCH_PORTS[(other, 4)]
    plan[other][H1_IP] = SWITCH_PORTS[(other, 1)]
    return plan


def changed_rules(old_plan, new_plan):
    """List of (switch, ip, port) present in new_plan but different from old_plan."""
    changes = []
    for sw in sorted(new_plan):
        for ip, port in sorted(new_plan[sw].items()):
            if old_plan.get(sw, {}).get(ip) != port:
                changes.append((sw, ip, port))
    return changes