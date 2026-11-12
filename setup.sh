#!/usr/bin/env bash
# NetRescue environment setup. Run on Ubuntu 20.04 or 22.04:  bash setup.sh
set -e

echo "== 1/4 System packages =="
sudo apt update
sudo apt install -y mininet openvswitch-switch iperf3 tcpdump \
    python3-venv python3-pip git make net-tools

echo "== 2/4 Start Open vSwitch =="
sudo systemctl enable --now openvswitch-switch

echo "== 3/4 Python virtual environment =="
# --system-site-packages lets the venv see the apt-installed Mininet module
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install --upgrade pip
pip install "setuptools==65.5.1" wheel
pip install -r requirements.txt

echo "== 4/4 Version check =="
python3 --version
ryu-manager --version
sudo ovs-vsctl --version | head -n 1
mn --version
iperf3 --version | head -n 1

echo
echo "Setup finished. Activate the environment with:  source venv/bin/activate"