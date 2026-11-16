<div align="center">

# 🌡️ Weather API Client

### The legacy reader was `payload["main"]["temp"] - 273.15`, wrapped in `except (KeyError, TypeError): return 0.0`. So a `null`, a quoted string or a missing object all became **0.0 degrees** — a reading — and a Celsius body was converted as if it were Kelvin, giving **-251.59 C**.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

```python
def get_temperature(payload):
    try:
        return payload["main"]["temp"] - 273.15
    except (KeyError, TypeError):
        return 0.0
```

**1 → The fallback is a reading.** `0.0` is a temperature. When the server sends no
`main` object, a `null`, or a quoted string, the legacy reader does not report "I could
not read this" — it reports **0.0 degrees**, which a dashboard draws at freezing point.
Three of the nine bundled bodies come back as exactly that:

```text
null-temp          0.00 C
string-temp        0.00 C
no-main            0.00 C
3 of 9 bodies come back as exactly 0.00 C
```

**2 → `- 273.15` is a unit conversion, not arithmetic.** The body says `"units": "metric"`,
so the number is already Celsius. Subtracting 273.15 turns `21.555` into **-251.59 C** —
and an imperial body into `-202.45 C`. The only warning is that the number is absurd, and
a dashboard has no absurdity check:

```text
metric          -251.59 C
imperial        -202.45 C
```

**3 → A JSON float is not the number the server sent.** The body says `21.555`.
`json.loads` gives the nearest binary double, whose exact value is below the tie:

```text
json.loads            -> float    21.555
its exact value       -> 21.55499999999999971578290569595...
x 100, exactly        -> 2155.499999999999971578290570...
int(...), as many do  -> 2155
parse_float=Decimal   -> Decimal  21.555
x 100, rounded half-up-> 2156
hundredths kept: 2156 from the digits, 2155 from the double
```

One hundredth, silently, and the honest fix is not "round more" — it is
`json.loads(text, parse_float=Decimal)`, so the digits the server wrote arrive intact.

**4 → `KeyError` is not the only shape of "no value".** A missing key, an explicit `null`
and a string all reach the same `except`. They are three different failures and they get
three different sentences, not one `0.0`.

**5 → A temperature has a floor.** Absolute zero is -273.15 C. A body reporting -300 C is
not cold, it is broken — the legacy reader accepts it and returns **-573.15**.

| body | legacy | here |
|---|---|---|
| `metric`, `21.555` | `-251.59 C` | `21.56 C`, 2156 hundredths |
| `standard`, `294.65` | `21.50 C` (right by accident) | `21.50 C` |
| `imperial`, `70.7` | `-202.45 C` | `21.50 C` |
| `"temp": null` | `0.00 C` | refused: a missing reading is not 0.0 |
| `"temp": "21.555"` | `0.00 C` | refused: a temperature is a number |
| `{"cod": "404"}` | `0.00 C` | refused: cod '404', city not found |
| `-300.0` | `-573.15 C` | refused: colder than absolute zero |
| no `humidity` | not read | `None`, printed as `-` |
| a truncated body | never ran | refused at the character it stopped |

The demonstration is offline: one bundled file of nine response bodies exactly as a server
would send them. Standard library only: no `requests`, no HTTP client, no API key.

---

# ✨ Features

- `Temperature` — **whole hundredths of a degree Celsius**, validated at construction,
  ordered, with `in_unit()`, `text(unit)`, `celsius_text()`
- `from_unit` / `in_unit` — Celsius, Kelvin and Fahrenheit converted **in integers only**,
  so a reading prints and reads back to the same hundredth
- `divide_half_up` — half away from zero, written out, because `round(2.5)` is 2
- `to_hundredths` — a `Decimal` to whole hundredths, half-up, refusing a `float`
- `decode` — `json.loads(..., parse_float=Decimal)`, so the digits survive
- `parse_temperature` — an integer, a `Decimal`, or a `float` (the binary value, recorded
  as such), and a named refusal for `null`, a string, a bool and a list
- `parse_humidity` — an optional percentage, `None` staying `None` rather than 0
- `legacy_temperature` — the three legacy lines, executable, so the demo refutes them
- `read_observation` — one body in, one `Observation` out, a broken body kept as a sentence
- `Table` — nine bodies with `readings()`, `refusals()`, `warmest()`, `coldest()`, `by_name()`
- `parse_blocks` — `--- name` then a body, line-numbered errors
- `audit` — nine named checks with a guard, and `loads` injected so a negative control can
  hand in a decoder that turns every number into a double
- CLI: `--readings`, `--body`, `--audit`, `--json`, `--quiet`, `--demo`
- 167 passing pytest tests

---

# 📂 Folder Structure

