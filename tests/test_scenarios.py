"""Tests for topology/scenarios/*.sh using a fake `tc` and `ip` (no root, no Mininet).

The fake tc keeps the state of a Mininet-TCLink-like interface:
    qdisc htb 5: root ... / qdisc netem 10: parent 5:1 limit 1000 delay 5ms
    class htb 5:1 root ... rate 10Mbit ceil 10Mbit
OWNER: Zainab
"""
import os
import re
import shutil
import stat
import subprocess
import textwrap

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCEN = os.path.join(ROOT, "topology", "scenarios")

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")

FAKE_TC = textwrap.dedent('''\
    #!/usr/bin/env python3
    import json, os, sys
    state_file = os.path.join(os.environ["FAKE_DIR"], "tc_state.json")
    log = open(os.path.join(os.environ["FAKE_DIR"], "calls.log"), "a")
    log.write("tc " + " ".join(sys.argv[1:]) + "\\n"); log.close()
    st = json.load(open(state_file))
    a = sys.argv[1:]
    dev = a[a.index("dev") + 1] if "dev" in a else None
    d = st.setdefault(dev, {"netem": "qdisc netem 10: parent 5:1 limit 1000 delay 5ms",
                            "htb": True, "rate": "10Mbit"})
    def save(): json.dump(st, open(state_file, "w"))
    if a[:2] == ["qdisc", "show"]:
        if d["htb"]: print("qdisc htb 5: root refcnt 2 r2q 10 default 0x1")
        if d["netem"]: print(d["netem"])
        else: print("qdisc noqueue 0: root refcnt 2")
    elif a[:2] == ["class", "show"]:
        if d["htb"]: print("class htb 5:1 root prio 0 rate %s ceil %s burst 15Kb" % (d["rate"], d["rate"]))
    elif a[:2] == ["qdisc", "change"] or a[:2] == ["qdisc", "replace"]:
        i = a.index("netem")
        parent = "root" if "root" in a[:i] else a[a.index("parent") + 1]
        handle = a[a.index("handle") + 1] if "handle" in a else "8001:"
        if a[1] == "change" and not d["netem"]:
            sys.exit("RTNETLINK answers: Invalid argument")
        d["netem"] = "qdisc netem %s %s %s" % (handle, "root" if parent == "root" else "parent " + parent, " ".join(a[i + 1:]))
        save()
    elif a[:2] == ["qdisc", "del"]:
        d["netem"] = ""; save()
    elif a[:2] == ["class", "change"]:
        assert a[a.index("classid") + 1] == "5:1" and a[a.index("parent") + 1] == "5:"
        d["rate"] = a[a.index("rate") + 1]; save()
    else:
        sys.exit("unsupported fake tc call: %r" % a)
''')

FAKE_IP = textwrap.dedent('''\\
    #!/usr/bin/env bash
    echo "ip $*" >> "$FAKE_DIR/calls.log"
    for missing in $FAKE_MISSING; do
      [[ " $* " == *" $missing "* ]] && exit 1
    done
    exit 0
''').replace("\\\\", "\\")


@pytest.fixture()
def env(tmp_path):
    fake = tmp_path / "fake"
    fake.mkdir()
    for name, body in (("tc", FAKE_TC), ("ip", FAKE_IP)):
        p = fake / name
        p.write_text(body)
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
    (fake / "tc_state.json").write_text("{}")
    e = dict(os.environ, FAKE_DIR=str(fake), TC=str(fake / "tc"), IP=str(fake / "ip"),
             NR_SKIP_ROOT_CHECK="1", NR_STATE_DIR=str(tmp_path / "state"), FAKE_MISSING="")
    e.pop("NETRESCUE_LINK", None)
    e["_fake"] = str(fake)
    return e


def sh(env, script, *args, **extra):
    e = dict(env, **extra)
    return subprocess.run(["bash", os.path.join(SCEN, script), *args], env=e,
                          capture_output=True, text=True)


def netem(env, dev="s1-eth2"):
    out = subprocess.run([env["TC"], "qdisc", "show", "dev", dev], env=env,
                         capture_output=True, text=True).stdout
    return [l for l in out.splitlines() if l.startswith("qdisc netem")][0]


def rate(env, dev="s1-eth2"):
    out = subprocess.run([env["TC"], "class", "show", "dev", dev], env=env,
                         capture_output=True, text=True).stdout
    return re.search(r"rate (\S+)", out).group(1)


def calls(env):
    return open(os.path.join(env["_fake"], "calls.log")).read()


# ------------------------------------------------------------------ delay
def test_delay_add_and_clear_restore_original(env):
    r = sh(env, "delay.sh", "add", "100ms")
    assert r.returncode == 0, r.stderr
    assert "delay 105ms" in netem(env)
    assert "parent 5:1 handle 10: netem" in calls(env)      # changed in place, not added
    assert re.match(r"EVENT \d+\.\d+ delay_add s1-s2 ", r.stdout)
    assert sh(env, "delay.sh", "clear").returncode == 0
    assert "delay 5ms" in netem(env) and "loss" not in netem(env)


def test_delay_units_and_repeat_do_not_accumulate(env):
    sh(env, "delay.sh", "add", "0.1s")
    sh(env, "delay.sh", "add", "50ms")           # replaces, not 5+100+50
    assert "delay 55ms" in netem(env)


