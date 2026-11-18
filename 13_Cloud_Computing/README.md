<div align="center">

# ☁️ Cloud Computing Projects

### Five cloud labs that each looked like "call the SDK and print the result" — and each one was really a question about what the number can prove. A price is integer cents. A config is a set of leaf paths. A balance index is not a saturation check. A prefix is not a folder. A delivery is not an event.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# ☁️ About

Every project here is an **offline simulation over bundled JSON**, not a wrapper pointed at a live
account. A text bill, three config documents, a capacity scenario, a bucket manifest and a queue
scenario all ship as ASCII in `data/`; the code parses them with the same strictness it would apply
to real input, and nothing reads an environment variable, opens a socket or touches the clock.

That choice is deliberate. A demo that dials out is not reproducible, and a demo that cannot be
reproduced cannot show you the number that was wrong last time. Here the whole input is on disk, so
two runs print the same bytes and each defect is a printable difference rather than an occasional
mystery.

**The lesson of each project is different, on purpose.** Five variations on "wrap the SDK" would
teach nothing; five different places a cloud program confuses a model with a measurement, a count
with a duration, or a format with a guess is the subject.

- **CloudCost_Calculator** — *money is an integer number of cents, and a tier boundary belongs to
  exactly one tier.* The legacy path sums floats: **5716** cents in the rebuild against **5714**
  from `sum()` of the same prices, with `requests` billed **44** vs **43** and `archive` **27** vs
  **26** hours. It also rounds `$1.005` through `round(x, 2)` to **100** cents instead of **101**,
  and prices tier 2 from its own lower bound, so 250 GB costs **250** where the boundary-correct
  answer is **252** and 550 GB costs **495** instead of **895**. The budget check then reports
  `$57.16` against a `$50.00` cap as `$7.16` over — in cents, exactly.
- **Cloud_Config_Manager** — *a merge is recursive, a named list is a map, and drift is a list of
  paths.* `{**base, **overlay}` keeps **9 leaves** of a document that has **18** and drops a whole
  service, because it replaces `services` instead of merging named entries by identity. `desired !=
  observed` is one boolean for a plan that has **8 paths**, cannot see an add or a remove, and calls
  `versioning: False` equal to `versioning: 0`. A top-level-only redactor prints `DB_PASSWORD` from
  `services[api].env` in full; the rebuild masks by key at any depth and masks both sides of a
  changed secret.
- **Load_Balancer_Simulator** — *a counter that never overlaps measures an empty queue, and a
  fairness index cannot see saturation.* `active += 1 ... active -= 1` inside one synchronous call
  leaves every sample at `(0, 0, 0)`, so least-connections sends all **12** requests to `alpha` and
  the makespan is **48** ticks against **12** for a correct least-load policy. Round-robin gives a
  perfectly even **4/4/4** — and runs two backends at **1333** permille of capacity while the third
  sits at 667. Jain's index scores that split **926** because it is scale-free; the rebuild reports
  the **maximum load ratio** beside it and apportions percentages so `334 + 333 + 333 = 1000`,
  where `33.3 + 33.3 + 33.3` sums to **99.9**.
- **S3_File_Manager** — *a prefix is a filter, a delimiter makes a folder, and an ETag is not an
  MD5.* `list_objects_v2(Prefix="logs/")` with no `Delimiter` matches **4** keys — including the
  zero-byte folder marker and three nested logs — and stops at the first page of **3**; the console
  shows two folders because it asks for `CommonPrefixes`. Comparing every ETag to
  `md5(body)` calls **4 of 9** objects corrupt: three multipart uploads whose ETag is a digest of
  digests plus a part count, and one SSE-KMS object whose ETag is not a body digest at all. The
  rebuild separates **8 verified, 0 corrupt, 1 opaque**, pages all **3** pages, and signs
  `reports/q3 final.txt` as `q3%20final.txt` with the requested 300-second expiry.
- **Serverless_Event_Queue** — *at-least-once means the same event twice, and depth is not age.*
  A 45-second handler under a 20-second visibility timeout is delivered at **5s** and again at
  **26s**, and both handlers succeed: **10 successful runs for 9 distinct events**. Ten events
  become **14 deliveries**, **4** of them duplicates. At **63s** the visible depth is **0** while
  the oldest unfinished event is 63 seconds old, and the worst moment is **83s** at depth **0** —
  invisible to a depth alarm, obvious to an age alarm. The poison event exhausts three attempts and
  is redriven to a dead-letter queue at **98s**, and a receipt-handle "dedup" stops **0 of 4**
  duplicates because every delivery carries a new handle.

