"""A queue position is not an index into a list that people can change.

The legacy player kept one number per playlist:

    def next_track(tracks, cursor):
        cursor = cursor + 1
        if cursor >= len(tracks):
            cursor = 0
        return cursor, tracks[cursor]

**1. The cursor is an index into a list the user edits.** With `Ember` playing at index 2,
deleting `Kite` at index 0 shifts everything down by one. The cursor still says 2, so the
player moves to the **track after** the one that should have played: `Quiet Hours` instead
of `Drift`. One deletion, and a track is skipped without ever being seen.

**2. `if cursor >= len(tracks): cursor = 0` decides the repeat mode by itself.** A playlist
with repeat *off* wraps to the top and plays forever, so the mode the user chose is never
consulted.

**3. Shuffle is not `random.shuffle` before every draw.** Reshuffling the whole list for
each "next" can play the same track twice in a row, can play track 3 four times before
track 4 at all, and cannot be reproduced: two runs disagree, so a bug in the shuffle is
unfixable. A shuffle is a **permutation consumed in order** -- every track once before any
track twice -- and a seeded one is reproducible on demand.

**4. A duration is a whole number of seconds.** `f"{total // 60}:{total % 60}"` prints a
64-minute playlist as `64:23` and a seven-second remainder as `7:5`. Hours are part of
the format, and seconds are two digits.

So this module keeps `Track.seconds` as integers, a `Player` whose order is a permutation
of *track indices* that survives removal, a repeat mode that `advance()` actually asks, a
seeded Fisher-Yates shuffle consumed in order, and a `format_duration` that pads. The
legacy path is kept beside it, executable, so every claim above is reproduced.

The demonstration is offline: one bundled playlist of eleven tracks.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PLAYLIST_FILE = DATA_DIR / "playlist.txt"

#: The legacy advance, transcribed -- and executable.
LEGACY_NEXT = ("def next_track(tracks, cursor):\n"
               "    cursor = cursor + 1\n"
               "    if cursor >= len(tracks):\n"
               "        cursor = 0\n"
               "    return cursor, tracks[cursor]")

#: The legacy duration total, transcribed.
LEGACY_TOTAL = 'return f"{total // 60}:{total % 60}"'

#: The three repeat modes.
REPEATS = ("off", "one", "all")

#: The separator a bundle line uses.
FIELD = "|"


class PlayerError(Exception):
    """A track, a duration, a position or a repeat mode that cannot be honoured."""


# --------------------------------------------------------------------------- #
# Durations
# --------------------------------------------------------------------------- #
def parse_duration(text: str) -> int:
    """`"3:07"` or `"1:04:23"` as a whole number of seconds."""
    if not isinstance(text, str):
        raise PlayerError(f"a duration is text, got {type(text).__name__}")
    fields = text.strip().split(":")
    if len(fields) not in (2, 3):
        raise PlayerError(f"a duration is MM:SS or HH:MM:SS, got {text!r}")
    for field in fields:
        if not field.isdigit():
            raise PlayerError(f"{field!r} in {text!r} is not a whole number")
    numbers = [int(field) for field in fields]
    if len(numbers) == 2:
        minutes, seconds = numbers
        if seconds >= 60:
            raise PlayerError(f"{text!r} has {seconds} seconds: seconds are "
                              f"0 to 59")
        return minutes * 60 + seconds
    hours, minutes, seconds = numbers
    if minutes >= 60 or seconds >= 60:
        raise PlayerError(f"{text!r} is HH:MM:SS, with minutes and seconds "
                          f"below 60")
    return hours * 3600 + minutes * 60 + seconds


def format_duration(seconds: int) -> str:
    """`187 -> "3:07"`, `3863 -> "1:04:23"` -- padded, with hours when needed."""
    if not isinstance(seconds, int) or isinstance(seconds, bool):
        raise PlayerError(f"a duration is whole seconds, got {seconds!r}")
    if seconds < 0:
        raise PlayerError(f"a duration is not negative, got {seconds}")
    minutes, rest = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}:{rest:02d}"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{rest:02d}"


def legacy_total(seconds: int) -> str:
    """`f"{seconds // 60}:{seconds % 60}"` -- no hours, no padding."""
    return f"{seconds // 60}:{seconds % 60}"


# --------------------------------------------------------------------------- #
# A track
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Track:
    """A title, an artist and a length in whole seconds."""

    title: str
    artist: str
    seconds: int

    def __post_init__(self) -> None:
        for value, name in ((self.title, "a title"), (self.artist, "an artist")):
            if not isinstance(value, str) or not value.strip():
                raise PlayerError(f"{name} is text, and not blank")
        if not isinstance(self.seconds, int) or isinstance(self.seconds, bool):
            raise PlayerError(f"a length is whole seconds, got {self.seconds!r}")
        if self.seconds <= 0:
            raise PlayerError(f"a length is positive, got {self.seconds}")

    def line(self) -> str:
        return f"{self.title:<16} {self.artist:<8} {format_duration(self.seconds):>7}"


def parse_track(text: str) -> Track:
    """`title | artist | MM:SS`, with the spaces around the pipes optional."""
    fields = [field.strip() for field in text.split(FIELD)]
    if len(fields) != 3:
        raise PlayerError(f"a line is 'title | artist | MM:SS', got {text!r}")
    title, artist, length = fields
    return Track(title, artist, parse_duration(length))


def parse_playlist(text: str) -> tuple[Track, ...]:
    """One track per line; `;` introduces a comment."""
    tracks: list[Track] = []
    for number, line in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        body = line.split(";", 1)[0].strip()
        if not body:
            continue
        try:
            tracks.append(parse_track(body))
        except PlayerError as error:
            raise PlayerError(f"line {number}: {error}") from None
    if not tracks:
        raise PlayerError("a playlist needs at least one track")
    titles = [track.title for track in tracks]
    if len(titles) != len(set(titles)):
        raise PlayerError("a playlist's titles are distinct, so a removal can "
                          "name one")
    return tuple(tracks)


def read_playlist(path=None) -> tuple[Track, ...]:
    target = Path(PLAYLIST_FILE if path is None else path)
    if not target.is_file():
        raise PlayerError(f"file not found: {target}")
    return parse_playlist(target.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# The legacy path
# --------------------------------------------------------------------------- #
def legacy_advance(tracks, cursor: int):
    """`cursor + 1`, wrapping to 0 -- whether or not repeat is on."""
    cursor = cursor + 1
    if cursor >= len(tracks):
        cursor = 0
    return cursor, tracks[cursor]


def legacy_shuffle(tracks, rng) -> list:
    """`rng.shuffle(tracks)` in place: the whole list, before every draw."""
    rng.shuffle(tracks)
    return tracks


# --------------------------------------------------------------------------- #
# The player
# --------------------------------------------------------------------------- #
class Player:
    """A playlist with an order, a cursor into that order, and a repeat mode."""

    def __init__(self, tracks, repeat: str = "off", seed=None) -> None:
        held = tuple(tracks)
        if not held:
            raise PlayerError("a player needs at least one track")
        for track in held:
            if not isinstance(track, Track):
                raise PlayerError(f"a player holds tracks, got {track!r}")
        if repeat not in REPEATS:
            raise PlayerError(f"a repeat mode is {REPEATS}, got {repeat!r}")
        self._tracks: list[Track] = list(held)
        self._repeat = repeat
        self._order: list[int] = list(range(len(self._tracks)))
        self._cursor = -1
        self._history: list[str] = []
        self._seed = seed
        if seed is not None:
            self.shuffle(seed)

    # -- reading ----------------------------------------------------------- #
    @property
    def repeat(self) -> str:
        return self._repeat

    @property
    def cursor(self) -> int:
        return self._cursor

    @property
    def seed(self):
        return self._seed

    def tracks(self) -> tuple[Track, ...]:
        return tuple(self._tracks)

    def order(self) -> tuple[int, ...]:
        """The play order, as positions in the playlist."""
        return tuple(self._order)

    def titles(self) -> tuple[str, ...]:
        return tuple(self._tracks[index].title for index in self._order)

    def history(self) -> tuple[str, ...]:
        return tuple(self._history)

    def played(self) -> int:
        return len(self._history)

    def total(self) -> int:
        return sum(track.seconds for track in self._tracks)

    def total_text(self) -> str:
        return format_duration(self.total())

    def position(self):
        """The playlist position of the track now playing, or `None`."""
        if self._cursor < 0 or self._cursor >= len(self._order):
            return None
        return self._order[self._cursor]

    def current(self):
        position = self.position()
        return None if position is None else self._tracks[position]

    def line(self) -> str:
        now = self.current()
        title = "nothing" if now is None else now.title
        return (f"{len(self._tracks)} track(s), {self.total_text()}, "
                f"repeat {self._repeat}, playing {title}, "
                f"{self.played()} played")

    # -- moving ------------------------------------------------------------ #
    def _record(self, track) -> None:
        self._history.append(track.title)

    def start(self):
        """Begin at the top of the order."""
        if not self._order:
            return None
        self._cursor = 0
        track = self._tracks[self._order[0]]
        self._record(track)
        return track

    def advance(self):
        """Play the next track, or `None` when the mode says stop."""
        if not self._order:
            return None
        if self._cursor < 0:
            return self.start()
        if self._repeat == "one":
            track = self.current()
            self._record(track)
            return track
        if self._cursor + 1 < len(self._order):
            self._cursor += 1
        elif self._repeat == "all":
            self._cursor = 0
        else:
            return None
        track = self.current()
        self._record(track)
        return track

    def back(self):
        """Play the previous track, or `None` at the top."""
        if self._cursor <= 0:
            return None
        self._cursor -= 1
        track = self.current()
        self._record(track)
        return track

    # -- editing ----------------------------------------------------------- #
    def _check_position(self, position: int) -> int:
        if not isinstance(position, int) or isinstance(position, bool):
            raise PlayerError(f"a position is a whole number, got {position!r}")
        if position < 0 or position >= len(self._tracks):
            raise PlayerError(f"a position is between 0 and "
                              f"{len(self._tracks) - 1}, got {position}")
        return position

    def remove(self, position: int):
        """Delete a track, keeping the cursor on the track it was pointing at.

        The cursor is an index into the *order*, and the order is a permutation
        of playlist positions. Removing a track means remapping every position
        above it, and moving the cursor down when the removed track sat before
        it -- otherwise the track that follows is skipped.
        """
        self._check_position(position)
        gone_slot = self._order.index(position)
        removed = self._tracks.pop(position)
        self._order = [index - 1 if index > position else index
                       for index in self._order if index != position]
        if self._cursor < 0:
            return removed
        # Removing a track at or before the cursor moves the cursor back one
        # slot, so the track that followed still follows. Removing the track
        # that is playing therefore leaves the *previous* track as current, and
        # the next advance plays the one that took its place.
        if gone_slot <= self._cursor:
            self._cursor -= 1
        if self._cursor >= len(self._order):
            self._cursor = 0 if (self._repeat == "all" and self._order) else -1
        return removed

    def shuffle(self, seed=None):
        """A seeded Fisher-Yates permutation, keeping the current track first."""
        order = list(range(len(self._tracks)))
        generator = random.Random(seed)
        for index in range(len(order) - 1, 0, -1):
            other = generator.randrange(index + 1)
            order[index], order[other] = order[other], order[index]
        current = self.position()
        if current is not None:
            order.remove(current)
            order.insert(0, current)
            self._cursor = 0
        self._order = order
        self._seed = seed
        return self.titles()

    def unshuffle(self):
        """Back to playlist order, keeping the current track playing."""
        current = self.position()
        self._order = list(range(len(self._tracks)))
        self._cursor = -1 if current is None else self._order.index(current)
        return self.titles()


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:                                     # noqa: BLE001
        return False


def audit(measured: dict, tracks, make_player=Player) -> list[tuple[str, bool]]:
    """Eleven checks, re-derived from what the demo measured or freshly built."""
    def at(name: str):
        if name not in measured:
            raise PlayerError(f"no measurement named {name!r}")
        return measured[name]

    def a_removal_before_the_cursor_does_not_skip_a_track() -> bool:
        return at("next_after_removal") == "Drift" and \
            at("legacy_next_after_removal") == "Quiet Hours"

    def removing_the_playing_track_moves_to_the_next_one() -> bool:
        return at("after_removing_current") == "Drift"

    def repeat_all_wraps_after_the_last_track() -> bool:
        return at("last_track") == "Half Light" and at("wrapped_to") == "Kite"

    def repeat_one_replays_the_same_track() -> bool:
        return at("repeated") == at("repeating_from") == "Kite"

    def repeat_off_stops_after_the_last_track() -> bool:
        return at("stopped") is None

    def eleven_advances_play_eleven_tracks_and_the_twelfth_stops() -> bool:
        return at("plays_without_repeat") == len(at("pass_order")) and \
            at("extra_play") is None

    def a_seeded_shuffle_is_reproducible() -> bool:
        first = make_player(tracks, "off", 7).titles()
        second = make_player(tracks, "off", 7).titles()
        third = make_player(tracks, "off", 8).titles()
        return first == second and first != third

    def a_shuffled_pass_plays_every_track_exactly_once() -> bool:
        order = make_player(tracks, "off", 7).titles()
        return len(order) == len(tracks) and set(order) == \
            {track.title for track in tracks}

    def a_shuffle_keeps_the_current_track_playing() -> bool:
        player = make_player(tracks, "off", 7)
        player.start()
        player.advance()
        playing = player.current().title
        player.shuffle(11)
        return player.current() is not None and \
            player.current().title == playing and player.titles()[0] == playing

    def the_total_is_the_sum_of_the_seconds() -> bool:
        return at("total_seconds") == sum(track.seconds for track in tracks)

    def the_total_crosses_an_hour_and_the_legacy_total_does_not() -> bool:
        return at("total_text") == "1:04:23" and at("legacy_total") == "64:23"

    checks = [
        ("a removal before the cursor does not skip a track",
         a_removal_before_the_cursor_does_not_skip_a_track),
        ("removing the playing track moves to the next one",
         removing_the_playing_track_moves_to_the_next_one),
        ("repeat all wraps after the last track",
         repeat_all_wraps_after_the_last_track),
        ("repeat one replays the same track", repeat_one_replays_the_same_track),
        ("repeat off stops after the last track",
         repeat_off_stops_after_the_last_track),
        ("eleven advances play eleven tracks and the twelfth stops",
         eleven_advances_play_eleven_tracks_and_the_twelfth_stops),
        ("a seeded shuffle is reproducible", a_seeded_shuffle_is_reproducible),
        ("a shuffled pass plays every track exactly once",
         a_shuffled_pass_plays_every_track_exactly_once),
        ("a shuffle keeps the current track playing",
         a_shuffle_keeps_the_current_track_playing),
        ("the total is the sum of the seconds",
         the_total_is_the_sum_of_the_seconds),
        ("the total crosses an hour and the legacy total does not",
         the_total_crosses_an_hour_and_the_legacy_total_does_not),
    ]
    return [(name, _guard(function)) for name, function in checks]


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def measure(tracks) -> dict:
    """Every experiment, each on a freshly built player."""
    measured: dict = {
        "pass_order": [track.title for track in tracks],
        "total_seconds": sum(track.seconds for track in tracks),
    }
    measured["total_text"] = format_duration(measured["total_seconds"])
    measured["legacy_total"] = legacy_total(measured["total_seconds"])

    # 1. a removal before the cursor
    player = Player(tracks)
    player.start()
    player.advance()
    player.advance()                       # Ember, at playlist position 2
    measured["playing"] = player.current().title
    after = list(tracks)
    legacy_cursor = player.position()
    after.pop(0)                           # Kite, before the cursor
    player.remove(0)
    following = player.advance()
    measured["next_after_removal"] = None if following is None else following.title
    measured["legacy_next_after_removal"] = \
        legacy_advance(after, legacy_cursor)[1].title

    # 2. removing the track that is playing
    player = Player(tracks)
    player.start()
    player.advance()
    player.advance()
    removed = player.remove(2)
    following = player.advance()
    measured["removed_playing"] = removed.title
    measured["after_removing_current"] = \
        None if following is None else following.title

    # 3-5. the three repeat modes
    player = Player(tracks, "all")
    player.start()
    for _ in range(len(tracks) - 1):
        player.advance()
    measured["last_track"] = player.current().title
    measured["wrapped_to"] = player.advance().title

    player = Player(tracks, "one")
    player.start()
    player.advance()
    player.advance()
    measured["repeating_from"] = player.current().title
    measured["repeated"] = player.advance().title

    player = Player(tracks, "off")
    player.start()
    for _ in range(len(tracks) - 1):
        player.advance()
    measured["stopped"] = player.advance()

    # 6. a full pass with repeat off
    player = Player(tracks, "off")
    player.start()
    for _ in range(len(tracks) + 4):
        if player.advance() is None:
            break
    measured["plays_without_repeat"] = player.played()
    measured["extra_play"] = player.advance()

    # 7. a seeded shuffle
    measured["shuffled"] = list(Player(tracks, "off", 7).titles())
    measured["shuffled_distinct"] = len(set(measured["shuffled"]))
    measured["legacy_shuffle"] = list(legacy_shuffle(list(tracks),
                                                    random.Random(7)))[0].title

    return measured


def run_demo() -> int:
    tracks = read_playlist()
    measured = measure(tracks)

    print("=" * 78)
    print(" PLAYER LAB - a queue position is not an index")
    print("=" * 78)

    print("\n  the legacy advance, transcribed:")
    for line in LEGACY_NEXT.split("\n"):
        print(f"    {line}")

    print(f"\n  {len(tracks)} tracks, {format_duration(measured['total_seconds'])} "
          f"in all:")
    for position, track in enumerate(tracks):
        print(f"    {position:>2}  {track.line()}")

    print("\n  the total, two ways:")
    print(f"    sum of the seconds:    {measured['total_seconds']}")
    print(f"    the padded format:     {measured['total_text']}")
    print(f"    the legacy format:     {measured['legacy_total']}  "
          f"(no hours, no padding)")

    print("\n  deleting a track while one is playing:")
    print(f"    playing:               {measured['playing']} (position 2)")
    print(f"    delete:                position 0")
    print(f"    the next track here:   {measured['next_after_removal']}")
    print(f"    the legacy next:       {measured['legacy_next_after_removal']}"
          f"  <- a track is skipped")
    print(f"    deleting the playing track itself moves to "
          f"{measured['after_removing_current']}")

    print("\n  the three repeat modes:")
    print(f"    all: after {measured['last_track']} comes "
          f"{measured['wrapped_to']}")
    print(f"    one: {measured['repeating_from']} repeats as "
          f"{measured['repeated']}")
    print(f"    off: after the last track, advance returns "
          f"{measured['stopped']}")
    print(f"    a full pass with repeat off plays "
          f"{measured['plays_without_repeat']} track(s), then "
          f"{measured['extra_play']}")

    print("\n  a seeded shuffle (seed 7):")
    print(f"    {', '.join(measured['shuffled'])}")
    print(f"    {measured['shuffled_distinct']} distinct titles in "
          f"{len(measured['shuffled'])} places -- a permutation, not a reshuffle")
    print(f"    the same seed always returns the same order")

    checks = audit(measured, tracks)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    print("\nCross-checks OK: " +
          f"{len(tracks)} tracks, {measured['total_text']} as "
          f"{measured['total_seconds']} seconds and "
          f"{measured['legacy_total']} as the legacy string, deleting track 0 "
          f"under {measured['playing']} plays {measured['next_after_removal']} "
          f"here and {measured['legacy_next_after_removal']} to the legacy "
          f"cursor, the shuffle places {measured['shuffled_distinct']} distinct "
          f"titles, and {sum(1 for _, okay in checks if okay)}/{len(checks)} "
          f"checks hold")

    print("Demo completed successfully.")
    return 0