```text
Weather_API_Client/
│
├── src/
│   ├── main.py         # CLI: the bundle, one body, the audit
│   └── observations.py # temperatures, units, decoding, the legacy reader, the audit
│
├── tests/
│   └── test_observations.py
│
├── data/
│   └── readings.txt  # nine bodies: metric, kelvin, imperial, null, string, 404, cold...
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 08_API_Development/Weather_API_Client

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: the decoder, the nine bodies, the legacy reader, the checks
python src/main.py --demo

# Read the bundled bodies
python src/main.py

# Read one body given on the command line
python src/main.py --body '{"units": "metric", "main": {"temp": 21.555, "humidity": 61}}'

# Every check
python src/main.py --audit

# The reading as JSON
python src/main.py --json reading.json

# Your own bundle
python src/main.py --readings .\readings.txt
```

**Exit codes:** `0` = the command ran · `1` = an audit check failed · `2` = a body that
cannot be read, a missing file, or a bundle with a body before its first header.

---

# ⚙️ How It Works

```text
decode(text)                       json.loads(..., parse_float=Decimal)
  └── 21.555 stays 21.555, not 21.55499999999999971578...

_read_fields(payload)
  ├── not a dict            -> refused: a response is a JSON object
  ├── "cod" present, != 200 -> refused: the response is an error, cod '404'
  ├── "units" unknown       -> refused: names units 'rankine'
  ├── no "main"             -> refused: carries no reading
  ├── no "temp"             -> refused: 'main' carries no 'temp' field
  ├── parse_temperature     -> whole hundredths, or a sentence
  └── parse_humidity        -> None, a percentage, or a sentence

Temperature.in_unit(unit)
  ├── celsius    -> as stored
  ├── kelvin     -> + 27315 hundredths
  └── fahrenheit -> * 9 / 5 (half-up) + 3200 hundredths
```

Details worth knowing:

- **A temperature is one number.** `21.56 C`, `294.71 K` and `70.81 F` are one
  `Temperature`, so the three cannot be added together by accident and a comparison never
  needs a unit.
- **Hundredths, not floats.** Every conversion is integer arithmetic, so a reading prints
  in all three units and reads back to the same hundredth — the audit re-derives that for
  every row instead of trusting the print.
- **`parse_float=Decimal` is the fix, not more rounding.** The binary double for `21.555`
  is *below* the tie, so no rounding rule recovers 2156 from it. Only the digits do.
- **A `float` is still accepted, and still wrong.** `parse_temperature(21.555)` gives 2155
  and the docstring says so: the reader does not pretend the binary value is the literal.
- **`None` is not `0 %`.** A body with no `humidity` prints `-`, and the audit fails if it
  ever prints `0%`.
- **Absolute zero is a hard floor.** `Temperature` refuses anything colder at
  construction, so no code path can carry a temperature that cannot exist.
- **A broken body is a sentence, not an exception.** One unreadable body does not throw
  away the other eight, and `--json` records every refusal with its reason.
- **A broken body is a `FAIL`.** Every audit check runs behind a guard, because a negative
  control plants the defect exactly where the check looks.

---

# 🧪 Technologies

- Python 3 standard library: `json`, `decimal`, `dataclasses`, `pathlib`, `argparse`,
  `contextlib`
- pytest 9.1.1

No `requests`, no HTTP client, no network, no API key.

---

# 📚 Concepts Covered

- A JSON number as a decimal literal, and the binary double `json.loads` makes of it
- `parse_float=Decimal`, and why more rounding cannot recover a digit that was lost
- Half-up rounding written out, against `round()` and its even neighbour
- A quantity stored in integer hundredths, and unit conversion by integer arithmetic
- A unit a response **names**, instead of one the code assumes
- "Missing" in its four shapes: a missing key, a `null`, a string, and a non-object
- An optional field whose absence is `None` rather than a zero
- A physical floor that refuses an impossible value at construction
- Error envelopes: an HTTP body that carries `cod` and `message` instead of a reading
- Audits with an injected decoder, so a check can be shown to test something

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**167 tests passed** covering half-up division and its five refusals, `to_hundredths`,
both decoders and the one-hundredth they disagree by, `Temperature` construction and the
absolute-zero floor, all three conversions and their round trips, every accepted and
refused `temp` and `humidity` shape, the eight legacy behaviours, `Observation` lines,
fifteen body refusals, `Table` accessors, the nine bundled counts, the block parser and
its six errors, nine audit checks with eight negative controls, the demo, and every CLI
mode including six exit-code-2 paths.

---

# 🎯 Learning Outcomes

- Decode a JSON body with `parse_float=Decimal`, so a number means what it says
- Explain why `int(x * 100)` is not a rounding rule
- Store a measurement in integer hundredths, and convert units without a float
- Read the unit a response names instead of assuming one
- Tell "no value" from a value in four different shapes, and refuse each by name
- Keep an optional reading as `None`, and print the absence rather than a zero
- Refuse a value that cannot physically exist, at construction
- Recognise an error envelope inside a body

---

# 🚀 Future Improvements

- A `units=metric` request builder, so the unit is chosen rather than read
- Time zones for the `dt` field, reusing the instant lab from `07_Web_Scraping`
- A tolerance, so two readings that differ by one hundredth compare as equal
- A second provider, so the field names become a strategy rather than a path
- A retry policy for the 429 body, reusing the retry lab from `REST_API_with_FastAPI`

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
