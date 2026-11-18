# Cloud Config Manager

A config manager is three one-line shortcuts that look correct until a second service appears -- and
they fail in four separate ways:

```python
merged = {**base, **overlay}          # one level, whole subtrees
drift = desired != observed           # one boolean, no path
if "secret" in key: value = "***"     # top level only
```

Each line produces a confident answer, and each one is silent.

**1. A shallow merge discards siblings.** `{**base, **overlay}` replaces a whole subtree, so an
overlay that changes one service's replica count deletes every other service along with its
image and environment. The bundled trio keeps **18 leaves** through a recursive merge and only
**9** through the shallow one: `services` falls from 2 entries to 1, and `tags` from 2 keys to
1.

**2. A list of named objects merges by identity, not by index.** Even a merge that recurses has to
decide what a list is. Replacing it loses data; zipping by position merges `web` with `api` as
soon as the order differs. A list whose entries all carry a unique string `name` is a map: merge
each named entry, keep the unmatched ones, preserve base order. An overlay of
`{name: api, replicas: 5}` therefore keeps `api`'s image and both of its environment variables and
changes only the count.

**3. Drift is a set of leaf paths, and absence is not a value.** `desired != observed` says *that*
something differs, never *what*: one boolean for a plan that has to touch eight places. Comparing
only the keys present in both is the other half of the mistake -- it cannot see a missing key (an
add) or an extra one (a remove). And Python's `==` is not type-strict: `True == 1` and `0 ==
False`, so a config that changed `versioning: false` to `versioning: 0` is reported as no drift at
all. The rebuild walks the union of keys, compares scalars with `type(left) is type(right) and
left == right`, and emits one `Change` per path.

**4. A secret is masked at render time and at every depth.** A redactor that only looks at
top-level keys prints `DB_PASSWORD` in full as soon as it lives under `services[api].env`, and a
plan that prints `before: '<old secret>'` leaks the value it just replaced. The rebuild masks by
key name at any depth, masks both sides of a secret change, and the demo searches its own rendered
plan for the bundled secret strings to prove none survived.

The demonstration is offline: three JSON documents, no YAML dependency, no cloud API, no clock.

## What this project teaches

- Why a recursive merge is the only merge that preserves untouched siblings
- Why a list is sometimes a map: identity by unique `name`, base order preserved
- Why structural copies are mandatory when the merged document outlives the call
- Why drift must be a list of paths with a kind, not a boolean
- Why absence needs two kinds -- an add and a remove -- and one-sided comparison sees neither
- Why `True == 1` makes `==` an unsafe config comparison, and what type-strict means
- Why redaction belongs at render time, by key, at every depth
- Why both the old and new value of a secret must be masked
- Why a shallow merge loses exactly the data the deep merge was supposed to keep
- Why validation should collect every problem instead of raising on the first
- How to audit a merge-and-diff pipeline by rebuilding it from the three documents

## How to run

```
python src/main.py --demo
python src/main.py --demo --quiet
python src/main.py --file data/desired.json --json out.json
python src/main.py --file data/desired.json --audit
python -m pytest tests -q
```

`--file` names the desired config; `override.json` and `observed.json` are read from the same
folder unless `--override` and `--observed` name them explicitly. `--audit` exits `1` if any check
fails. Exit code `2` means the input was refused -- a missing file, non-ASCII bytes, invalid JSON,
a root that is not a mapping, an unknown top-level key, a non-slug project or region, a duplicate
service name, a replica count of zero, or a price-like storage size outside its range.

## Project structure

```
Cloud_Config_Manager/
├── README.md
├── requirements.txt        # pytest==9.1.1
├── .gitignore
├── data/
│   ├── desired.json        # 18 leaves, 2 services
│   ├── override.json       # 5 leaves: region, budget, api replicas, tags.env
│   └── observed.json       # 21 leaves: drift, an extra service, a rotated secret
├── src/
│   ├── config_manager.py   # merge, diff, mask, audit, demo
│   └── main.py             # argparse only
└── tests/
    └── test_config_manager.py   # 185 tests
```

## What the demo shows

| step | legacy | rebuild |
| --- | --- | --- |
| leaves after overlay | 9 | **18** |
| services after overlay | 1 (`api`) | **2** (`web`, `api`) |
| api replicas | 3 (unchanged) | **5** |
| drift | one boolean | **8 paths** |
| change kinds | none | **6 change, 1 add, 1 remove** |
| `versioning` bool vs int | equal | **different** |
| secret values leaked | 1 of 2 | **0 of 2** |

The eight paths, in plan order:

```
~ $.region                                us-east-1 -> us-west-2
~ $.services[web].image                   nginx:1.24 -> nginx:1.25
~ $.services[api].replicas                4 -> 5
~ $.services[api].env.DB_PASSWORD         *** (secret value changed)
- $.services[worker]                      (not in the desired config)
~ $.storage.versioning                    True -> False
~ $.budget                                400 -> 500
+ $.tags.env                              staging
```

- **16/16 audit checks pass**, including one that rebuilds the plan from the three documents
- `True == 1` is `True`; `same(True, 1)` is `False`, and `diff` reports the type change
- The rendered plan names `DB_PASSWORD` but never prints either of the two secret values
- `--demo --quiet` prints nothing on stdout or stderr, and two demos are byte-identical

## Requirements

Python 3.10+, standard library only (`json`, `re`, `dataclasses`, `argparse`). Tests need
pytest==9.1.1. No YAML parser, no cloud SDK, no credentials, no network call; the three documents
are bundled.

---
**Devender J** -- https://github.com/JDevender007
