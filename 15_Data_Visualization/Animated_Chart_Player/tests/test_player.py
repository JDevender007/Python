"""Tests for the Animated Chart Player project."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
import pandas as pd
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from player import (  # noqa: E402
    ANIMATIONS,
    DEMO_CSV,
    REQUIRED_COLUMNS,
    PlayerError,
    build_animation,
    gif_frame_count,
    load_scores,
    render_animation,
    rankings_at,
    run_demo,
    scores_through,
    teams,
    weeks,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_ANIMS = {"line", "bar", "area"}

# some tests build animations without saving them (by design)
pytestmark = pytest.mark.filterwarnings(
    "ignore:Animation was deleted without rendering")


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
def _csv(tmp_path: Path, rows: list[dict], name: str = "scores.csv") -> Path:
    path = tmp_path / name
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _grid(teams_scores: dict[str, list[float]]) -> list[dict]:
    """Build rows from {team: [week1_score, week2_score, ...]}."""
    rows = []
    for team, values in teams_scores.items():
        for week, score in enumerate(values, start=1):
            rows.append({"week": week, "team": team, "score": score})
    return rows


@pytest.fixture(scope="module")
def sample() -> pd.DataFrame:
    return load_scores(DEMO_CSV)


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def test_load_bundled_sample(sample):
    assert len(sample) == 48
    assert list(sample.columns) == list(REQUIRED_COLUMNS)
    assert sample["team"].nunique() == 4
    assert sample["week"].nunique() == 12
    assert not sample.duplicated(subset=["week", "team"]).any()
    assert sorted(sample["week"].unique()) == list(range(1, 13))


def test_load_missing_file(tmp_path):
    with pytest.raises(PlayerError, match="not found"):
        load_scores(tmp_path / "nope.csv")


def test_load_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("week,score\n1,10\n", encoding="utf-8")
    with pytest.raises(PlayerError, match="missing column"):
        load_scores(path)


def test_load_empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text(",".join(REQUIRED_COLUMNS) + "\n", encoding="utf-8")
    with pytest.raises(PlayerError, match="no rows"):
        load_scores(path)


def test_load_empty_team(tmp_path):
    rows = _grid({"A": [1, 2], "B": [3, 4]})
    rows[0]["team"] = ""
    with pytest.raises(PlayerError, match="empty team"):
        load_scores(_csv(tmp_path, rows))


def test_load_non_numeric_week(tmp_path):
    rows = _grid({"A": [1, 2], "B": [3, 4]})
    rows[0]["week"] = "first"
    with pytest.raises(PlayerError, match="'week' contains non-numeric"):
        load_scores(_csv(tmp_path, rows))


def test_load_fractional_week(tmp_path):
    rows = _grid({"A": [1, 2], "B": [3, 4]})
    rows[0]["week"] = 1.5
    with pytest.raises(PlayerError, match="whole numbers"):
        load_scores(_csv(tmp_path, rows))


def test_load_non_numeric_score(tmp_path):
    rows = _grid({"A": [1, 2], "B": [3, 4]})
    rows[0]["score"] = "high"
    with pytest.raises(PlayerError, match="'score' contains non-numeric"):
        load_scores(_csv(tmp_path, rows))


def test_load_infinite_score(tmp_path):
    rows = _grid({"A": [1, 2], "B": [3, 4]})
    rows[0]["score"] = float("inf")
    with pytest.raises(PlayerError, match="finite"):
        load_scores(_csv(tmp_path, rows))


def test_load_duplicate_week_team(tmp_path):
    rows = _grid({"A": [1, 2], "B": [3, 4]})
    rows.append(dict(rows[0], score=99))
    with pytest.raises(PlayerError, match="duplicate"):
        load_scores(_csv(tmp_path, rows))


def test_load_incomplete_timeline(tmp_path):
    # team B misses week 2
    rows = _grid({"A": [1, 2], "B": [3]})
    with pytest.raises(PlayerError, match="every team needs every week.*B"):
        load_scores(_csv(tmp_path, rows))


def test_load_single_team(tmp_path):
    rows = _grid({"A": [1, 2]})
    with pytest.raises(PlayerError, match="at least two teams"):
        load_scores(_csv(tmp_path, rows))


def test_load_single_week(tmp_path):
    rows = [{"week": 1, "team": "A", "score": 1.0},
            {"week": 1, "team": "B", "score": 2.0}]
    with pytest.raises(PlayerError, match="at least two weeks"):
        load_scores(_csv(tmp_path, rows))


def test_load_all_negative_scores(tmp_path):
    rows = _grid({"A": [-1, -2], "B": [-3, -4]})
    with pytest.raises(PlayerError, match="negative"):
        load_scores(_csv(tmp_path, rows))


# --------------------------------------------------------------------------- #
# Frame data helpers
# --------------------------------------------------------------------------- #
def test_weeks_and_teams(sample):
    assert weeks(sample) == list(range(1, 13))
    assert teams(sample) == sorted(sample["team"].unique())
    assert len(teams(sample)) == 4


def test_scores_through_lengths(sample):
    for week in weeks(sample):
        data = scores_through(sample, week)
        assert all(len(values) == week for values in data.values())
        assert set(data) == set(teams(sample))


def test_scores_through_values_match_sample(sample):
    data = scores_through(sample, 3)
    for team, values in data.items():
        expected = sample[(sample["team"] == team)
                          & (sample["week"] <= 3)].sort_values("week")["score"]
        assert values == list(expected)


def test_rankings_are_sorted_descending(sample):
    ranking = rankings_at(sample, 12)
    scores = [score for _, score in ranking]
    assert scores == sorted(scores, reverse=True)
    assert len(ranking) == 4


def test_rankings_match_manual_sort(sample):
    week = 7
    manual = sorted(
        ((str(t), float(s)) for t, s in
         sample[sample["week"] == week][["team", "score"]].values),
        key=lambda pair: (-pair[1], pair[0]))
    assert rankings_at(sample, week) == manual


def test_rankings_tie_broken_by_name(tmp_path):
    rows = _grid({"Alpha": [5.0, 5.0], "Beta": [3.0, 5.0]})
    frame = load_scores(_csv(tmp_path, rows))
    # tied at week 2: alphabetical order breaks the tie
    assert rankings_at(frame, 2) == [("Alpha", 5.0), ("Beta", 5.0)]


# --------------------------------------------------------------------------- #
# Animation building
# --------------------------------------------------------------------------- #
def test_registry_contains_expected_animations():
    assert set(ANIMATIONS) == EXPECTED_ANIMS
    for name, (builder, description) in ANIMATIONS.items():
        assert callable(builder), name
        assert description


@pytest.mark.parametrize("name", sorted(EXPECTED_ANIMS))
def test_build_animation_returns_funcanimation(sample, name):
    from matplotlib.animation import FuncAnimation
    animation = build_animation(name, sample)
    assert isinstance(animation, FuncAnimation)
    assert animation._func is not None
    plt.close(animation._fig)


def test_build_animation_unknown_name(sample):
    with pytest.raises(PlayerError, match="unknown animation.*available"):
        build_animation("spiral", sample)
    assert plt.get_fignums() == []


def test_build_animation_closes_cleanly(sample):
    for name in EXPECTED_ANIMS:
        animation = build_animation(name, sample)
        plt.close(animation._fig)
    assert plt.get_fignums() == []


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", sorted(EXPECTED_ANIMS))
def test_render_animation_writes_gif(tmp_path, sample, name):
    path = render_animation(name, sample, tmp_path / "out" / f"{name}.gif")
    assert path.is_file()
    assert path.stat().st_size > 5_000
    assert gif_frame_count(path) == 12  # one frame per week
    assert plt.get_fignums() == [], f"figure leaked for {name}"


def test_render_animation_renders_twice_idempotent(tmp_path, sample):
    target = tmp_path / "line.gif"
    first = render_animation("line", sample, target)
    size = first.stat().st_size
    second = render_animation("line", sample, target)
    assert second.stat().st_size == size  # deterministic re-render


def test_render_animation_rejects_bad_fps(tmp_path, sample):
    with pytest.raises(PlayerError, match="fps"):
        render_animation("line", sample, tmp_path / "x.gif", fps=0)
    with pytest.raises(PlayerError, match="fps"):
        render_animation("line", sample, tmp_path / "x.gif", fps=99)


def test_render_animation_unknown_name(tmp_path, sample):
    with pytest.raises(PlayerError, match="unknown animation"):
        render_animation("spin", sample, tmp_path / "x.gif")
    assert plt.get_fignums() == []


def test_gif_frame_count_on_missing_file(tmp_path):
    with pytest.raises(Exception):
        gif_frame_count(tmp_path / "absent.gif")


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(tmp_path, capsys):
    out_dir = tmp_path / "gifs"
    assert run_demo(out_dir=out_dir) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    assert "4 teams x 12 weeks" in out
    assert len(list(out_dir.glob("*.gif"))) == 3
    for name in EXPECTED_ANIMS:
        assert (out_dir / f"{name}.gif").is_file()


def test_run_demo_is_idempotent(tmp_path, capsys):
    out_dir = tmp_path / "gifs"
    assert run_demo(out_dir=out_dir) == 0
    assert run_demo(out_dir=out_dir) == 0
    out = capsys.readouterr().out
    assert out.count("Demo completed successfully.") == 2
    assert len(list(out_dir.glob("*.gif"))) == 3  # overwritten, not doubled


def test_run_demo_quiet(tmp_path, capsys):
    assert run_demo(out_dir=tmp_path / "q", quiet=True) == 0
    assert capsys.readouterr().out == ""


def test_run_demo_missing_sample(tmp_path, monkeypatch):
    import player
    monkeypatch.setattr(player, "DEMO_CSV", tmp_path / "absent.csv")
    with pytest.raises(PlayerError, match="bundled sample"):
        player.run_demo(out_dir=tmp_path / "x")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(tmp_path, capsys):
    out_dir = tmp_path / "cli"
    assert main(["--demo", "--out", str(out_dir)]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert len(list(out_dir.glob("*.gif"))) == 3


def test_cli_demo_quiet(tmp_path, capsys):
    assert main(["--demo", "--out", str(tmp_path / "q"), "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_file_renders_all(tmp_path, capsys):
    out_dir = tmp_path / "all"
    assert main(["--file", str(DEMO_CSV), "--out", str(out_dir)]) == 0
    out = capsys.readouterr().out
    assert "Done." in out
    assert len(list(out_dir.glob("*.gif"))) == 3


def test_cli_single_animation(tmp_path, capsys):
    out_dir = tmp_path / "one"
    assert main(["--file", str(DEMO_CSV), "--anim", "bar",
                 "--out", str(out_dir)]) == 0
    out = capsys.readouterr().out
    assert "bar" in out
    assert (out_dir / "bar.gif").is_file()
    assert not (out_dir / "line.gif").exists()


def test_cli_custom_fps(tmp_path, capsys):
    out_dir = tmp_path / "fps"
    assert main(["--file", str(DEMO_CSV), "--anim", "line", "--fps", "8",
                 "--out", str(out_dir)]) == 0
    assert gif_frame_count(out_dir / "line.gif") == 12


def test_cli_bad_fps(tmp_path, capsys):
    assert main(["--file", str(DEMO_CSV), "--fps", "0",
                 "--out", str(tmp_path)]) == 2
    assert "--fps" in capsys.readouterr().err


def test_cli_unknown_animation(tmp_path, capsys):
    assert main(["--file", str(DEMO_CSV), "--anim", "spiral",
                 "--out", str(tmp_path)]) == 2
    assert "unknown animation" in capsys.readouterr().err


def test_cli_list(capsys):
    assert main(["--list"]) == 0
    out = capsys.readouterr().out
    for name in EXPECTED_ANIMS:
        assert name in out
    assert "3 animations available." in out


def test_cli_missing_file(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.csv")]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_invalid_schema(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n", encoding="utf-8")
    assert main(["--file", str(bad)]) == 2
    assert "missing column" in capsys.readouterr().err


def test_cli_requires_action(capsys):
    with pytest.raises(SystemExit):
        main([])


def test_project_has_sample_data():
    assert DEMO_CSV.is_file()
    assert DEMO_CSV.parent == PROJECT_ROOT / "data"


# --------------------------------------------------------------------------- #
# Pure helpers beyond the basics
# --------------------------------------------------------------------------- #
def test_scores_through_before_first_week_is_empty(sample):
    assert scores_through(sample, 0) == {}


def test_scores_through_past_last_week_keeps_full_series(sample):
    series = scores_through(sample, 99)
    assert set(series) == set(teams(sample))
    assert all(len(values) == len(weeks(sample)) for values in series.values())


def test_teams_helper_matches_frame_values(sample):
    assert teams(sample) == sorted(sample["team"].unique())
    assert teams(sample)[0] == min(sample["team"])
