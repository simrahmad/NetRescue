# NetRescue Architecture

## Topology

    h1 -- s1 -- s2 -- s4 -- h2     Path A: 10 Mbps, 5 ms per link
           \         /
            -- s3 --              Path B:  5 Mbps, 12 ms per link

| Node | IP | MAC | DPID |
|---|---|---|---|
| h1 | 10.0.0.1 | 00:00:00:00:00:01 | |
| h2 | 10.0.0.2 | 00:00:00:00:00:02 | |
| s1 to s4 | | | 0000000000000001 to 0000000000000004 |

## Switch ports (fixed)

| Switch | Port 1 | Port 2 | Port 3 |
|---|---|---|---|
| s1 | h1 | s2 | s3 |
| s2 | s1 | s4 | |
| s3 | s1 | s4 | |
| s4 | s2 | s3 | h2 |

## Linux interface names (for tc and link scripts)

| Link | Interface |
|---|---|
| s1-s2 (Path A) | s1-eth2 |
| s1-s3 (Path B) | s1-eth3 |
| s2-s4 (Path A) | s2-eth2 |
| s3-s4 (Path B) | s3-eth2 |

## Design notes

- Switches run in secure fail mode and use OpenFlow 1.3.
- ARP is static (autoStaticArp) because the loop would circle ARP broadcasts.
- The controller listens on port 6653.