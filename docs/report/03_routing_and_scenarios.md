# Link cost, routing algorithm and failure scenarios (draft)

Owner: Zainab Fatima. Code: `routing/`, `topology/scenarios/`. Tests: `tests/`.

## 1. Link cost

For each core link the controller computes

    C = alpha * L + beta * P + gamma * U        (alpha, beta, gamma = 0.4, 0.4, 0.2)

| Term | Meaning | Normalization |
|---|---|---|
| L | probe round-trip latency | latency_ms / 200, clipped to 0..1 |
| P | packet loss | loss_pct / 10, clipped to 0..1 |
| U | utilization | util (already 0..1), clipped |

Justification of the caps: healthy RTT is 10 ms (Path A) and 24 ms (Path B) and the delay
scenario adds about 100 ms, so 200 ms keeps all scenarios below saturation. At 10 percent
loss TCP is already unusable, so larger values are equally bad.

* A `down` link has infinite cost and is never selected.
* A `congested` link is still usable; congestion only raises the cost through L, P and U.
  This is how the controller keeps congestion and failure separate.
* No latency reading (all probes lost) counts as the worst value; a missing loss or
  utilization reading counts as 0.

Path cost is the sum of its link costs. Dijkstra's algorithm (`routing/dijkstra.py`) finds the
cheapest switch-to-switch path; ties go to the lower-numbered switch, which is Path A and
matches the baseline.

## 2. Hysteresis (`PathSelector`)

Switch only if another path is at least `margin` (20 percent) cheaper than the current one for
`confirmations` (3) readings in a row. Exceptions: the first reading, and a failed current path,
which switch immediately. An optional `cooldown` (readings after a switch, default 0) is
available to study oscillation. Utilization feeds back on itself (moving traffic to B raises
B's utilization), so margin, confirmations and cooldown are the parameters to tune and to
report in the experiments, including the cost of switching too eagerly.

## 3. Scenario scripts

All scripts take `add <value>` / `clear` (`down` / `up` for link_fail) and `status`.
Default link `s1-s2` (first hop of Path A); change with `NETRESCUE_LINK=s2-s4`.

| Scenario | Command | Mechanism |
|---|---|---|
| Delay | `sudo bash topology/scenarios/delay.sh add 100ms` | netem delay on s1-eth2 |
| Loss | `sudo bash topology/scenarios/loss.sh add 5%` | netem loss on s1-eth2 |
| Bandwidth | `sudo bash topology/scenarios/bandwidth.sh add 2mbit` | htb class rate on s1-eth2 |
| Failure | `sudo bash topology/scenarios/link_fail.sh down` / `up` | `ip link set` on both ends |
| Reset all | `sudo bash topology/scenarios/clear_all.sh` | between experiment repeats |

Mininet's TCLink already installs an htb rate limiter and a netem delay on every link, so the
scripts change those existing qdiscs rather than adding new ones, and `clear` restores the
original 5 ms / 10 Mbit (Path A) or 12 ms / 5 Mbit (Path B). Every call prints an
`EVENT <epoch> <name> <link> <detail>` line with the exact time of the change.

Verification: `bash topology/scenarios/delay.sh status` (or `tc qdisc show dev s1-eth2`).

## 4. Limitations to state in the report

* Impairments are applied in one direction (h1 to h2), so a 100 ms delay raises RTT by 100 ms.
* Results come from Mininet, not physical routers.
* Cost weights and caps are chosen by us, not derived; the experiments report sensitivity.
