# Load Balancer Simulator

A load balancer that never overlaps a request measures an empty queue. The legacy version is built
from three honest-looking lines:

```python
self.active += 1
ok = rng.random() >= self.failure_rate
self.active -= 1

return min(pool, key=lambda b: (b.active, b.name))
```

Each line is correct on its own. Together they send every request to the alphabetically first
backend.

**1. A counter incremented and decremented inside one call is not a measurement.** `serve()` is
synchronous: by the time the next request is dispatched, every backend's `active` is back to zero.
`least_connections` therefore sees `(0, "alpha"), (0, "beta"), (0, "gamma")` for every request and
sends all **12** of them to `alpha`, whose queue ends at **48** ticks while its two peers finish at
**0**. Concurrency is not a detail of least-connections; it is the quantity the strategy is named
after.

**2. A weight is capacity, not a request count.** Round-robin gives `alpha`, `beta` and `gamma` four
requests each. With weights 1, 2 and 1 that is 16, 16 and 16 units of work against fair shares of
12, 24 and 12: `alpha` and `gamma` run at **1333 permille** of their capacity and `beta` at
**667**. Splitting requests evenly is balancing *counts*, not load.

**3. Fairness is not `max - min`.** The legacy score is `max(counts) - min(counts)`, which calls the
4/4/4 split **perfect** -- spread 0 -- although `alpha` and `gamma` are each at 1333‰ and `beta` at
667‰. Jain's index over capacity-normalised load scores the same split **926**: nearly fair, and
blind to the fact that two backends are saturated. Jain is scale-free; it compares backends to each
other, never to their own limit. The rebuild reports both -- the index for balance and the
**maximum load ratio** for saturation -- and the 4/4/4 split is balanced by neither.

**4. A percentage is an apportionment, not a division.** `100 * count / total` formatted to one
decimal prints `33.3%` three times for a 4/4/4 split, and the three lines sum to **99.9**. The
rebuild apportions 1000 permille with the largest-remainder method: **334 + 333 + 333 = 1000**,
exactly, every time.

The simulation is discrete and integer. A backend completes `weight` work units per tick, a request
finishes at `ceil(assigned_work / weight)`, and no clock, socket, float or random number is
involved. Twelve requests of four units run against three backends weighted 1, 2 and 1, and every
number below is reproducible from `data/scenario.json`.

## What this project teaches

- Why an in-flight counter needs overlapping requests to mean anything
- Why least-connections degenerates to "first name" without concurrency
- Why a weight is a capacity in work units per tick, not a share of requests
- Why equal request counts can saturate one backend and idle another
- How smooth weighted round-robin reaches the weight ratio exactly
- Why greedy least-load scheduling needs a projected finish, not a connection count
- Why Jain's index is scale-free, and why that makes it blind to uniform overload
- Why you need an absolute load ratio beside a fairness index
- Why `max - min` calls an overloaded distribution perfect
- Largest-remainder apportionment: percentages that sum to 1000 permille
- Why a fixed simulation is more informative than a random one
- How to audit four policies by rebuilding all of them from the scenario

## How to run

```
python src/main.py --demo
python src/main.py --demo --quiet
python src/main.py --file data/scenario.json --json out.json
python src/main.py --file data/scenario.json --policy least_load
python src/main.py --file data/scenario.json --audit
python -m pytest tests -q
```

`--file` names a scenario: a name, a list of `{name, weight}` backends and a list of
`{name, work}` requests. `--policy` prints one table instead of four. `--audit` exits `1` if any
check fails. Exit code `2` means the input was refused -- a missing file, non-ASCII bytes, invalid
JSON, a root that is not a mapping, a bad or duplicate backend name, a weight outside 1..64, an
empty request list, or work outside 1..1024.

## Project structure

```
Load_Balancer_Simulator/
├── README.md
├── requirements.txt        # pytest==9.1.1
├── .gitignore
├── data/
│   └── scenario.json       # 3 backends weighted 1/2/1, 12 requests of 4 units
├── src/
│   ├── load_balancer.py    # policies, integer metrics, audit, demo
│   └── main.py             # argparse only
└── tests/
    └── test_load_balancer.py   # 134 tests
```

## What the demo shows

| policy | counts | work | makespan | total | Jain(counts) | Jain(capacity) | max load |
| --- | --- | --- | --: | --: | --: | --: | --: |
| round_robin | 4/4/4 | 16/16/16 | 16 | 100 | 1000 | 926 | **1333** |
| smooth_weighted | 3/6/3 | 12/24/12 | 12 | 90 | 889 | 1000 | 1000 |
| legacy_least_connections | **12/0/0** | **48/0/0** | **48** | **312** | 333 | 333 | **4000** |
| least_load | 3/6/3 | 12/24/12 | 12 | 90 | 889 | 1000 | 1000 |

- The legacy in-flight counter samples `(0, 0, 0)` on all 12 requests, so every request lands on
  `alpha`: **12/0/0**, makespan **48** ticks, total completion **312**
- Least load and smooth weighted round-robin agree on counts and work, and disagree on placement:
  `beta, alpha, beta` versus `beta, alpha, gamma` for the first three requests
- Round-robin's capacity Jain is **926** -- "nearly fair" -- while the busiest backend is at
  **1333** permille: the index alone would have called a saturated split acceptable
- Float shares for 4/4/4 are `33.3 + 33.3 + 33.3 = 99.9%`; apportioned permille is
  `334 + 333 + 333 = 1000`
- **15/15 audit checks pass**, including one that rebuilds all four runs from the scenario

## Requirements

Python 3.10+, standard library only (`json`, `math`, `dataclasses`, `argparse`). Tests need
pytest==9.1.1. No sockets, no real backends, no clock, no random seed; the scenario is bundled.

---
**Devender J** -- https://github.com/JDevender007
