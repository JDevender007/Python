"""Named entity recognizer: rules, patterns, and gazetteers - fully offline.

Detects DATE, MONEY, PLACE and ORG entities in plain text using regex
patterns (dates, money, organisation suffixes) plus bundled gazetteer
lists (places, organisations), then scores precision/recall/F1 against a
bundled annotated sample. Local files only - no network, no downloads.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_PLACES = DATA_DIR / "gazetteer_places.txt"
DEFAULT_ORGS = DATA_DIR / "gazetteer_orgs.txt"
DEFAULT_GOLD = DATA_DIR / "gold.json"

LABELS = ("DATE", "MONEY", "PLACE", "ORG")
LABEL_PRIORITY = {"DATE": 0, "MONEY": 1, "PLACE": 2, "ORG": 3}

MONTHS = ("January|February|March|April|May|June|July|August|September|"
          "October|November|December")

DATE_PATTERNS = (
    rf"\b(?:{MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}\b",
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTHS})\s+\d{{4}}\b",
    rf"\b(?:{MONTHS})\s+\d{{4}}\b",
    r"\b\d{4}-\d{2}-\d{2}\b",
    r"\b\d{1,2}/\d{1,2}/\d{4}\b",
)

MONEY_PATTERNS = (
    r"[$\u20ac\u00a3]\s?\d[\d,]*(?:\.\d+)?"
    r"(?:\s?(?:million|billion|trillion|thousand))?",
    r"\b\d[\d,]*(?:\.\d+)?(?:\s(?:million|billion|trillion|thousand))?"
    r"\s(?:dollars|euros|pounds)\b",
)

ORG_SUFFIXES = (
    "Corporation", "Association", "Commission", "Foundation",
    "University", "Institute", "Ministry", "Company", "Organization",
    "Inc.", "Ltd.", "Corp.", "Inc", "Ltd", "Corp",
    "LLC", "Bank", "Agency", "Group",
)
ORG_PATTERN = re.compile(
    r"\b((?:[A-Z][\w.\-&]*\s+){0,5}(?:" +
    "|".join(re.escape(s) for s in ORG_SUFFIXES) + r"))(?![\w])")

# Words an organisation name may not start with (article/preposition runs).
_LEADING_JUNK = frozenset({
    "The", "A", "An", "In", "On", "At", "For", "By", "With", "To", "Of",
    "And", "But", "As", "Is", "Its", "This", "That", "Meanwhile",
})


class NerError(RuntimeError):
    """Raised for invalid text, missing files, and bad annotation schemas."""


# --------------------------------------------------------------------------- #
# Entity and gazetteers
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Entity:
    """One recognised named entity: text slice + label + character span."""

    text: str
    label: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise NerError("entity text must be a non-empty string")
        if self.label not in LABELS:
            raise NerError(f"unknown label: {self.label!r} "
                           f"(expected one of {', '.join(LABELS)})")
        if isinstance(self.start, bool) or not isinstance(self.start, int) \
                or isinstance(self.end, bool) or not isinstance(self.end, int):
            raise NerError("entity span must be made of integers")
        if self.start < 0 or self.end <= self.start:
            raise NerError(
                f"invalid span [{self.start}, {self.end}) "
                f"(need 0 <= start < end)")

    @property
    def length(self) -> int:
        return self.end - self.start

    def to_dict(self) -> dict:
        return {"text": self.text, "label": self.label,
                "start": self.start, "end": self.end}


def load_gazetteer(path: str | Path) -> tuple[str, ...]:
    """Load one capitalised entry per line, preserving order, no duplicates."""
    source = Path(path)
    if not source.is_file():
        raise NerError(f"gazetteer file not found: {source}")
    entries: list[str] = []
    seen: set[str] = set()
    for number, line in enumerate(source.read_text(
            encoding="utf-8").splitlines(), start=1):
        entry = line.strip()
        if not entry:
            continue
        if not entry[0].isupper():
            raise NerError(
                f"entry on line {number} ({entry!r}) must start with an "
                f"uppercase letter")
        if entry not in seen:
            seen.add(entry)
            entries.append(entry)
    if not entries:
        raise NerError(f"no gazetteer entries in {source.name}")
    return tuple(entries)


# --------------------------------------------------------------------------- #
# Candidate generation
# --------------------------------------------------------------------------- #
def _pattern_candidates(text: str, patterns: tuple[str, ...],
                        label: str) -> list[tuple[int, int, str]]:
    found: list[tuple[int, int, str]] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            found.append((match.start(), match.end(), label))
    return found


def _gazetteer_candidates(text: str, entries: tuple[str, ...],
                          label: str) -> list[tuple[int, int, str]]:
    found: list[tuple[int, int, str]] = []
    for entry in sorted(entries, key=len, reverse=True):
        pattern = r"(?<![\w])" + re.escape(entry) + r"(?![\w])"
        for match in re.finditer(pattern, text):
            found.append((match.start(), match.end(), label))
    return found


def _org_candidates(text: str, gazetteer: tuple[str, ...]
                    ) -> list[tuple[int, int, str]]:
    found = _gazetteer_candidates(text, gazetteer, "ORG")
    for match in ORG_PATTERN.finditer(text):
        start, name = match.start(), match.group(1)
        words = name.split()
        # Never let an org span begin with an article/preposition.
        while words and words[0] in _LEADING_JUNK:
            start += len(words[0]) + 1
            words = words[1:]
        if words:
            found.append((start, start + len(" ".join(words)), "ORG"))
    return found


def find_entities(text: str,
                  places: tuple[str, ...] | None = None,
                  orgs: tuple[str, ...] | None = None) -> list[Entity]:
    """Run every rule/pattern/gazetteer detector and resolve overlaps."""
    if not isinstance(text, str):
        raise NerError(f"text must be a string, got {type(text).__name__}")
    if not text.strip():
        raise NerError("text must not be empty")
    if places is None:
        places = load_gazetteer(DEFAULT_PLACES)
    if orgs is None:
        orgs = load_gazetteer(DEFAULT_ORGS)

    candidates: list[tuple[int, int, str]] = []
    candidates += _pattern_candidates(text, DATE_PATTERNS, "DATE")
    candidates += _pattern_candidates(text, MONEY_PATTERNS, "MONEY")
    candidates += _gazetteer_candidates(text, places, "PLACE")
    candidates += _org_candidates(text, orgs)

    # Longest span wins; ties go by position then label priority.
    candidates.sort(key=lambda c: (-(c[1] - c[0]), c[0],
                                   LABEL_PRIORITY[c[2]]))
    accepted: list[tuple[int, int, str]] = []
    for start, end, label in candidates:
        if any(end > s and start < e for s, e, _ in accepted):
            continue
        accepted.append((start, end, label))

    return [Entity(text[start:end], label, start, end)
            for start, end, label in sorted(accepted)]


# --------------------------------------------------------------------------- #
# Gold annotations and evaluation
# --------------------------------------------------------------------------- #
def load_gold(path: str | Path) -> list[dict]:
    """Load annotated texts: [{'text': str, 'entities': [Entity, ...]}, ...]."""
    source = Path(path)
    if not source.is_file():
        raise NerError(f"gold file not found: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise NerError(f"could not parse {source.name}: {exc}") from exc

    if not isinstance(payload, list) or not payload:
        raise NerError(
            f"expected a non-empty JSON list of annotations in {source.name}")

    items: list[dict] = []
    for position, item in enumerate(payload):
        if not isinstance(item, dict):
            raise NerError(f"annotation {position} must be an object")
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            raise NerError(
                f"annotation {position}: 'text' must be a non-empty string")
        raw_entities = item.get("entities")
        if not isinstance(raw_entities, list):
            raise NerError(
                f"annotation {position}: 'entities' must be a list")

        entities: list[Entity] = []
        for number, raw in enumerate(raw_entities):
            if not isinstance(raw, dict):
                raise NerError(
                    f"annotation {position} entity {number} must be an object")
            missing = [k for k in ("start", "end", "label") if k not in raw]
            if missing:
                raise NerError(
                    f"annotation {position} entity {number} missing: "
                    f"{', '.join(missing)}")
            try:
                entity = Entity(str(raw.get("text", "")), raw["label"],
                                raw["start"], raw["end"])
            except NerError as exc:
                raise NerError(
                    f"annotation {position} entity {number}: {exc}") from exc
            if entity.end > len(text):
                raise NerError(
                    f"annotation {position} entity {number}: span "
                    f"[{entity.start}, {entity.end}) outside text "
                    f"(len {len(text)})")
            declared = raw.get("text")
            if isinstance(declared, str) and declared != \
                    text[entity.start:entity.end]:
                raise NerError(
                    f"annotation {position} entity {number}: text "
                    f"{declared!r} does not match source slice "
                    f"{text[entity.start:entity.end]!r}")
            entities.append(entity)
        items.append({"text": text, "entities": entities})
    return items


def evaluate(predicted: list[Entity],
             gold: list[Entity]) -> dict:
    """Exact-span precision/recall/F1 per label plus micro averages."""
    for name, group in (("predicted", predicted), ("gold", gold)):
        if not isinstance(group, list) or any(
                not isinstance(e, Entity) for e in group):
            raise NerError(f"{name} must be a list of Entity objects")

    pred_keys = {(e.start, e.end, e.label) for e in predicted}
    gold_keys = {(e.start, e.end, e.label) for e in gold}

    labels: dict[str, dict] = {}
    total_tp = total_fp = total_fn = 0
    for label in LABELS:
        tp = len({k for k in pred_keys if k[2] == label}
                 & {k for k in gold_keys if k[2] == label})
        fp = len({k for k in pred_keys if k[2] == label}
                 - {k for k in gold_keys if k[2] == label})
        fn = len({k for k in gold_keys if k[2] == label}
                 - {k for k in pred_keys if k[2] == label})
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) \
            if precision + recall else 0.0
        labels[label] = {"tp": tp, "fp": fp, "fn": fn,
                         "precision": round(precision, 4),
                         "recall": round(recall, 4),
                         "f1": round(f1, 4),
                         "gold": tp + fn, "predicted": tp + fp}
        total_tp += tp
        total_fp += fp
        total_fn += fn

    precision = total_tp / (total_tp + total_fp) if total_tp + total_fp \
        else 0.0
    recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) \
        if precision + recall else 0.0
    return {
        "labels": labels,
        "micro": {"tp": total_tp, "fp": total_fp, "fn": total_fn,
                  "precision": round(precision, 4),
                  "recall": round(recall, 4),
                  "f1": round(f1, 4)},
    }


def evaluate_texts(annotations: list[dict]) -> dict:
    """Evaluate the extractor against every loaded gold annotation."""
    predicted: list[Entity] = []
    gold: list[Entity] = []
    for item in annotations:
        predicted += find_entities(item["text"])
        gold += item["entities"]
    return evaluate(predicted, gold)


# --------------------------------------------------------------------------- #
# Reports and demo
# --------------------------------------------------------------------------- #
def render_entities(text: str, entities: list[Entity]) -> str:
    """Show the source text with an entity table underneath."""
    lines = [text, "", "Detected entities:"]
    if not entities:
        lines.append("  (none)")
    for entity in entities:
        lines.append(f"  [{entity.label:<5}] {entity.text} "
                     f"@ {entity.start}-{entity.end}")
    return "\n".join(lines)


def render_evaluation(result: dict) -> str:
    """Precision/recall/F1 table for the evaluation result."""
    lines = [
        "Evaluation against gold annotations (exact span + label):",
        "  label   gold  pred     P      R     F1",
    ]
    for label in LABELS:
        row = result["labels"][label]
        lines.append(f"  {label:<6} {row['gold']:>4} {row['predicted']:>5} "
                     f"{row['precision']:>6.3f} {row['recall']:>5.3f} "
                     f"{row['f1']:>6.3f}")
    micro = result["micro"]
    lines.append(f"  {'micro':<6} {micro['tp'] + micro['fn']:>4} "
                 f"{micro['tp'] + micro['fp']:>5} "
                 f"{micro['precision']:>6.3f} {micro['recall']:>5.3f} "
                 f"{micro['f1']:>6.3f}")
    return "\n".join(lines)


def run_demo(gold_path: str | Path | None = None,
             places_path: str | Path | None = None,
             orgs_path: str | Path | None = None) -> int:
    """Annotate the bundled sample and score against bundled gold."""
    print("=" * 68)
    print(" NAMED ENTITY RECOGNIZER - offline demo")
    print(" Rules + patterns + gazetteers; bundled gold; no network.")
    print("=" * 68)

    gold_file = Path(gold_path) if gold_path else DEFAULT_GOLD
    places_file = Path(places_path) if places_path else DEFAULT_PLACES
    orgs_file = Path(orgs_path) if orgs_path else DEFAULT_ORGS
    if not gold_file.is_file():
        raise NerError(f"bundled gold not found: {gold_file}")

    places = load_gazetteer(places_file)
    orgs = load_gazetteer(orgs_file)
    annotations = load_gold(gold_file)
    print(f"\nGold: {len(annotations)} annotated texts, "
          f"{len(places)} places, {len(orgs)} orgs")

    showcase = annotations[0]
    entities = find_entities(showcase["text"], places=places, orgs=orgs)
    print()
    print(render_entities(showcase["text"], entities))

    predicted: list[Entity] = []
    gold: list[Entity] = []
    per_item: list[list[Entity]] = []
    for item in annotations:
        found = find_entities(item["text"], places=places, orgs=orgs)
        per_item.append(found)
        predicted += found
        gold += item["entities"]
    result = evaluate(predicted, gold)
    print()
    print(render_evaluation(result))

    # --- cross-checks the demo asserts ----------------------------------- #
    micro = result["micro"]
    assert micro["precision"] >= 0.85, "precision below 0.85"
    assert micro["recall"] >= 0.85, "recall below 0.85"
    assert micro["f1"] >= 0.85, "micro F1 below 0.85"
    for item, found in zip(annotations, per_item):
        spans = [(e.start, e.end) for e in found]
        assert spans == sorted(spans), "entities must be span-sorted"
        for left, right in zip(spans, spans[1:]):
            assert left[1] <= right[0], "overlapping entities leaked"
        for entity in found:
            assert item["text"][entity.start:entity.end] == entity.text, \
                "span does not slice back to the entity text"
            assert entity.label in LABELS

    again = find_entities(showcase["text"], places=places, orgs=orgs)
    assert again == entities, "recognizer not deterministic"

    perfect = evaluate(gold, gold)
    assert perfect["micro"]["f1"] == 1.0, "perfect prediction must be 1.0"
    none = evaluate([], gold)
    assert none["micro"]["f1"] == 0.0 and none["micro"]["fn"] > 0

    print(f"\nCross-checks OK: micro P {micro['precision']:.3f} / "
          f"R {micro['recall']:.3f} / F1 {micro['f1']:.3f} "
          f"(threshold 0.85), spans slice back, no overlaps, "
          "deterministic re-run, metrics sanity-checked")
    print("Demo completed successfully.")
    return 0
