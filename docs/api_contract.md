# NetRescue API Contract

Every component uses these formats. If something must change, tell Simrah and update this file in the same pull request. Develop against `data/mock_metrics.json` until the live controller API is ready.

## Conventions

| Item | Rule |
|---|---|
| Latency | milliseconds, number |
| Loss | percent, 0 to 100 |
| Utilization (`util`) | fraction of link capacity, 0.0 to 1.0 |
| Throughput | Mbps, number |
| Time | ISO 8601 UTC string, for example `2026-11-16T10:30:00Z` |
| Link ID | the two switch names joined by a dash, lower number first: `s1-s2`, `s1-s3`, `s2-s4`, `s3-s4` |
| Routed links | only the four core links above (host links `h1-s1` and `s4-h2` are not routed) |

## Topology

```
h1 -- s1 -- s2 -- s4 -- h2      (Path A)
       \         /
        -- s3 --               (Path B)
```

## Link status values

| Status | Meaning |
|---|---|
| `up` | working normally |
| `congested` | still usable, but utilization or loss is above the threshold |
| `down` | failed (several probes in a row received no reply) |

Thresholds are configurable (Zainab and M3 agree on the defaults). The monitoring code must keep `congested` and `down` separate.

## Objects

### Link metrics (produced by `monitoring/`)

```json
{
  "link": "s1-s2",
  "latency_ms": 12.4,
  "loss_pct": 0.5,
  "throughput_mbps": 8.2,
  "util": 0.3,
  "capacity_mbps": 10,
  "status": "up"
}
```

### Metrics snapshot (published every 1 to 2 seconds)

```json
{
  "timestamp": "2026-11-16T10:30:00Z",
  "links": [ { "...": "link metrics objects, one per core link" } ]
}
```

### Route (produced by `controller/`)

```json
{
  "timestamp": "2026-11-16T10:30:00Z",
  "mode": "adaptive",
  "path": ["h1", "s1", "s3", "s4", "h2"],
  "path_name": "B",
  "cost": 0.41
}
```

`mode` is `adaptive` or `baseline`. `path_name` is `A` (via s2) or `B` (via s3).

### Event (produced by `controller/`)

```json
{
  "id": 3,
  "timestamp": "2026-11-16T10:30:05Z",
  "type": "route_change",
  "from_path": "A",
  "to_path": "B",
  "reason": "loss 4.2 percent and utilization 0.92 on s1-s2"
}
```

`type` is one of `route_change`, `link_down`, `link_up`, `congestion`.

## REST endpoints (served by `controller/api.py`, port 8080)

| Method | Path | Returns |
|---|---|---|
| GET | `/topology` | nodes and links |
| GET | `/metrics` | latest metrics snapshot |
| GET | `/current_route` | current route object |
| GET | `/events` | list of events, newest last |
| GET | `/mode` | `{"mode": "adaptive"}` |
| POST | `/mode` | body `{"mode": "baseline"}` switches mode |

The dashboard (Flask, port 5000) calls these. Until the controller API exists, it reads `data/mock_metrics.json`, which has one key per endpoint: `topology`, `metrics`, `current_route`, `events`.

## Experiment results (produced by `experiments/`)

One CSV row per run, saved in `experiments/results/`:

| Column | Meaning |
|---|---|
| `run_id` | unique number |
| `scenario` | `delay`, `loss`, `bandwidth`, or `link_fail` |
| `mode` | `baseline` or `adaptive` |
| `repeat` | 1 to 5 or more |
| `recovery_time_s` | time until traffic works again |
| `packets_lost` | packets lost during the event |
| `avg_latency_ms` | average end-to-end latency |
| `throughput_mbps` | average throughput |
| `route_changes` | number of path switches during the run |