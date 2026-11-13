"""Tests for the Named Entity Recognizer project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ner import (  # noqa: E402
    DEFAULT_GOLD,
    DEFAULT_ORGS,
    DEFAULT_PLACES,
    LABELS,
    Entity,
    NerError,
    evaluate,
    find_entities,
    load_gazetteer,
    load_gold,
    render_entities,
    render_evaluation,
    run_demo,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Entity
# --------------------------------------------------------------------------- #
def test_entity_valid_and_serializable():
    entity = Entity("Geneva", "PLACE", 5, 11)
    assert entity.length == 6
    assert entity.to_dict() == {"text": "Geneva", "label": "PLACE",
                                "start": 5, "end": 11}
    assert Entity("Geneva", "PLACE", 5, 11) == entity


def test_entity_rejects_unknown_label():
    with pytest.raises(NerError, match="unknown label"):
        Entity("Ada", "PERSON", 0, 3)


def test_entity_rejects_bad_spans_and_empty_text():
    with pytest.raises(NerError, match="invalid span"):
        Entity("x", "DATE", 3, 3)
    with pytest.raises(NerError, match="invalid span"):
        Entity("x", "DATE", -1, 4)
    with pytest.raises(NerError, match="made of integers"):
        Entity("x", "DATE", 0.5, 4)
    with pytest.raises(NerError, match="non-empty string"):
        Entity("  ", "DATE", 0, 4)


# --------------------------------------------------------------------------- #
# Gazetteers
# --------------------------------------------------------------------------- #
def test_load_bundled_gazetteers():
    places = load_gazetteer(DEFAULT_PLACES)
    orgs = load_gazetteer(DEFAULT_ORGS)
    assert len(places) >= 20 and len(orgs) >= 8
    assert "Geneva" in places and "New York City" in places
    assert "World Health Organization" in orgs
    assert len(set(places)) == len(places), "no duplicate entries"


def test_load_gazetteer_missing_file(tmp_path):
    with pytest.raises(NerError, match="gazetteer file not found"):
        load_gazetteer(tmp_path / "nope.txt")


def test_load_gazetteer_empty_file(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("\n \n", encoding="utf-8")
    with pytest.raises(NerError, match="no gazetteer entries"):
        load_gazetteer(path)


def test_load_gazetteer_rejects_lowercase_entry(tmp_path):
    path = tmp_path / "lower.txt"
    path.write_text("Geneva\nparis\n", encoding="utf-8")
    with pytest.raises(NerError, match="uppercase letter"):
        load_gazetteer(path)


# --------------------------------------------------------------------------- #
# DATE patterns
# --------------------------------------------------------------------------- #
def test_date_month_day_year():
    entities = find_entities("The event was on March 5, 1994 in Geneva.",
                             places=(), orgs=())
    dates = [e for e in entities if e.label == "DATE"]
    assert len(dates) == 1
    assert dates[0].text == "March 5, 1994"


def test_date_iso_and_slash_formats():
    text = "Files dated 2023-07-14 and 12/31/2025 were archived."
    dates = [e.text for e in find_entities(text, places=(), orgs=())
             if e.label == "DATE"]
    assert dates == ["2023-07-14", "12/31/2025"]


def test_date_month_year_and_day_first_overlap_resolution():
    text = "They met in June 2019 again."
    dates = [e.text for e in find_entities(text, places=(), orgs=())
             if e.label == "DATE"]
    assert dates == ["June 2019"]

    text = "The flight left on 15 June 2019 at noon."
    dates = [e.text for e in find_entities(text, places=(), orgs=())
             if e.label == "DATE"]
    assert dates == ["15 June 2019"], "longer day-first span must win"


def test_bare_year_is_not_a_date():
    assert find_entities("It happened in 1989 quietly.",
                         places=(), orgs=()) == []


# --------------------------------------------------------------------------- #
# MONEY patterns
# --------------------------------------------------------------------------- #
def test_money_currency_symbols():
    text = "Fees were $4.5 million, then \u20ac2,000 and finally \u00a375."
    money = [e.text for e in find_entities(text, places=(), orgs=())
             if e.label == "MONEY"]
    assert money == ["$4.5 million", "\u20ac2,000", "\u00a375"]


def test_money_scale_words():
    text = "The fund sent 12 million dollars to the project."
    money = [e.text for e in find_entities(text, places=(), orgs=())
             if e.label == "MONEY"]
    assert money == ["12 million dollars"]


def test_plain_numbers_are_not_money():
    assert find_entities("The team scored 42 points and 3 goals.",
                         places=(), orgs=()) == []


# --------------------------------------------------------------------------- #
# PLACE / ORG rules
# --------------------------------------------------------------------------- #
def test_place_longest_gazetteer_match_wins():
    entities = find_entities("In New York City today.",
                             places=load_gazetteer(DEFAULT_PLACES),
                             orgs=())
    places = [e for e in entities if e.label == "PLACE"]
    assert [p.text for p in places] == ["New York City"]


def test_org_suffix_rule():
    text = "She joined Acme Inc. and later Stanford University."
    orgs = [e.text for e in find_entities(text, places=(), orgs=())
            if e.label == "ORG"]
    assert orgs == ["Acme Inc.", "Stanford University"]


def test_org_gazetteer_never_leaks_articles():
    entities = find_entities(
        "the Bank of England announced it", places=(), orgs=("Bank of England",))
    orgs = [e for e in entities if e.label == "ORG"]
    assert [o.text for o in orgs] == ["Bank of England"]


def test_no_person_label_is_ever_produced():
    assert find_entities("Dr. Chen spoke quietly.", places=(), orgs=()) == []


def test_custom_gazetteer_parameters():
    text = "Zanzibar is nice and sunny."
    assert [e.text for e in find_entities(text, places=("Zanzibar",),
                                          orgs=())] == ["Zanzibar"]
    assert find_entities(text, places=(), orgs=()) == []


# --------------------------------------------------------------------------- #
# Whole-pipeline behaviour
# --------------------------------------------------------------------------- #
def test_entities_sorted_non_overlapping_and_sliced():
    text = ("Acme Corporation paid $4.5 million in Geneva on 2023-07-14 "
            "after the New York City office opened.")
    entities = find_entities(text)
    spans = [(e.start, e.end) for e in entities]
    assert spans == sorted(spans)
    for left, right in zip(spans, spans[1:]):
        assert left[1] <= right[0], "spans overlap"
    for entity in entities:
        assert text[entity.start:entity.end] == entity.text
        assert entity.label in LABELS
    labels = {e.label for e in entities}
    assert {"DATE", "MONEY", "PLACE", "ORG"} <= labels


def test_find_entities_rejects_bad_input():
    with pytest.raises(NerError, match="must be a string"):
        find_entities(None)
    with pytest.raises(NerError, match="must not be empty"):
        find_entities("   ")


def test_find_entities_is_deterministic():
    text = "NASA and the Bank of England met in London on 2024-01-05."
    assert find_entities(text) == find_entities(text)


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #
def test_evaluate_perfect_match():
    gold = [Entity("Geneva", "PLACE", 0, 6), Entity("2023-07-14", "DATE",
                                                    10, 20)]
    result = evaluate(gold, gold)
    assert result["micro"]["f1"] == 1.0
    assert result["micro"]["tp"] == 2
    assert result["labels"]["DATE"]["precision"] == 1.0
    assert result["labels"]["ORG"] == {"tp": 0, "fp": 0, "fn": 0,
                                       "precision": 0.0, "recall": 0.0,
                                       "f1": 0.0, "gold": 0,
                                       "predicted": 0}


def test_evaluate_empty_prediction():
    gold = [Entity("Geneva", "PLACE", 0, 6), Entity("Paris", "PLACE", 7, 12)]
    result = evaluate([], gold)
    assert result["micro"] == {"tp": 0, "fp": 0, "fn": 2,
                               "precision": 0.0, "recall": 0.0, "f1": 0.0}
    assert result["labels"]["PLACE"]["fn"] == 2


def test_evaluate_partial_math_and_deduplication():
    gold = [Entity("Geneva", "PLACE", 0, 6), Entity("2023-07-14", "DATE",
                                                    10, 20)]
    predicted = [Entity("2023-07-14", "DATE", 10, 20),
                 Entity("Acme", "ORG", 30, 34),
                 Entity("2023-07-14", "DATE", 10, 20)]
    result = evaluate(predicted, gold)
    assert result["micro"]["tp"] == 1
    assert result["micro"]["fp"] == 1
    assert result["micro"]["fn"] == 1
    assert result["micro"]["precision"] == 0.5
    assert result["micro"]["recall"] == 0.5
    assert result["micro"]["f1"] == 0.5
    assert result["labels"]["DATE"]["predicted"] == 1, "duplicates collapse"


def test_evaluate_rejects_non_entities():
    with pytest.raises(NerError, match="predicted must be a list"):
        evaluate([1], [])
    with pytest.raises(NerError, match="gold must be a list"):
        evaluate([], ["x"])


# --------------------------------------------------------------------------- #
# Gold annotations
# --------------------------------------------------------------------------- #
def test_load_gold_bundled():
    annotations = load_gold(DEFAULT_GOLD)
    assert len(annotations) == 5
    total = 0
    for item in annotations:
        assert item["text"].strip()
        for entity in item["entities"]:
            assert entity.label in LABELS
            assert item["text"][entity.start:entity.end] == entity.text
            total += 1
    assert total == 20
    labels = {e.label for item in annotations for e in item["entities"]}
    assert labels == set(LABELS)


def test_load_gold_missing_and_broken_files(tmp_path):
    with pytest.raises(NerError, match="gold file not found"):
        load_gold(tmp_path / "nope.json")
    broken = tmp_path / "broken.json"
    broken.write_text("{oops", encoding="utf-8")
    with pytest.raises(NerError, match="could not parse"):
        load_gold(broken)


def test_load_gold_schema_errors(tmp_path):
    cases = [
        ("{}", "non-empty JSON list"),
        ("[123]", "must be an object"),
        ('[{"entities": []}]', "'text' must be a non-empty string"),
        ('[{"text": "hello", "entities": {}}]', "'entities' must be a list"),
    ]
    for payload, expected in cases:
        path = tmp_path / "case.json"
        path.write_text(payload, encoding="utf-8")
        with pytest.raises(NerError, match=expected):
            load_gold(path)


def test_load_gold_entity_errors(tmp_path):
    cases = [
        ('[{"text": "hello", "entities": [{"start": 0}]}]', "missing: end"),
        ('[{"text": "hello world", "entities": '
         '[{"text": "x", "label": "DATE", "start": 0, "end": 99}]}]',
         "outside text"),
        ('[{"text": "hello world", "entities": '
         '[{"text": "nope", "label": "DATE", "start": 0, "end": 4}]}]',
         "does not match source slice"),
        ('[{"text": "hello", "entities": '
         '[{"text": "hello", "label": "PERSON", "start": 0, "end": 5}]}]',
         "unknown label"),
    ]
    for payload, expected in cases:
        path = tmp_path / "case.json"
        path.write_text(payload, encoding="utf-8")
        with pytest.raises(NerError, match=expected):
            load_gold(path)


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #
def test_render_reports():
    text = "Acme paid $5 in Geneva."
    entities = find_entities(text)
    shown = render_entities(text, entities)
    assert text in shown
    assert "Detected entities:" in shown
    assert "[MONEY]" in shown and "[PLACE]" in shown

    result = evaluate(entities, entities)
    table = render_evaluation(result)
    assert "exact span + label" in table
    assert "micro" in table
    for label in LABELS:
        assert label in table


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK:" in out
    assert "micro" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_gold(tmp_path):
    with pytest.raises(NerError, match="bundled gold"):
        run_demo(gold_path=tmp_path / "nope.json")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_twice_exits_zero(capsys):
    assert main(["--demo"]) == 0
    assert main(["--demo"]) == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_cli_text_mode(capsys):
    text = "Acme paid $5 in Geneva on 2023-07-14."
    assert main(["--text", text]) == 0
    out = capsys.readouterr().out
    assert "FILE: Inline text" in out
    assert "Detected entities:" in out
    assert "[MONEY]" in out and "[DATE ]" in out and "[PLACE]" in out


def test_cli_file_mode(tmp_path, capsys):
    path = tmp_path / "note.txt"
    path.write_text("Stanford University sits in San Francisco.\n",
                    encoding="utf-8")
    assert main(["--file", str(path)]) == 0
    out = capsys.readouterr().out
    assert "FILE: note.txt" in out
    assert "[ORG  ]" in out and "[PLACE]" in out


def test_cli_gold_mode(capsys):
    assert main(["--gold", str(DEFAULT_GOLD)]) == 0
    out = capsys.readouterr().out
    assert "exact span + label" in out
    assert "1.000" in out


def test_cli_missing_text_file_returns_two(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.txt"), "--quiet"]) == 2
    assert "text file not found" in capsys.readouterr().err


def test_cli_empty_file_returns_two(tmp_path, capsys):
    path = tmp_path / "empty.txt"
    path.write_text("   \n", encoding="utf-8")
    assert main(["--file", str(path), "--quiet"]) == 2
    assert "no text in" in capsys.readouterr().err


def test_cli_missing_gold_returns_two(tmp_path, capsys):
    assert main(["--gold", str(tmp_path / "nope.json"), "--quiet"]) == 2
    assert "gold file not found" in capsys.readouterr().err


def test_cli_empty_text_fails_fast(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--text", "  "])
    assert excinfo.value.code == 2
    assert "not be empty" in capsys.readouterr().err


def test_cli_json_output(tmp_path):
    payload_path = tmp_path / "entities.json"
    assert main(["--text", "Geneva hosts the meeting.",
                 "--json", str(payload_path), "--quiet"]) == 0
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["file"] == "Inline text"
    assert [e["label"] for e in payload["entities"]] == ["PLACE"]
    assert payload["entities"][0]["text"] == "Geneva"


def test_cli_requires_an_action(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2
    assert "--demo --file --text --gold" in capsys.readouterr().err


def test_project_ships_bundled_data():
    assert DEFAULT_GOLD.is_file()
    assert DEFAULT_PLACES.is_file()
    assert DEFAULT_ORGS.is_file()
    assert DEFAULT_GOLD.parent == PROJECT_ROOT / "data"