# ------------------------------------------------------------------- loss
def test_loss_keeps_delay_and_delay_keeps_loss(env):
    assert sh(env, "loss.sh", "add", "5%").returncode == 0
    n = netem(env)
    assert "loss 5%" in n and "delay 5ms" in n and "limit 1000" in n
    sh(env, "delay.sh", "add", "40ms")
    n = netem(env)
    assert "delay 45ms" in n and "loss 5%" in n
    sh(env, "loss.sh", "clear")
    n = netem(env)
    assert "loss" not in n and "delay 45ms" in n   # delay scenario untouched
    sh(env, "delay.sh", "clear")
    assert "delay 5ms" in netem(env)


def test_loss_without_percent_sign_and_validation(env):
    assert sh(env, "loss.sh", "add", "2.5").returncode == 0
    assert "loss 2.5%" in netem(env)
    for bad in ("abc", "150%", "-3"):
        r = sh(env, "loss.sh", "add", bad)
        assert r.returncode != 0 and "ERROR" in r.stderr or r.returncode == 2


# -------------------------------------------------------------- bandwidth
def test_bandwidth_changes_htb_class_and_restores(env):
    assert sh(env, "bandwidth.sh", "add", "2mbit").returncode == 0
    assert rate(env) == "2mbit"
    assert "tbf" not in calls(env)
    sh(env, "bandwidth.sh", "clear")
    assert rate(env) == "10mbit"


def test_bandwidth_validation(env):
    for bad in ("2", "fast", "2mbps"):
        assert sh(env, "bandwidth.sh", "add", bad).returncode != 0
    assert rate(env) == "10Mbit"


# ---------------------------------------------------------------- link_fail
def test_link_fail_brings_both_ends_down_and_up(env):
    r = sh(env, "link_fail.sh", "down")
    assert r.returncode == 0, r.stderr
    log = calls(env)
    assert "link set dev s1-eth2 down" in log and "link set dev s2-eth1 down" in log
    assert re.match(r"EVENT \d+\.\d+ link_down s1-s2 ", r.stdout)
    r = sh(env, "link_fail.sh", "up")
    assert "link set dev s1-eth2 up" in calls(env) and "link_up" in r.stdout


def test_other_link_selected_with_env(env):
    sh(env, "link_fail.sh", "down", NETRESCUE_LINK="s3-s4")
    log = calls(env)
    assert "s3-eth2 down" in log and "s4-eth2 down" in log
    assert sh(env, "link_fail.sh", "down", NETRESCUE_LINK="s9-s9").returncode != 0


# ------------------------------------------------------------ general behaviour
def test_missing_interface_gives_helpful_error(env):
    r = sh(env, "delay.sh", "add", "10ms", FAKE_MISSING="s1-eth2")
    assert r.returncode != 0 and "Is Mininet running" in r.stderr


def test_usage_errors(env):
    for script in ("delay.sh", "loss.sh", "bandwidth.sh", "link_fail.sh"):
        assert sh(env, script).returncode == 2
        assert sh(env, script, "bogus").returncode == 2


def test_requires_root_when_check_enabled(env):
    if os.geteuid() == 0:
        pytest.skip("running as root")
    r = sh(env, "delay.sh", "add", "10ms", NR_SKIP_ROOT_CHECK="0")
    assert r.returncode != 0 and "must run as root" in r.stderr


def test_clear_all_resets_everything(env):
    sh(env, "delay.sh", "add", "100ms")
    sh(env, "loss.sh", "add", "5%")
    sh(env, "bandwidth.sh", "add", "2mbit")
    r = sh(env, "clear_all.sh")
    assert r.returncode == 0, r.stderr
    n = netem(env)
    assert "delay 5ms" in n and "loss" not in n and rate(env) == "10mbit"


def test_netem_created_when_link_has_none(env):
    import json
    p = os.path.join(env["_fake"], "tc_state.json")
    json.dump({"s1-eth2": {"netem": "", "htb": False, "rate": ""}}, open(p, "w"))
    assert sh(env, "loss.sh", "add", "3%").returncode == 0
    assert "loss 3%" in netem(env) and "delay 5ms" in netem(env)


# ---------------------------------------------- consistency with the topology
def test_base_values_match_diamond_topo():
    """common.sh must repeat the PATH_A / PATH_B constants of diamond_topo.py."""
    topo = open(os.path.join(ROOT, "topology", "diamond_topo.py")).read()
    a = re.search(r"PATH_A\s*=\s*dict\(bw=(\d+),\s*delay=\"(\d+)ms\"\)", topo)
    b = re.search(r"PATH_B\s*=\s*dict\(bw=(\d+),\s*delay=\"(\d+)ms\"\)", topo)
    assert a and b
    common = open(os.path.join(SCEN, "common.sh")).read()
    assert "s1-s2|s2-s4) echo %s ;;" % a.group(2) in common
    assert "s1-s3|s3-s4) echo %s ;;" % b.group(2) in common
    assert "s1-s2|s2-s4) echo %s ;;" % a.group(1) in common
    assert "s1-s3|s3-s4) echo %s ;;" % b.group(1) in common