**Every number is exact and every claim is checkable.** Money is integer cents; ratios are permille
and basis points; ages are whole seconds; `divide_half_up` does the rounding and `round()` never
touches a measurement. Each project's `audit()` re-derives its own result from the loaded records
instead of restating the summary it just printed, and its readers are injectable — `read_decoded=`,
`merge=`, `read=`, `run=`, `verify=`, `list_fn=` — so a negative control can make exactly one check
fail and prove the check is live.

The libraries used are `json`, `hashlib`, `math`, `re`, `dataclasses` and `argparse` — the standard
library, nothing else. No `boto3`, no `PyYAML`, no clock, no `random`, no sockets.

---

# 🎯 Learning Objectives

- Parse decimal money into integer cents and never sum a float
- Round half up on integers, and see `round(1.005, 2)` land on 100
- Assign a tier boundary to one tier only, and price a quantity from its own band
- Compare a total against a budget in the same unit it was measured in
- Merge two mappings recursively, and keep the siblings a shallow merge deletes
- Treat a list of uniquely named objects as a map, preserving base order
- Report drift as a list of paths with a kind, including adds and removes
- Compare config scalars by type and value, because `True == 1`
- Mask a secret by key at any depth, on both sides of a change
- Recognise that an in-flight counter needs overlapping work to mean anything
- Model a weight as capacity in work units per tick, not a share of requests
- Separate a scale-free fairness index from an absolute saturation ratio
- Apportion percentages by largest remainder so they sum to 1000 permille
- Distinguish a prefix filter from a delimiter that groups into common prefixes
- Recompute a multipart ETag as a digest of part digests plus a part count
- Mark a KMS ETag opaque rather than corrupt, and page until `IsTruncated` is false
- Percent-encode a key into a canonical request and bind the expiry into the signature
- Recognise that at-least-once delivery makes the consumer responsible for duplicates
- Measure backlog age as well as visible depth, and know what each one hides
- Retry within an attempt budget, then redrive with the reason attached

---

# 📦 Projects

No. | Project | Description | Tests | Status
--: | --- | --- | --: | :---:
01 | CloudCost_Calculator | Integer-cent pricing, boundary-correct tiers, budget variance and savings in whole cents. | 112 | ✅
02 | Cloud_Config_Manager | Recursive merge, identity-keyed lists, path-level drift and depth-aware secret masking. | 185 | ✅
03 | Load_Balancer_Simulator | Discrete-tick policies, capacity-normalised load, Jain plus a max-load ratio and apportionment. | 134 | ✅
04 | S3_File_Manager | Delimiter listing, pagination, multipart/KMS ETag verification and presigned URLs. | 149 | ✅
05 | Serverless_Event_Queue | Visibility timeouts, duplicate delivery, attempt budgets, DLQ and backlog age. | 146 | ✅

**Total: 726 tests**, and **75 audit checks** across the five projects (13 + 16 + 15 + 16 + 15).

---

# 🧠 Concepts Covered

- Money as integer cents, parsed from decimal text, never through a float
- Half-up rounding as `(2n + d) // (2d)`, and why bankers' rounding is a policy choice
- Usage tiers as half-open bands, with the boundary owned by the upper band
- Budget variance as a signed integer difference, rendered in dollars and cents
- Recursive merge, structural copies, and why a merge must not alias its inputs
- Identity-keyed list merging with base order preserved, versus positional zipping
- Drift as `(path, kind, before, after)` with adds, removes and type changes
- Type-strict equality, `True == 1`, and `0 == False`
- Redaction by key name at any depth, applied at render time and to both sides
- Synchronous request handling and why an in-flight gauge reads zero
- Least-load scheduling on a projected finish, not a connection count
- Smooth weighted round-robin reaching the weight ratio exactly
- Jain's index in permille, its scale invariance, and its blindness to uniform overload
- Maximum load ratio as the absolute check beside the relative index
- Largest-remainder apportionment summing to 1000 permille
- `Prefix` as a string filter, `Delimiter` as the folder boundary, `CommonPrefixes`
- Zero-byte folder markers that are objects whose key is the prefix
- Multipart ETags, part counts, and opaque SSE-KMS ETags
- Continuation pagination and `IsTruncated` as the only reliable end signal
- Percent-encoded canonical requests and an expiry that is part of the signature
- At-least-once delivery, visibility timeouts and duplicate side effects
- Receipt handles versus idempotency keys, and the attempt budget behind a DLQ
- Backlog age versus visible depth, and the alarms each one misses

