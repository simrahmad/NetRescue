# NetRescue

**Performance-Aware Adaptive Routing Under Dynamic Network Conditions**
Computer Networks semester project, NUST SEECS.

NetRescue is a software-defined networking project. A Mininet network with two redundant paths between a client and a server is controlled by a Ryu controller. The controller reads live latency, packet loss, and link utilization, computes a cost per link, picks the best path with Dijkstra's algorithm, and installs OpenFlow rules. It reroutes traffic when a path becomes congested, lossy, or fails, using hysteresis to avoid route flapping. A Flask dashboard shows the live state. Adaptive routing is compared against a hop-count shortest-path baseline.

**Research question:** Can routing that considers live latency, loss, and congestion outperform shortest-path routing in a controlled network?

## Team

| Person | Role | Folders |
|---|---|---|
| Simrah (Lead) | Scaffold, baseline, controller, API, integration | root, `controller/`, `docs/` |
| Zainab Fatima (Lead) | Routing logic, scenarios, project management, report | `routing/`, `topology/scenarios/`, `docs/report/` |
| M3 (add name) | Monitoring | `monitoring/` |
| M4 (add name) | Dashboard | `dashboard/` |
| M5 (add name) | Experiments and evaluation | `experiments/` |

## Repository layout

| Folder | Purpose |
|---|---|
| `topology/` | Mininet topology and failure scenarios |
| `controller/` | Ryu controllers (baseline and adaptive) and REST API |
| `routing/` | Link cost formula and Dijkstra with hysteresis |
| `monitoring/` | Latency, loss, throughput, and utilization measurement |
| `dashboard/` | Flask dashboard |
| `experiments/` | Experiment runner, results, and plots |
| `data/` | Mock metrics for development without a live network |
| `docs/` | Architecture, API contract, and report sections |
| `tests/` | Tests |

## Getting started

1. Use Ubuntu 20.04 or 22.04 (a VM is fine). Windows and macOS cannot run Mininet directly.
2. Clone the repo and run `bash setup.sh` (added in Step 4 of the setup plan).
3. Run `make topo`, `make controller`, `make dashboard` (commands added with the Makefile).

The dashboard developer can work on any operating system using `data/mock_metrics.json`.

## Where to start

Open your own folder, read the `TODO` comments in your files, and work on your own branch. The full plan, task list, and timeline are in the "NetRescue: Team Project Guide" document.

## Timeline

15 days. Feature freeze at the end of Day 12. Days 13 to 15 are for the report, slides, and demo.
