"""Tests for the Hash Cracker project."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cracker import (  # noqa: E402
    CHARSETS,
    CrackerError,
    crack,
    hash_text,
    load_wordlist,
    mutations,
    render_result,
    run_demo,
    verify,
)
from main import main  # noqa: E402


# --------------------------------------------------------------------------- #
# Hashing
# --------------------------------------------------------------------------- #
def test_hash_text_known_values():
    assert hash_text("abc", "md5") == "900150983cd24fb0d6963f7d28e17f72"
    assert hash_text("abc", "sha1") == "a9993e364706816aba3e25717850c26c9cd0d89d"
    assert hash_text("abc", "sha256") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_hash_text_is_lowercase_hex():
    digest = hash_text("hello", "md5")
    assert digest == digest.lower()
    assert all(c in "0123456789abcdef" for c in digest)
    assert len(digest) == 32


def test_hash_text_unsupported_algo():
    with pytest.raises(CrackerError, match="unsupported algorithm"):
        hash_text("x", "blake3")


def test_verify_true_and_false():
    digest = hash_text("secret", "sha256")
    assert verify("secret", digest, "sha256") is True
    assert verify("wrong", digest, "sha256") is False


def test_verify_is_case_insensitive_on_digest():
    digest = hash_text("secret", "md5")
    assert verify("secret", digest.upper(), "md5") is True


# --------------------------------------------------------------------------- #
# Wordlist and mutations
# --------------------------------------------------------------------------- #
def test_load_default_wordlist():
    words = load_wordlist()
    assert len(words) >= 100
    assert "password" in words
    assert not any(w.startswith("#") for w in words)


def test_load_wordlist_comments_and_blanks(tmp_path):
    path = tmp_path / "wl.txt"
    path.write_text("# comment\n\nalpha\n  beta  \n", encoding="utf-8")
    assert load_wordlist(path) == ["alpha", "beta"]


def test_load_wordlist_missing(tmp_path):
    with pytest.raises(CrackerError, match="not found"):
        load_wordlist(tmp_path / "nope.txt")


def test_load_wordlist_empty(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("# nothing\n", encoding="utf-8")
    with pytest.raises(CrackerError, match="empty"):
        load_wordlist(path)


def test_mutations_include_common_forms():
    forms = list(mutations("Password"))
    assert "Password" in forms
    assert "password" in forms
    assert "PASSWORD" in forms
    assert "password1" in forms
    assert "password!" in forms
    assert any(f.startswith("@") or "$" in f for f in forms)  # leet forms


def test_mutations_dedupe_not_required_but_present():
    forms = list(mutations("abc"))
    assert "abc" in forms and "Abc" in forms


# --------------------------------------------------------------------------- #
# Brute force
# --------------------------------------------------------------------------- #
def test_brute_force_counts():
    from cracker import brute_force_candidates

    # digits, length 1-2 -> 10 + 100
    assert len(list(brute_force_candidates("ab", 2))) == 2 + 4


def test_brute_force_min_length():
    from cracker import brute_force_candidates

    assert list(brute_force_candidates("ab", 2, min_length=2)) == ["aa", "ab", "ba", "bb"]


def test_brute_force_invalid():
    from cracker import brute_force_candidates

    with pytest.raises(CrackerError, match="charset"):
        list(brute_force_candidates("", 2))
    with pytest.raises(CrackerError, match="max_length"):
        list(brute_force_candidates("ab", 1, min_length=2))


# --------------------------------------------------------------------------- #
# Cracking
# --------------------------------------------------------------------------- #
def test_crack_dictionary_finds_word():
    digest = hash_text("sunshine", "sha256")
    result = crack(digest, "sha256", mode="dictionary", time_budget_s=10.0)
    assert result.found is True
    assert result.plaintext == "sunshine"
    assert result.attempts > 0
    assert result.algo == "sha256"


def test_crack_dictionary_md5_with_mutation():
    # "qwerty123" is produced by mutating the word "qwerty"
    digest = hash_text("qwerty123", "md5")
    result = crack(digest, "md5", mode="dictionary", time_budget_s=10.0)
    assert result.found is True
    assert result.plaintext == "qwerty123"


def test_crack_bruteforce_digits():
    digest = hash_text("4827", "sha1")
    result = crack(digest, "sha1", mode="bruteforce", charset="0123456789",
                   max_length=4, time_budget_s=10.0)
    assert result.found is True
    assert result.plaintext == "4827"
    assert result.attempts <= 11_110


def test_crack_not_found_reports_honestly():
    digest = hash_text("impossible-value-xyz", "sha256")
    result = crack(digest, "sha256", mode="dictionary",
                   charset="0", max_length=1, time_budget_s=1.0)
    assert result.found is False
    assert result.plaintext == ""
    assert "NOT FOUND" in render_result(result, digest)


def test_crack_rejects_bad_digest():
    with pytest.raises(CrackerError, match="hex"):
        crack("not-hex!", "sha256")


def test_crack_rejects_bad_algo():
    with pytest.raises(CrackerError, match="unsupported"):
        crack("abc123", "blake3")


def test_crack_rejects_bad_mode():
    with pytest.raises(CrackerError, match="mode"):
        crack("abc123", "sha256", mode="telepathy")


def test_crack_custom_wordlist(tmp_path):
    path = tmp_path / "wl.txt"
    path.write_text("zebra\n", encoding="utf-8")
    digest = hash_text("zebra", "sha256")
    result = crack(digest, "sha256", wordlist=path, use_mutations=False,
                   mode="dictionary")
    assert result.found is True
    assert result.plaintext == "zebra"


def test_crack_no_mutations_mode(tmp_path):
    path = tmp_path / "wl.txt"
    path.write_text("tiger\n", encoding="utf-8")
    # "Tiger" needs the capitalize mutation; without mutations it fails
    digest = hash_text("Tiger", "sha256")
    result = crack(digest, "sha256", wordlist=path, use_mutations=False,
                   mode="dictionary")
    assert result.found is False

    result2 = crack(digest, "sha256", wordlist=path, use_mutations=True,
                    mode="dictionary")
    assert result2.found is True
    assert result2.plaintext == "Tiger"


def test_result_to_dict_shape():
    digest = hash_text("sunshine")
    payload = crack(digest, "sha256", mode="dictionary").to_dict()
    for key in ("found", "plaintext", "algo", "mode", "attempts",
                "elapsed_s", "candidates_per_s", "notes"):
        assert key in payload


def test_render_result_contains_stats():
    digest = hash_text("sunshine")
    result = crack(digest, "sha256", mode="dictionary")
    text = render_result(result, digest)
    assert "Attempts" in text
    assert "Recovered: sunshine" in text


def test_charsets_are_unique():
    for name, pool in CHARSETS.items():
        assert len(pool) == len(set(pool)), name


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Recovered: sunshine" in out
    assert "Recovered: 4827" in out


def test_cli_hash_text(capsys):
    assert main(["--hash-text", "abc", "--algo", "md5"]) == 0
    assert capsys.readouterr().out.strip() == "900150983cd24fb0d6963f7d28e17f72"


def test_cli_verify_match(capsys):
    digest = hash_text("secret")
    assert main(["--verify", "secret", digest]) == 0
    assert "MATCH" in capsys.readouterr().out


def test_cli_verify_mismatch(capsys):
    digest = hash_text("secret")
    assert main(["--verify", "wrong", digest]) == 1
    assert "NO MATCH" in capsys.readouterr().out


def test_cli_crack_success(capsys):
    digest = hash_text("sunshine")
    assert main(["--hash", digest, "--algo", "sha256", "--mode", "dictionary"]) == 0
    assert "Recovered: sunshine" in capsys.readouterr().out


def test_cli_crack_failure_exit_one(capsys):
    digest = hash_text("zzzz-not-in-wordlist")
    assert main(["--hash", digest, "--mode", "dictionary"]) == 1
    assert "NOT FOUND" in capsys.readouterr().out


def test_cli_json_output(capsys):
    import json

    digest = hash_text("sunshine")
    assert main(["--hash", digest, "--json"]) == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["found"] is True
    assert payload["plaintext"] == "sunshine"


def test_cli_no_action_errors(capsys):
    with pytest.raises(SystemExit):
        main([])
    assert "--demo" in capsys.readouterr().err


def test_cli_max_len_cap(capsys):
    digest = hash_text("x")
    assert main(["--hash", digest, "--mode", "bruteforce", "--max-len", "9"]) == 2
    assert "capped" in capsys.readouterr().err


def test_cli_bad_digest(capsys):
    assert main(["--hash", "zzzz"]) == 2
    assert "hex" in capsys.readouterr().err


def test_run_demo_direct(capsys):
    assert run_demo() == 0
    assert "offline demo" in capsys.readouterr().out