---

# 📂 Repository Structure

```text
13_Cloud_Computing/
│
├── CloudCost_Calculator/
│   ├── src/    cost_calculator.py, main.py
│   ├── tests/  test_cost_calculator.py
│   └── data/   bill.txt
│
├── Cloud_Config_Manager/
│   ├── src/    config_manager.py, main.py
│   ├── tests/  test_config_manager.py
│   └── data/   desired.json, override.json, observed.json
│
├── Load_Balancer_Simulator/
│   ├── src/    load_balancer.py, main.py
│   ├── tests/  test_load_balancer.py
│   └── data/   scenario.json
│
├── S3_File_Manager/
│   ├── src/    s3_manager.py, main.py
│   ├── tests/  test_s3_manager.py
│   └── data/   bucket.json
│
├── Serverless_Event_Queue/
│   ├── src/    event_queue.py, main.py
│   ├── tests/  test_event_queue.py
│   └── data/   scenario.json
│
└── README.md
```

Each project has the same shape: all logic in one library module, a thin `main.py` argparse CLI,
a `tests/` suite, deterministic ASCII seeds in `data/`, a pinned `requirements.txt`, a
`.gitignore`, and a `README.md` that states its own defect and pins its own numbers.

The input is data. `bill.txt` holds seven billed lines with prices in dollars and at most three
decimals, the config trio holds 18 + 5 + 21 leaves, `scenario.json` holds three backends weighted
1/2/1 with twelve requests of four units, `bucket.json` holds 9 objects (5 single, 3 multipart,
1 KMS) with their declared ETags, and the queue scenario holds 10 events with processing times and
failing attempts. Each library module still carries the defective expression as an executable
string — `LEGACY_TOTAL`, `LEGACY_TIER`, `LEGACY_MERGE`, `LEGACY_DRIFT`, `LEGACY_REDACT`,
`LEGACY_ACTIVE`, `LEGACY_CHOOSE`, `LEGACY_FAIRNESS`, `LEGACY_SHARE`, `LEGACY_LIST`, `LEGACY_ETAG`,
`LEGACY_URL`, `LEGACY_COUNT`, `LEGACY_ALARM`, `LEGACY_REDRIVE`, `LEGACY_DEDUP` — so the tests can
run the wrong code beside the right one on the same input.

No module imports `boto3`, `botocore`, `yaml`, `time` or `random`. Storage is a JSON manifest, the
queue is a discrete-event loop over whole seconds, and every demo is byte-for-byte reproducible.

---

# ▶️ Run any project

```bash
cd 13_Cloud_Computing/Load_Balancer_Simulator

python src/main.py --demo          # offline, deterministic, exit 0
python src/main.py --file data/scenario.json --json out.json
python src/main.py --audit         # every check with PASS/FAIL
python -m pytest tests -q          # the suite
```

Every project supports `--demo`, `--quiet` with `--demo` (prints nothing on stdout or stderr),
`--audit`, `--json <path>` and `--file <input>` naming the primary seed file; sibling seeds are
read from the same folder. Exit code `2` means the input was refused, with `error: ...` on
stderr — a missing file, a non-ASCII byte, invalid JSON, a root that is not a mapping, an unknown
top-level key, a duplicate name, a value outside its declared range, or a document that does not
validate. Nothing opens a connection and no demo writes into the repository: JSON output goes only
where you point it.

---

# ✅ Verify the whole category

```powershell
Get-ChildItem -Directory | ForEach-Object {
    Push-Location $_
    python -m compileall -q src tests
    python -m pytest tests -q
    python src\main.py --demo
    python src\main.py --demo --quiet
    Pop-Location
}
```

The gates each project must pass, and does:

1. `compileall` on `src` and `tests` exits 0
2. `pytest` passes with no skips, 112+ tests
3. `--demo` exits 0, prints `Cross-checks OK: ...` then `Demo completed successfully.` as its last two lines
4. `--demo` twice produces byte-identical output, and `--demo --quiet` prints nothing at all
5. no non-ASCII byte in `src/`, `tests/` or the text data files

---

# 🎓 Learning Outcomes

This category helps you understand:

- Why a price is an integer quantity and a float is a rounding decision waiting to happen
- Why a tier boundary must belong to one band, and how pricing from the wrong end doubles a bill
- Why a shallow merge is silent: it deletes the siblings it never looked at
- Why a list of named objects is a map, and why position is not identity
- Why one boolean cannot describe a plan that has eight paths
- Why `True == 1` makes `==` an unsafe comparison for configuration
- Why redaction belongs at render time, by key, at every depth
- Why an in-flight counter needs overlap, and why least-connections degenerates without it
- Why a weight is capacity, so equal request counts can saturate a third of the fleet
- Why Jain's index is scale-free, and why a saturation ratio must sit beside it
- Why percentages are apportioned, not divided, if they must sum to 100
- Why a prefix filter and a folder view are two different queries
- Why a multipart ETag is a digest of digests, and a KMS ETag is opaque rather than corrupt
- Why a listing ends when `IsTruncated` is false, not when a token looks empty
- Why a presigned URL encodes the key and signs the expiry, and proves nothing about existence
- Why at-least-once delivery makes idempotency the consumer's job
- Why queue depth hides in-flight work and says nothing about waiting time
- Why an attempt budget with a DLQ preserves the event a delete-on-failure policy loses
- Why a receipt handle identifies a delivery while an event id identifies the event
- How to write an audit whose every check has a negative control
- How to make a cloud demonstration reproducible byte for byte

---

# 🛠️ Patterns Included

Parsing - `parse_bill`, `read_bill`, `load_document`, `read_configs`, `read_scenario`, `read_bucket`
Records - `BillLine`, `Change`, `Backend`, `Request`, `Scenario`, `Placement`, `Run`, `ObjectRecord`, `Manifest`, `Listing`, `Event`, `QueueConfig`, `Delivery`, `DeadLetter`, `Snapshot`
Validation - `DomainError`, `ConfigError`, `ScenarioError`, `BucketError`, `QueueError`, `validate_or_raise`, `problems`
Arithmetic - `divide_half_up`, `ceil_div`, `jain_permille`, `apportion_permille`, `max_load_permille`
Pricing - `parse_price`, `format_cents`, `line_cents`, `legacy_line_cents`, `bill_total`, `legacy_bill_total`, `tiered_cents`, `legacy_tiered_cents`, `budget_status`, `disagreements`
Config - `deep_merge`, `shallow_merge`, `_merge_lists`, `diff`, `same`, `mask`, `leaks`, `count_leaves`, `names_of`, `build_plan`, `summarize`
Balancing - `simulate`, `_smooth_weighted_index`, `legacy_fairness`, `legacy_shares`, `spread`, `capacity_verdict`, `legacy_verdict`, `render_run`
Storage - `list_objects`, `legacy_list`, `query`, `md5_hex`, `multipart_etag`, `expected_etag`, `verify_etags`, `legacy_verify`, `encode_key`, `presign`, `legacy_presign`
Queues - `simulate`, `legacy_processed`, `legacy_alarm`, `legacy_dropped`, `legacy_dedup_hit`, `receipt_handle`, `age_worst`, `stale_moment`
Legacy - `LEGACY_TOTAL`, `LEGACY_TIER`, `LEGACY_MERGE`, `LEGACY_DRIFT`, `LEGACY_REDACT`, `LEGACY_ACTIVE`, `LEGACY_CHOOSE`, `LEGACY_FAIRNESS`, `LEGACY_SHARE`, `LEGACY_LIST`, `LEGACY_ETAG`, `LEGACY_URL`, `LEGACY_COUNT`, `LEGACY_ALARM`, `LEGACY_REDRIVE`, `LEGACY_DEDUP`
Reporting - `measure`, `report`, `render_plan`, `render_run`, `render_listing`, `render_timeline`, `render_dead`, `--json`
Auditing - `audit`, `_guard`, injectable readers, mergers, verifiers, listers and simulators
Testing - exact pinned numbers, validation refusals, one failing check per negative control

---

# 🚀 Future Improvements

- A shared `--batch` runner that executes all five demos and compares their output hashes
- A real rate-card importer that converts vendor price sheets into the same integer-cent schema
- A merge policy table so lists can opt into replace, append or identity-merge per path
- A capacity planner that turns the load-balancer output into a per-backend scaling recommendation
- A storage-class transition model layered on the bucket manifest, still without a network call
- A queue scenario generator that fuzzes visibility timeouts and asserts the duplicate bound
- A terminal-diff view that shows the exact cents, leaves or deliveries the legacy path got wrong

---

# 🤝 Contributing

Contributions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Commit your changes with a clear message.
4. Push the branch.
5. Open a Pull Request.

---

# 👨‍💻 Author

**Devender J**

Python Developer | Data Analytics Enthusiast | AI & Machine Learning Learner

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found these projects useful, consider giving this repository a star.

</div>
