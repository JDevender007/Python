"""Tests for the player lab: a queue position is not an index."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                          # noqa: E402
import player as module                                     # noqa: E402
from player import (                                        # noqa: E402
    FIELD,
    LEGACY_NEXT,
    LEGACY_TOTAL,
    REPEATS,
    Player,
    PlayerError,
    Track,
    audit,
    format_duration,
    legacy_advance,
    legacy_shuffle,
    legacy_total,
    measure,
    parse_duration,
    parse_playlist,
    parse_track,
    problems,
    read_playlist,
    run_demo,
)

TRACKS = read_playlist()
MEASURED = measure(TRACKS)


def titles(player) -> list:
    return [track.title for track in player.tracks()]


# --------------------------------------------------------------------------- #
# parse_duration
# --------------------------------------------------------------------------- #
def test_parse_duration_reads_minutes_and_seconds():
    assert parse_duration("3:07") == 187


def test_parse_duration_reads_an_hour():
    assert parse_duration("1:04:23") == 3863


def test_parse_duration_reads_one_digit_seconds():
    assert parse_duration("0:7") == 7


def test_parse_duration_reads_zero():
    assert parse_duration("0:00") == 0


def test_parse_duration_refuses_sixty_seconds():
    with pytest.raises(PlayerError, match="seconds are 0 to 59"):
        parse_duration("3:60")


def test_parse_duration_refuses_sixty_minutes_in_the_third_field():
    with pytest.raises(PlayerError, match="below 60"):
        parse_duration("1:75:00")


def test_parse_duration_refuses_a_single_field():
    with pytest.raises(PlayerError, match="MM:SS or HH:MM:SS"):
        parse_duration("187")


def test_parse_duration_refuses_four_fields():
    with pytest.raises(PlayerError, match="MM:SS or HH:MM:SS"):
        parse_duration("1:2:3:4")


def test_parse_duration_refuses_a_word():
    with pytest.raises(PlayerError, match="is not a whole number"):
        parse_duration("3:0x")


def test_parse_duration_refuses_a_number():
    with pytest.raises(PlayerError, match="a duration is text"):
        parse_duration(187)


# --------------------------------------------------------------------------- #
# format_duration
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("seconds,expected", [
    (0, "0:00"), (7, "0:07"), (59, "0:59"), (60, "1:00"), (187, "3:07"),
    (599, "9:59"), (3599, "59:59"), (3600, "1:00:00"), (3863, "1:04:23"),
    (7325, "2:02:05"),
])
def test_format_duration_pads_and_adds_hours(seconds, expected):
    assert format_duration(seconds) == expected


def test_format_duration_refuses_a_negative():
    with pytest.raises(PlayerError, match="not negative"):
        format_duration(-1)


def test_format_duration_refuses_a_float():
    with pytest.raises(PlayerError, match="whole seconds"):
        format_duration(1.5)


def test_format_duration_refuses_a_true():
    with pytest.raises(PlayerError, match="whole seconds"):
        format_duration(True)


def test_a_formatted_duration_parses_back():
    for seconds in (0, 7, 187, 3863, 7325):
        assert parse_duration(format_duration(seconds)) == seconds


# --------------------------------------------------------------------------- #
# The legacy total
# --------------------------------------------------------------------------- #
def test_the_legacy_total_has_no_hours():
    assert legacy_total(3863) == "64:23"


def test_the_legacy_total_does_not_pad_the_seconds():
    assert legacy_total(427) == "7:7"


def test_the_legacy_total_agrees_under_a_minute():
    assert legacy_total(7) == "0:7"


def test_the_legacy_total_source_is_the_transcription():
    assert LEGACY_TOTAL == 'return f"{total // 60}:{total % 60}"'


# --------------------------------------------------------------------------- #
# Track
# --------------------------------------------------------------------------- #
def test_a_track_holds_a_title_an_artist_and_a_length():
    track = Track("Kite", "Aria", 187)
    assert (track.title, track.artist, track.seconds) == ("Kite", "Aria", 187)


def test_a_track_line_pads_the_length():
    assert Track("Kite", "Aria", 187).line() == "Kite             Aria        3:07"


def test_a_track_refuses_a_blank_title():
    with pytest.raises(PlayerError, match="is text, and not blank"):
        Track("  ", "Aria", 187)


def test_a_track_refuses_a_number_as_an_artist():
    with pytest.raises(PlayerError, match="an artist is text"):
        Track("Kite", 4, 187)


def test_a_track_refuses_a_zero_length():
    with pytest.raises(PlayerError, match="is positive"):
        Track("Kite", "Aria", 0)


def test_a_track_refuses_a_float_length():
    with pytest.raises(PlayerError, match="whole seconds"):
        Track("Kite", "Aria", 187.0)


def test_a_track_refuses_a_bool_length():
    with pytest.raises(PlayerError, match="whole seconds"):
        Track("Kite", "Aria", True)


# --------------------------------------------------------------------------- #
# Parsing the playlist
# --------------------------------------------------------------------------- #
def test_parse_track_splits_three_fields():
    assert parse_track("Kite | Aria | 3:07") == Track("Kite", "Aria", 187)


def test_parse_track_accepts_no_spaces():
    assert parse_track("Kite|Aria|3:07") == Track("Kite", "Aria", 187)


def test_parse_track_refuses_two_fields():
    with pytest.raises(PlayerError, match="title"):
        parse_track("Kite | Aria")


def test_parse_playlist_reads_one_track_per_line():
    assert len(parse_playlist("a | b | 1:00\nc | d | 2:00\n")) == 2


def test_parse_playlist_skips_a_comment():
    assert len(parse_playlist("; a note\na | b | 1:00\n")) == 1


def test_parse_playlist_skips_blank_lines():
    assert len(parse_playlist("\na | b | 1:00\n\n")) == 1


def test_parse_playlist_reads_windows_line_endings():
    assert len(parse_playlist("a | b | 1:00\r\nc | d | 2:00\r\n")) == 2


def test_parse_playlist_names_the_line_it_could_not_read():
    with pytest.raises(PlayerError, match="line 2:"):
        parse_playlist("a | b | 1:00\nbroken line\n")


def test_parse_playlist_refuses_an_empty_bundle():
    with pytest.raises(PlayerError, match="at least one track"):
        parse_playlist("; nothing\n")


def test_parse_playlist_refuses_two_tracks_with_one_title():
    with pytest.raises(PlayerError, match="titles are distinct"):
        parse_playlist("a | b | 1:00\na | c | 2:00\n")


def test_the_bundled_playlist_has_eleven_tracks():
    assert len(TRACKS) == 11


def test_the_bundled_playlist_totals_3863_seconds():
    assert sum(track.seconds for track in TRACKS) == 3863


def test_read_playlist_refuses_a_missing_file(tmp_path):
    with pytest.raises(PlayerError, match="file not found"):
        read_playlist(tmp_path / "nope.txt")


def test_read_playlist_accepts_its_own_file(tmp_path):
    path = tmp_path / "playlist.txt"
    path.write_bytes(b"a | b | 1:00\n")
    assert read_playlist(path)[0].title == "a"


# --------------------------------------------------------------------------- #
# The legacy path
# --------------------------------------------------------------------------- #
def test_the_legacy_advance_wraps_at_the_end():
    assert legacy_advance(["a", "b"], 1) == (0, "a")


def test_the_legacy_advance_moves_one_forward():
    assert legacy_advance(["a", "b", "c"], 0) == (1, "b")


def test_the_legacy_advance_has_no_way_to_stop():
    for cursor in range(10):
        assert legacy_advance(["a", "b"], cursor)[0] in (0, 1)


def test_the_legacy_advance_skips_a_track_after_a_removal():
    after = titles(Player(TRACKS))[1:]        # the playlist with Kite removed
    assert legacy_advance(after, 2)[1] == "Quiet Hours"


def test_the_legacy_shuffle_reorders_in_place():
    tracks = ["a", "b", "c", "d", "e"]
    assert sorted(legacy_shuffle(tracks, random.Random(1))) == \
        ["a", "b", "c", "d", "e"]


def test_the_legacy_shuffle_can_put_the_same_track_first_twice():
    tracks = list("abcdefgh")
    first = legacy_shuffle(list(tracks), random.Random(3))[0]
    second = legacy_shuffle(list(tracks), random.Random(3))[0]
    assert first == second              # same seed, same first draw
    assert legacy_shuffle(list(tracks), random.Random(4))[0] != first


def test_the_transcribed_legacy_advance_is_the_wrap():
    assert LEGACY_NEXT.startswith("def next_track(tracks, cursor):")
    assert "cursor = 0" in LEGACY_NEXT


# --------------------------------------------------------------------------- #
# Player: construction and reading
# --------------------------------------------------------------------------- #
def test_a_player_holds_the_tracks_it_was_given():
    assert len(Player(TRACKS).tracks()) == 11


def test_a_player_starts_unstarted():
    player = Player(TRACKS)
    assert player.cursor == -1 and player.position() is None


def test_a_player_starts_in_playlist_order():
    assert Player(TRACKS).order() == tuple(range(11))


def test_a_player_starts_playing_nothing():
    assert Player(TRACKS).current() is None


def test_a_player_reports_its_total_in_seconds():
    assert Player(TRACKS).total() == 3863


def test_a_player_formats_its_total():
    assert Player(TRACKS).total_text() == "1:04:23"


def test_a_player_line_names_the_track_and_the_count():
    player = Player(TRACKS)
    player.start()
    assert player.line() == ("11 track(s), 1:04:23, repeat off, playing Kite, "
                             "1 played")


def test_a_player_refuses_an_empty_playlist():
    with pytest.raises(PlayerError, match="at least one track"):
        Player([])


def test_a_player_refuses_something_that_is_not_a_track():
    with pytest.raises(PlayerError, match="holds tracks"):
        Player(["Kite"])


def test_a_player_refuses_an_unknown_repeat_mode():
    with pytest.raises(PlayerError, match="a repeat mode is"):
        Player(TRACKS, "loop")


def test_the_three_repeat_modes_are_named():
    assert REPEATS == ("off", "one", "all")


# --------------------------------------------------------------------------- #
# Player: moving
# --------------------------------------------------------------------------- #
def test_start_plays_the_first_track():
    assert Player(TRACKS).start().title == "Kite"


def test_start_records_the_play():
    player = Player(TRACKS)
    player.start()
    assert player.history() == ("Kite",)


def test_advance_without_start_plays_the_first_track():
    assert Player(TRACKS).advance().title == "Kite"


def test_advance_moves_one_track_forward():
    player = Player(TRACKS)
    player.start()
    assert player.advance().title == "Harbour"


def test_advance_stops_after_the_last_track_with_repeat_off():
    player = Player(TRACKS, "off")
    player.start()
    for _ in range(len(TRACKS) - 1):
        player.advance()
    assert player.current().title == "Half Light"
    assert player.advance() is None


def test_a_stopped_player_keeps_pointing_at_the_last_track():
    player = Player(TRACKS, "off")
    player.start()
    for _ in range(len(TRACKS) - 1):
        player.advance()
    player.advance()
    assert player.current().title == "Half Light"


def test_repeat_all_wraps_to_the_first_track():
    player = Player(TRACKS, "all")
    player.start()
    for _ in range(len(TRACKS) - 1):
        player.advance()
    assert player.advance().title == "Kite"


def test_repeat_one_stays_on_the_same_track():
    player = Player(TRACKS, "one")
    player.start()
    assert player.advance().title == "Kite"
    assert player.advance().title == "Kite"


def test_a_full_pass_plays_every_track_once():
    player = Player(TRACKS, "off")
    player.start()
    for _ in range(20):
        if player.advance() is None:
            break
    assert len(player.history()) == 11
    assert set(player.history()) == {track.title for track in TRACKS}


def test_back_moves_one_track_back():
    player = Player(TRACKS)
    player.start()
    player.advance()
    assert player.back().title == "Kite"


def test_back_at_the_top_does_nothing():
    player = Player(TRACKS)
    player.start()
    assert player.back() is None


def test_every_play_is_recorded():
    player = Player(TRACKS)
    player.start()
    player.advance()
    player.back()
    assert player.history() == ("Kite", "Harbour", "Kite")
    assert player.played() == 3


# --------------------------------------------------------------------------- #
# Player: removing a track
# --------------------------------------------------------------------------- #
def test_remove_deletes_the_track_and_returns_it():
    player = Player(TRACKS)
    assert player.remove(0).title == "Kite"
    assert len(player.tracks()) == 10


def test_remove_keeps_the_order_a_permutation():
    player = Player(TRACKS)
    player.remove(3)
    assert sorted(player.order()) == list(range(10))


def test_removing_the_playing_track_does_not_skip_the_next():
    player = Player(TRACKS)
    player.start()
    player.advance()
    player.advance()
    assert player.current().title == "Ember"
    player.remove(2)
    assert player.advance().title == "Drift"


def test_removing_a_track_before_the_cursor_does_not_skip_the_next():
    player = Player(TRACKS)
    player.start()
    player.advance()
    player.advance()
    player.remove(0)
    assert player.current().title == "Ember"
    assert player.advance().title == "Drift"


def test_removing_a_track_after_the_cursor_changes_nothing():
    player = Player(TRACKS)
    player.start()
    player.remove(5)
    assert player.advance().title == "Harbour"


def test_removing_the_playing_track_while_it_is_the_first_leaves_nothing_playing():
    player = Player(TRACKS)
    player.start()
    player.remove(0)
    assert player.current() is None
    assert player.advance().title == "Harbour"


def test_removing_every_track_empties_the_player():
    player = Player(TRACKS)
    player.start()
    for _ in range(len(TRACKS)):
        player.remove(0)
    assert player.tracks() == () and player.current() is None


def test_a_removal_before_the_cursor_moves_the_cursor_down():
    player = Player(TRACKS)
    player.start()
    player.advance()
    player.advance()
    assert player.cursor == 2
    player.remove(0)
    assert player.cursor == 1


def test_remove_refuses_a_position_past_the_end():
    with pytest.raises(PlayerError, match="a position is between 0 and 10"):
        Player(TRACKS).remove(11)


def test_remove_refuses_a_negative_position():
    with pytest.raises(PlayerError, match="a position is between 0 and 10"):
        Player(TRACKS).remove(-1)


def test_remove_refuses_a_float_position():
    with pytest.raises(PlayerError, match="whole number"):
        Player(TRACKS).remove(1.0)


# --------------------------------------------------------------------------- #
# Player: shuffle
# --------------------------------------------------------------------------- #
def test_a_seeded_shuffle_is_reproducible():
    assert Player(TRACKS, "off", 7).titles() == Player(TRACKS, "off", 7).titles()


def test_two_seeds_give_two_orders():
    assert Player(TRACKS, "off", 7).titles() != Player(TRACKS, "off", 8).titles()


def test_a_shuffle_is_a_permutation():
    order = Player(TRACKS, "off", 7).titles()
    assert sorted(order) == sorted(track.title for track in TRACKS)


def test_a_shuffle_places_every_track_in_a_different_slot():
    order = Player(TRACKS, "off", 7).titles()
    assert order != tuple(track.title for track in TRACKS)


def test_a_shuffle_keeps_the_current_track_playing():
    player = Player(TRACKS)
    player.start()
    player.advance()
    player.shuffle(3)
    assert player.current().title == "Harbour"
    assert player.titles()[0] == "Harbour"


def test_a_shuffle_puts_the_current_track_first():
    player = Player(TRACKS)
    player.start()
    player.advance()
    player.advance()
    player.shuffle(3)
    assert player.cursor == 0 and player.titles()[0] == "Ember"


def test_a_second_shuffle_keeps_the_current_track_playing():
    player = Player(TRACKS, "off", 7)
    player.start()
    player.advance()
    playing = player.current().title
    player.shuffle(11)
    assert player.current().title == playing


def test_unshuffle_returns_to_playlist_order():
    player = Player(TRACKS, "off", 7)
    player.unshuffle()
    assert player.order() == tuple(range(11))


def test_unshuffle_keeps_the_current_track_playing():
    player = Player(TRACKS, "off", 7)
    player.start()
    playing = player.current().title
    player.unshuffle()
    assert player.current().title == playing


def test_a_shuffled_pass_plays_every_track_once():
    player = Player(TRACKS, "off", 7)
    player.start()
    for _ in range(20):
        if player.advance() is None:
            break
    assert len(player.history()) == 11
    assert len(set(player.history())) == 11


def test_the_seed_is_remembered():
    assert Player(TRACKS, "off", 7).seed == 7
    assert Player(TRACKS).seed is None


def test_a_player_without_a_seed_keeps_playlist_order():
    assert Player(TRACKS).titles() == tuple(track.title for track in TRACKS)


# --------------------------------------------------------------------------- #
# measure
# --------------------------------------------------------------------------- #
def test_measure_pins_the_total():
    assert MEASURED["total_seconds"] == 3863
    assert MEASURED["total_text"] == "1:04:23"
    assert MEASURED["legacy_total"] == "64:23"


def test_measure_pins_the_playing_track():
    assert MEASURED["playing"] == "Ember"


def test_measure_pins_the_next_track_after_a_removal():
    assert MEASURED["next_after_removal"] == "Drift"


def test_measure_shows_the_legacy_cursor_skipping():
    assert MEASURED["legacy_next_after_removal"] == "Quiet Hours"


def test_measure_pins_removing_the_playing_track():
    assert MEASURED["removed_playing"] == "Ember"
    assert MEASURED["after_removing_current"] == "Drift"


def test_measure_pins_the_three_repeat_modes():
    assert MEASURED["last_track"] == "Half Light"
    assert MEASURED["wrapped_to"] == "Kite"
    assert MEASURED["repeating_from"] == MEASURED["repeated"] == "Kite"
    assert MEASURED["stopped"] is None


def test_measure_pins_a_full_pass():
    assert MEASURED["plays_without_repeat"] == 11
    assert MEASURED["extra_play"] is None


def test_measure_pins_the_shuffle():
    assert MEASURED["shuffled"][:3] == ["Harbour", "Half Light", "Drift"]
    assert MEASURED["shuffled_distinct"] == 11


def test_measure_records_what_the_legacy_shuffle_draws_first():
    assert MEASURED["legacy_shuffle"] in {track.title for track in TRACKS}


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
CHECK_NAMES = [
    "a removal before the cursor does not skip a track",
    "removing the playing track moves to the next one",
    "repeat all wraps after the last track",
    "repeat one replays the same track",
    "repeat off stops after the last track",
    "eleven advances play eleven tracks and the twelfth stops",
    "a seeded shuffle is reproducible",
    "a shuffled pass plays every track exactly once",
    "a shuffle keeps the current track playing",
    "the total is the sum of the seconds",
    "the total crosses an hour and the legacy total does not",
]


def real_checks():
    return audit(MEASURED, TRACKS)


def test_the_audit_holds_eleven_named_checks():
    assert [name for name, _ in real_checks()] == CHECK_NAMES


def test_the_audit_passes_on_the_bundled_playlist():
    assert problems(real_checks()) == []


def test_the_audit_is_repeatable():
    assert real_checks() == real_checks()


def corrupted(**changes) -> dict:
    payload = dict(MEASURED)
    payload.update(changes)
    return payload


def test_the_audit_catches_the_legacy_skip_recorded_as_right():
    checks = audit(corrupted(next_after_removal="Quiet Hours"), TRACKS)
    assert CHECK_NAMES[0] in problems(checks)


def test_the_audit_catches_removing_the_playing_track_skipping_one():
    checks = audit(corrupted(after_removing_current="Quiet Hours"), TRACKS)
    assert CHECK_NAMES[1] in problems(checks)


def test_the_audit_catches_a_wrap_to_the_wrong_track():
    checks = audit(corrupted(wrapped_to="Harbour"), TRACKS)
    assert CHECK_NAMES[2] in problems(checks)


def test_the_audit_catches_repeat_one_moving_on():
    checks = audit(corrupted(repeated="Harbour"), TRACKS)
    assert CHECK_NAMES[3] in problems(checks)


def test_the_audit_catches_repeat_off_wrapping():
    checks = audit(corrupted(stopped="Kite"), TRACKS)
    assert CHECK_NAMES[4] in problems(checks)


def test_the_audit_catches_an_extra_play_past_the_end():
    checks = audit(corrupted(plays_without_repeat=12), TRACKS)
    assert CHECK_NAMES[5] in problems(checks)


def test_the_audit_catches_a_total_that_dropped_a_track():
    checks = audit(corrupted(total_seconds=3812), TRACKS)
    assert CHECK_NAMES[9] in problems(checks)


def test_the_audit_catches_a_legacy_total_that_padded_correctly():
    checks = audit(corrupted(legacy_total="1:04:23"), TRACKS)
    assert CHECK_NAMES[10] in problems(checks)


class RepeatingShuffle(Player):
    """A player whose shuffle ignores the seed: two calls never agree."""

    def __init__(self, tracks, repeat="off", seed=None):
        self._calls = 0
        super().__init__(tracks, repeat, seed)

    def shuffle(self, seed=None):
        order = list(range(len(self._tracks)))
        self._calls += 1
        if self._calls % 2 == 0:
            order.reverse()
        self._order = order
        return self.titles()


def test_the_audit_catches_an_unseeded_shuffle():
    checks = audit(MEASURED, TRACKS, RepeatingShuffle)
    assert CHECK_NAMES[6] in problems(checks)


class RepeatingPlayer(Player):
    """A player that can play one track twice before the rest once."""

    def __init__(self, tracks, repeat="off", seed=None):
        super().__init__(tracks, repeat, seed)
        if seed is not None:
            order = list(range(len(self._tracks)))
            random.Random(seed).shuffle(order)
            self._order = order + [order[0]]


def test_the_audit_catches_a_pass_that_doubles_a_track():
    checks = audit(MEASURED, TRACKS, RepeatingPlayer)
    assert CHECK_NAMES[7] in problems(checks)


class LosingShuffle(Player):
    """A player whose shuffle forgets what was playing."""

    def shuffle(self, seed=None):
        order = list(range(len(self._tracks)))
        random.Random(seed).shuffle(order)
        self._order = order
        self._cursor = -1
        return self.titles()


def test_the_audit_catches_a_shuffle_that_stops_the_music():
    checks = audit(MEASURED, TRACKS, LosingShuffle)
    assert CHECK_NAMES[8] in problems(checks)


def test_a_missing_measurement_is_a_failure_not_a_traceback():
    payload = corrupted()
    del payload["total_seconds"]
    checks = audit(payload, TRACKS)
    assert CHECK_NAMES[9] in problems(checks)
    assert len(checks) == len(CHECK_NAMES)


def test_every_check_has_a_negative_control():
    caught = set()
    caught |= set(problems(audit(corrupted(next_after_removal="x"), TRACKS)))
    caught |= set(problems(audit(corrupted(after_removing_current="x"), TRACKS)))
    caught |= set(problems(audit(corrupted(wrapped_to="x"), TRACKS)))
    caught |= set(problems(audit(corrupted(repeated="x"), TRACKS)))
    caught |= set(problems(audit(corrupted(stopped="x"), TRACKS)))
    caught |= set(problems(audit(corrupted(plays_without_repeat=99), TRACKS)))
    caught |= set(problems(audit(MEASURED, TRACKS, RepeatingShuffle)))
    caught |= set(problems(audit(MEASURED, TRACKS, RepeatingPlayer)))
    caught |= set(problems(audit(MEASURED, TRACKS, LosingShuffle)))
    caught |= set(problems(audit(corrupted(total_seconds=0), TRACKS)))
    caught |= set(problems(audit(corrupted(total_text="0:00"), TRACKS)))
    assert caught == set(CHECK_NAMES)


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_demo_returns_zero(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out and "Demo completed successfully." in out


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    assert capsys.readouterr().out == first


def test_demo_prints_no_non_ascii(capsys):
    run_demo()
    assert all(ord(character) < 128 for character in capsys.readouterr().out)


def test_demo_shows_the_legacy_advance(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "PLAYER LAB" in out and "cursor = cursor + 1" in out


def test_demo_shows_the_skipped_track(capsys):
    run_demo()
    assert "a track is skipped" in capsys.readouterr().out


def test_demo_shows_all_eleven_checks(capsys):
    run_demo()
    assert "11/11 checks pass" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo(capsys):
    assert cli.main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_lists_the_tracks(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "Kite" in out and "11 track(s)" in out


def test_cli_advances(capsys):
    assert cli.main(["--steps", "2"]) == 0
    out = capsys.readouterr().out
    assert "Harbour" in out and "Ember" in out


def test_cli_stops_at_the_end(capsys):
    assert cli.main(["--steps", "20"]) == 0
    out = capsys.readouterr().out
    assert "stop" in out


def test_cli_repeat_all_keeps_going(capsys):
    assert cli.main(["--steps", "11", "--repeat", "all"]) == 0
    out = capsys.readouterr().out
    assert out.count("Kite") >= 2


def test_cli_removes_a_track(capsys):
    assert cli.main(["--remove", "0", "--steps", "1"]) == 0
    out = capsys.readouterr().out
    assert "removed position 0: Kite" in out
    assert "Harbour" in out


def test_cli_shuffles_with_a_seed(capsys):
    assert cli.main(["--seed", "7", "--steps", "2"]) == 0
    assert "Harbour" in capsys.readouterr().out


def test_cli_prints_the_total(capsys):
    assert cli.main(["--total"]) == 0
    out = capsys.readouterr().out
    assert "1:04:23" in out and "64:23" in out


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 11 and "FAIL" not in out


def test_cli_writes_the_run_as_json(tmp_path, capsys):
    target = tmp_path / "run.json"
    assert cli.main(["--seed", "7", "--steps", "2", "--json", str(target),
                     "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert len(payload["tracks"]) == 11
    assert payload["tracks"][0]["length"] == "3:07"
    assert payload["total_text"] == "1:04:23"
    assert payload["order"][:3] == ["Harbour", "Half Light", "Drift"]


def test_cli_json_carries_the_measurements_and_checks(tmp_path, capsys):
    target = tmp_path / "run.json"
    assert cli.main(["--audit", "--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["measurements"]["legacy_total"] == "64:23"
    assert len(payload["checks"]) == 11
    assert all(check["ok"] for check in payload["checks"])


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_refuses_a_position_past_the_end(capsys):
    assert cli.main(["--remove", "11"]) == 2
    assert "a position is between 0 and 10" in capsys.readouterr().err


def test_cli_refuses_a_negative_step_count(capsys):
    assert cli.main(["--steps", "-1"]) == 2
    assert "steps is 0 or more" in capsys.readouterr().err


def test_cli_refuses_a_missing_playlist(tmp_path, capsys):
    assert cli.main(["--playlist", str(tmp_path / "nope.txt")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_refuses_an_unknown_repeat_mode(capsys):
    with pytest.raises(SystemExit) as raised:
        cli.main(["--repeat", "loop"])
    assert raised.value.code == 2


def test_the_module_keeps_its_field_separator():
    assert FIELD == "|" and module.FIELD == "|"
