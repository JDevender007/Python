# Cloud Cost Calculator

A monthly bill is a whole number of cents; a unit price is not. The legacy calculator did what a
spreadsheet does:

```python
total = 0.0
for line in bill:
    total += line.quantity * float(line.price_usd)
return round(total * 100)
```

Three separate mistakes live in those three lines.

**1. A unit price is not a bill.** `$0.145` is 14.5 cents and `$1.005` is 100.5 cents. A bill is
charged in whole cents, so the half has to be rounded -- half-up, in public, once. `round()` does
not do that: it rounds half to even, and worse, `0.145 * 100` is `14.499999999999998`, so the float
path rounds *down* where half-up rounds *up*. Three at `$0.145` is **44 cents** here and **43**
there; one at `$1.005` is **101** here and **100** there.

**2. Adding floats adds their errors.** Each line is a double that is already slightly wrong, and
the sum is wrong by a different amount again. The seven bundled lines cost **5716 cents** as
integers and **5714** through floats, and no re-rounding of the total repairs the lines it was
built from.

**3. A price with more precision than a bill can express is refused.** A tenth of a cent is the
finest granularity this module stores; `$0.0234` is not 2.34 tenths, it is a price the caller has
to decide how to round. Silently truncating it is how a bill disagrees with its invoice.

So prices are parsed to integer tenths of a cent, a line is `divide_half_up(quantity *
price_tenths, 10)`, and every total is a sum of those integers. Tiered pricing is billed tier by
tier, each tier rounded at its own boundary, so the 101st unit is priced at the second rate rather
than the first.

## What this project teaches

- Why `$0.145` cannot be stored as a float cent, and where the lost half goes
- `divide_half_up` on integers, versus `round()` half-to-even on a wrong double
- Rounding once per line, then summing -- never summing floats and rounding at the end
- Refusing a price finer than the storage granularity instead of truncating it
- Tiered pricing billed tier by tier, with the boundary unit in the lower tier
- Why the marginal rate on every unit is not the tiered price
- Formatting cents and tenths without a float ever reaching the output
- Comparing a total to a budget in cents and reporting the difference in dollars
- Pinning every disagreement between the integer and float paths
- Auditing a bill by rebuilding each line from its own fields

## How to run

```
python src/main.py --demo
python src/main.py --demo --quiet
python src/main.py --file data/bill.txt --json out.json
python src/main.py --file data/bill.txt --budget 4000 --tier-units 550 --audit
python -m pytest tests -q
```

`--file` names a bill: one `service | sku | quantity | price` row per line, `#` starting a
comment. `--budget` is in cents, `--tier-units` prices a unit count against the bundled tier table.
Exit code `2` means the input was refused -- a missing file, a row without four fields, a quantity
that is not a whole number, a negative price, or a price with more than three decimals. `--audit`
exits `1` if any check fails.

## Project structure

```
CloudCost_Calculator/
├── README.md
├── requirements.txt        # pytest==9.1.1
├── .gitignore
├── data/
│   └── bill.txt            # 7 lines: half-cent, repeating, tiered and bulk rates
├── src/
│   ├── cost_calculator.py  # prices in tenths, bills in cents, tiers, checks, demo
│   └── main.py             # argparse only
└── tests/
    └── test_cost_calculator.py   # 112 tests
```

## What the demo shows

| service | sku | qty | price | cents | float |
| --- | --- | --: | --: | --: | --: |
| compute | c7.large | 730 | $0.013 | 949 | 949 |
| storage | gp3 | 250 | $0.023 | 575 | 575 |
| requests | api-call | 3 | $0.145 | **44** | **43** |
| egress | outbound | 120 | $0.09 | 1080 | 1080 |
| database | db.r6 | 730 | $0.041 | 2993 | 2993 |
| archive | glacier | 1 | $0.265 | **27** | **26** |
| logs | ingest | 44 | $0.011 | 48 | 48 |

- The bill is **5716 cents** as integers, **5714** as floats: **2 cents apart**, from two rows
- `3 x $0.145` -> **44 cents** half-up, **43** from the float
- `$1.005` -> **101 cents** for one unit, **100** from the float
- `$0.0234` is refused: three decimals is the limit
- Tiers: 100 units -> **250 cents**; 101 -> **252** (the boundary unit keeps the first rate);
  550 -> **895 cents** tier by tier, against **495** at the marginal rate
- **$57.16** against a **$50.00** budget: over by **$7.16**
- 13/13 audit checks pass, including one that rebuilds every line from its own fields

## Requirements

Python 3.10+, standard library only (`json`, `dataclasses`, `argparse`). Tests need
pytest==9.1.1. No provider API, no rate-card download; the bill and the tiers are bundled.

---
**Devender J** -- https://github.com/JDevender007
