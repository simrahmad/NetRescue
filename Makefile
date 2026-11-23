# NetRescue commands. Run on the Ubuntu VM from the repo root.
# Each command line starts with ">" instead of a Tab (see .RECIPEPREFIX).
.RECIPEPREFIX = >
PYTHON = venv/bin/python
RYU    = venv/bin/ryu-manager

.PHONY: help topo controller adaptive dashboard experiment test clean
.PHONY: help topo controller adaptive adaptive-dev monitor dashboard experiment test clean

help:
> @echo "Terminal 1:  make controller   (baseline Ryu controller)"
> @echo "             make adaptive     (adaptive Ryu controller)"
> @echo "Terminal 2:  make topo         (Mininet network + CLI, needs sudo)"
> @echo "Terminal 3:  make dashboard    (Flask dashboard on port 5000)"
> @echo "Other:       make experiment | make test | make clean"

topo:
> sudo $(PYTHON) topology/diamond_topo.py

controller:
> $(RYU) --ofp-tcp-listen-port 6653 controller/baseline_controller.py


adaptive:
> $(RYU) --ofp-tcp-listen-port 6653 --wsapi-host 127.0.0.1 --wsapi-port 8080 controller/adaptive_controller.py

adaptive-dev:
> NETRESCUE_DEV_FEED=/tmp/netrescue_feed.json $(RYU) --ofp-tcp-listen-port 6653 --wsapi-host 127.0.0.1 --wsapi-port 8080 controller/adaptive_controller.py

dashboard:
> $(PYTHON) dashboard/app.py

experiment:
> sudo $(PYTHON) experiments/run_experiment.py

test:
> $(PYTHON) -m pytest -q tests

clean:
> sudo mn -c

monitor:
> sudo $(PYTHON) -m monitoring.publisher