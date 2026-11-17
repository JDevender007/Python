"""Tests for the Tiny Transformer LM project."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lm import (  # noqa: E402
    DEMO_CORPUS,
    MIN_CORPUS_CHARS,
    LmError,
    CharTokenizer,
    TinyGPT,
    build_model,
    load_corpus,
    render_report,
    run_demo,
    train_lm,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
def _corpus(repeat: str = "the lighthouse keeper waited. ") -> str:
    """A synthetic corpus comfortably above the minimum size."""
    text = (repeat * ((MIN_CORPUS_CHARS // len(repeat)) + 1))[:800]
    return text


@pytest.fixture(scope="module")
def trained():
    # Small model + few steps keeps the suite fast; the demo covers training
    return train_lm(load_corpus(DEMO_CORPUS), steps=40, batch_size=16,
                    block_size=16, d_model=32, n_layer=1, n_head=2, seed=5)


# --------------------------------------------------------------------------- #
# Corpus loading
# --------------------------------------------------------------------------- #
def test_load_bundled_corpus():
    text = load_corpus(DEMO_CORPUS)
    assert len(text) >= 10000
    assert MIN_CORPUS_CHARS <= len(text)
    assert "lighthouse" in text
    assert text.strip()


def test_load_missing_file(tmp_path):
    with pytest.raises(LmError, match="not found"):
        load_corpus(tmp_path / "nope.txt")


def test_load_empty_file(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("", encoding="utf-8")
    with pytest.raises(LmError, match="corpus is empty"):
        load_corpus(path)


def test_load_whitespace_only(tmp_path):
    path = tmp_path / "blank.txt"
    path.write_text("  \n\t\n", encoding="utf-8")
    with pytest.raises(LmError, match="corpus is empty"):
        load_corpus(path)


def test_load_too_small(tmp_path):
    path = tmp_path / "small.txt"
    path.write_text("too small", encoding="utf-8")
    with pytest.raises(LmError, match="corpus too small"):
        load_corpus(path)


# --------------------------------------------------------------------------- #
# Character tokenizer
# --------------------------------------------------------------------------- #
def test_tokenizer_vocab():
    tok = CharTokenizer("banana band")
    assert tok.vocab_size == len(set("banana band"))
    assert tok.chars == sorted(set("banana band"))
    assert tok.stoi["b"] == tok.chars.index("b")


def test_tokenizer_roundtrip():
    tok = CharTokenizer(_corpus())
    text = "the keeper waited."
    assert tok.decode(tok.encode(text)) == text


def test_tokenizer_unknown_character():
    tok = CharTokenizer(_corpus())
    with pytest.raises(LmError, match="not in vocabulary"):
        tok.encode("hello \u2603")


def test_tokenizer_empty_text():
    with pytest.raises(LmError, match="empty"):
        CharTokenizer("")


def test_tokenizer_decode_unknown_id(trained):
    with pytest.raises(LmError, match="unknown token id"):
        trained.tokenizer.decode([9999])


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
def test_build_model_is_seeded():
    first = build_model(40, block_size=16, d_model=32, seed=5)
    second = build_model(40, block_size=16, d_model=32, seed=5)
    for a, b in zip(first.parameters(), second.parameters()):
        assert torch.equal(a, b)


def test_model_output_shape(trained):
    x = torch.randint(0, trained.tokenizer.vocab_size, (4, 10))
    out = trained.model(x)
    assert out.shape == (4, 10, trained.tokenizer.vocab_size)


def test_model_rejects_bad_head_split():
    with pytest.raises(LmError, match="divisible"):
        TinyGPT(vocab_size=10, d_model=30, n_head=4)


def test_model_rejects_bad_block_size():
    with pytest.raises(LmError, match="block_size"):
        TinyGPT(vocab_size=10, block_size=4)


def test_model_rejects_bad_layers():
    with pytest.raises(LmError, match="n_layer"):
        TinyGPT(vocab_size=10, n_layer=0)


def test_model_rejects_bad_vocab():
    with pytest.raises(LmError, match="vocab_size"):
        TinyGPT(vocab_size=1)


def test_attention_is_causal():
    """Changing future tokens must not change earlier logits."""
    model = build_model(25, block_size=16, d_model=32, n_head=2, n_layer=2,
                        seed=3)
    torch.manual_seed(11)
    x1 = torch.randint(0, 25, (1, 8))
    x2 = x1.clone()
    x2[0, 5:] = (x2[0, 5:] + 1) % 25
    model.eval()
    with torch.no_grad():
        y1, y2 = model(x1), model(x2)
    assert torch.allclose(y1[0, :5], y2[0, :5], atol=1e-5), \
        "earlier positions leaked future information"
    assert not torch.allclose(y1[0, 7], y2[0, 7], atol=1e-3), \
        "future change had no effect at all"


def test_model_rejects_overlong_sequence(trained):
    with pytest.raises(LmError, match="exceeds block size"):
        trained.model(torch.zeros(1, 64, dtype=torch.long))


# --------------------------------------------------------------------------- #
# Training
# --------------------------------------------------------------------------- #
def test_train_quick_on_bundled_corpus():
    result = train_lm(load_corpus(DEMO_CORPUS), steps=10, block_size=16,
                      d_model=32, n_layer=1, seed=1)
    assert len(result.history) == 10
    assert math.isfinite(result.final_loss)
    assert result.final_loss < 10.0
    assert result.corpus_chars >= MIN_CORPUS_CHARS


def test_train_loss_decreases():
    result = train_lm(_corpus(), steps=60, batch_size=16, block_size=16,
                      d_model=32, n_layer=1, lr=3e-3, seed=2)
    assert result.final_loss < result.initial_loss - 0.2, \
        "loss did not fall on a repetitive corpus"


def test_train_is_deterministic():
    text = load_corpus(DEMO_CORPUS)
    first = train_lm(text, steps=8, block_size=16, d_model=32, n_layer=1,
                     seed=9)
    second = train_lm(text, steps=8, block_size=16, d_model=32, n_layer=1,
                      seed=9)
    assert first.history == second.history


def test_train_seed_changes_history():
    text = load_corpus(DEMO_CORPUS)
    first = train_lm(text, steps=8, block_size=16, d_model=32, n_layer=1,
                     seed=1)
    second = train_lm(text, steps=8, block_size=16, d_model=32, n_layer=1,
                      seed=2)
    assert first.history != second.history


def test_train_rejects_bad_steps():
    with pytest.raises(LmError, match="steps must be >= 1"):
        train_lm(_corpus(), steps=0)


def test_train_rejects_bad_batch():
    with pytest.raises(LmError, match="batch_size"):
        train_lm(_corpus(), batch_size=0)


def test_train_rejects_bad_block():
    with pytest.raises(LmError, match="block_size must be >= 8"):
        train_lm(_corpus(), block_size=2)


def test_train_rejects_bad_lr():
    with pytest.raises(LmError, match="lr must be > 0"):
        train_lm(_corpus(), lr=0.0)


def test_train_rejects_nan_lr():
    with pytest.raises(LmError, match="lr must be > 0"):
        train_lm(_corpus(), lr=float("nan"))


def test_train_rejects_small_corpus():
    with pytest.raises(LmError, match="at least 500 characters"):
        train_lm("abc", steps=5)


def test_train_rejects_block_larger_than_corpus():
    with pytest.raises(LmError, match="too short for block_size"):
        train_lm(_corpus(), steps=5, block_size=700)


def test_train_rejects_bad_head_split():
    with pytest.raises(LmError, match="divisible"):
        train_lm(_corpus(), steps=5, d_model=30, n_head=4)


# --------------------------------------------------------------------------- #
# Sampling
# --------------------------------------------------------------------------- #
def test_sample_length_and_prompt(trained):
    text = trained.sample("The ", length=40, temperature=0.8, top_k=8,
                          seed=7)
    assert text.startswith("The ")
    assert len(text) == 4 + 40


def test_sample_empty_prompt(trained):
    text = trained.sample("", length=25, seed=1)
    assert len(text) == 25


def test_sample_stays_in_vocab(trained):
    text = trained.sample("The ", length=60, temperature=1.0, top_k=5,
                          seed=3)
    assert set(text) <= set(trained.tokenizer.chars)


def test_sample_is_deterministic(trained):
    a = trained.sample("The ", length=30, temperature=1.0, top_k=8, seed=4)
    b = trained.sample("The ", length=30, temperature=1.0, top_k=8, seed=4)
    assert a == b


def test_sample_seed_changes_output(trained):
    a = trained.sample("The ", length=30, temperature=1.0, top_k=8, seed=4)
    b = trained.sample("The ", length=30, temperature=1.0, top_k=8, seed=5)
    assert a != b


def test_sample_top_k_clamped_to_vocab(trained):
    text = trained.sample("The ", length=20, top_k=100000, seed=0)
    assert len(text) == 24
    assert set(text) <= set(trained.tokenizer.chars)


def test_sample_rejects_bad_length(trained):
    with pytest.raises(LmError, match="length must be >= 1"):
        trained.sample("The ", length=0)


def test_sample_rejects_bad_temperature(trained):
    with pytest.raises(LmError, match="temperature must be > 0"):
        trained.sample("The ", temperature=0.0)
    with pytest.raises(LmError, match="temperature must be > 0"):
        trained.sample("The ", temperature=-1.0)


def test_sample_rejects_bad_top_k(trained):
    with pytest.raises(LmError, match="top_k must be >= 1"):
        trained.sample("The ", top_k=0)


def test_sample_rejects_unknown_prompt(trained):
    with pytest.raises(LmError, match="not in vocabulary"):
        trained.sample("\u2603", length=10)


def test_sample_rejects_long_prompt(trained):
    with pytest.raises(LmError, match="exceeds block size"):
        trained.sample("The keeper waited.", length=10)


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def test_render_report_sections(trained):
    text = render_report(trained)
    assert "TINY TRANSFORMER LM" in text
    assert "Corpus" in text and "Model" in text and "Training" in text
    assert "Final loss" in text


def test_result_to_dict(trained):
    payload = trained.to_dict()
    json.dumps(payload)
    assert payload["steps"] == 40
    assert payload["vocab_size"] == trained.tokenizer.vocab_size
    assert payload["final_loss"] < payload["initial_loss"] + 1e-9
    assert payload["block_size"] == 16


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out
    assert "Generated from prompt" in out


def test_run_demo_is_idempotent(capsys):
    assert main(["--demo", "--quiet"]) == 0
    assert main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""

    assert main(["--demo"]) == 0
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert out.count("Demo completed successfully.") == 2
    assert out.count("Cross-checks OK") == 2


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_file_training(capsys):
    assert main(["--file", str(DEMO_CORPUS), "--steps", "5"]) == 0
    out = capsys.readouterr().out
    assert "Final loss" in out


def test_cli_prompt_generation(capsys):
    assert main(["--prompt", "The ", "--steps", "5", "--length", "30",
                 "--quiet"]) == 0
    out = capsys.readouterr().out
    assert "Generated from prompt 'The '" in out


def test_cli_json_output(tmp_path, capsys):
    payload_path = tmp_path / "gen.json"
    assert main(["--file", str(DEMO_CORPUS), "--steps", "5",
                 "--prompt", "The ", "--length", "12",
                 "--json", str(payload_path), "--quiet"]) == 0
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["training"]["steps"] == 5
    assert payload["prompt"] == "The "
    assert payload["generated"].startswith("The ")
    assert len(payload["generated"]) == 4 + 12


def test_cli_requires_action():
    with pytest.raises(SystemExit):
        main([])


def test_cli_missing_file(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.txt"), "--steps",
                 "5"]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_small_corpus(tmp_path, capsys):
    path = tmp_path / "small.txt"
    path.write_text("tiny", encoding="utf-8")
    assert main(["--file", str(path), "--steps", "5"]) == 2
    assert "corpus too small" in capsys.readouterr().err


def test_cli_bad_steps_fails_fast(capsys):
    # validated BEFORE the corpus is even loaded
    assert main(["--file", str(tmp_path_missing()), "--steps", "0"]) == 2
    assert "steps must be >= 1" in capsys.readouterr().err


def test_cli_bad_temperature_fails_fast(capsys):
    assert main(["--file", str(tmp_path_missing()),
                 "--temperature", "0"]) == 2
    assert "temperature must be > 0" in capsys.readouterr().err


def test_cli_bad_top_k(capsys):
    assert main(["--file", str(DEMO_CORPUS), "--top-k", "0", "--steps",
                 "5"]) == 2
    assert "top-k must be >= 1" in capsys.readouterr().err


def test_cli_unknown_prompt_char(capsys):
    # prompt vocabulary check runs before training starts
    assert main(["--prompt", "\u2603", "--steps", "5", "--quiet"]) == 2
    assert "not in vocabulary" in capsys.readouterr().err


def test_cli_bad_length(capsys):
    assert main(["--file", str(DEMO_CORPUS), "--length", "0", "--steps",
                 "5"]) == 2
    assert "length must be >= 1" in capsys.readouterr().err


def test_project_has_sample_data():
    assert DEMO_CORPUS.is_file()
    assert DEMO_CORPUS.parent == PROJECT_ROOT / "data"
    assert len(load_corpus(DEMO_CORPUS)) >= 10000


def tmp_path_missing() -> Path:
    """A path that certainly does not exist (for fail-fast checks)."""
    return PROJECT_ROOT / "data" / "__missing__.txt"
