# Inventory Database

A stock ledger stores a **signed** entry per movement: a receipt is positive, an issue is
negative, an adjustment is whatever the stocktake says. The legacy system stored positive
magnitudes and rebuilt the sign at query time with a `CASE` branch -- and because that
branch names `out` explicitly and lets everything else fall into the `ELSE`, a `-30`
water-damage write-off is read back as `+30`. The shelf reports 70 lamps where 10 remain,
and the numbers never reconcile against the stocktake. This project teaches that **the sign
belongs in the data, not in a `CASE` branch**.

The same system prices each category with `SUM(units) * p.unit_price`, a bare column beside
an aggregate. SQLite returns the price of an arbitrary row in the group, so a category worth
`40954.00` is reported at `22954.00` -- and the query never errors.

Both defective queries are kept as executable strings and run beside the corrected ones on
the same seed files.

## What this project teaches

- A ledger entry carries its own sign, and a query that re-derives it creates a second source of truth
- Why `CASE ... ELSE` silently absorbs every label the author forgot (`adjustment`)
- The exact arithmetic of the bug: a mis-signed adjustment is off by *twice* its magnitude
- Refusing a sign/label mismatch by name instead of quietly normalising it
- A bare column beside an aggregate: legal SQL, arbitrary answer, no error
- `SUM(a * b)` (per-row product) vs `SUM(a) * b` (one row's `b` for the whole group)
- Integer cents parsed from decimal text, and `divide_half_up` for the average stock value
- Low stock as `on hand <= reorder_level`, inclusive of the boundary
- Reporting a negative on-hand explicitly rather than letting a filter hide it
- Auditing a total against an independent product-by-product loop

## How to run

```
python src/main.py --demo
python src/main.py --demo --quiet
python src/main.py --file data/movements.csv --json out.json
python src/main.py --file data/movements.csv --audit
python -m pytest tests -q
```

`--file` names the movements CSV; `products.csv` and `suppliers.csv` are read from the same
folder. Exit code `2` means the input was refused, with `error: ...` on stderr -- including
a receipt with negative units or an issue with positive ones.

## Project structure

```
Inventory_Database/
├── README.md
├── requirements.txt        # pytest==9.1.1
├── .gitignore
├── data/
│   ├── suppliers.csv       # 3 suppliers
│   ├── products.csv        # 6 products, prices as decimal text
│   └── movements.csv       # 13 signed movements: 6 in, 5 out, 2 adjustments
├── src/
│   ├── ledger.py           # every rule, query, check and the demo
│   └── main.py             # argparse only
└── tests/
    └── test_ledger.py      # 127 tests
```

## What the demo shows

| sku | product | in | out | adj | on hand | legacy |
| --- | --- | --: | --: | --: | --: | --: |
| SKU1001 | Wireless Mouse | 1 | 1 | 1 | 37 | **47** |
| SKU1002 | Mechanical Keyboard | 1 | 1 | 0 | 9 | 9 |
| SKU1003 | USB-C Cable 1m | 1 | 1 | 0 | 125 | 125 |
| SKU1004 | Notebook A5 | 1 | 1 | 0 | 180 | 180 |
| SKU1005 | Desk Lamp LED | 1 | 0 | 1 | 10 | **70** |
| SKU1006 | Office Chair | 1 | 1 | 0 | 5 | 5 |
| **total** | | 6 | 5 | 2 | **366** | **436** |

- The four SKUs with **no adjustment** agree exactly. Only the two with an adjustment are
  wrong, and each is off by twice the adjustment: `+10` for the `-5` shrinkage and `+60` for
  the `-30` write-off
- The `CASE` branch reports `436` units against a ledger of `366` -- a `70`-unit
  overstatement made of two write-offs read as receipts
- Low stock (`on hand <= reorder level`) is `SKU1002 9/10`, `SKU1005 10/15`,
  `SKU1006 5/5`; the legacy report sees `SKU1005` at 70 and drops it from the list
- The bare-column category report prices the one-product categories correctly, but
  multiplies Electronics' 46 units by one product's `499.00` and Furniture's 15 units by one
  product's `899.00`, reporting `75534.00` against a true value of `121534.00`
- `divide_half_up(12153400, 6)` gives the `20255.67` average stock value per product
- 20/20 audit checks pass, with negative controls that make the signed-sum checks fail on
  purpose

## Requirements

Python 3.10+, standard library only (`sqlite3`, `csv`, `argparse`, `re`). Tests need
pytest==9.1.1.

---
**Devender J** -- https://github.com/JDevender007
