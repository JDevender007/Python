"""A hotel where a room has dates, a state machine, and a price strategy.

The legacy project had none of the three. Its ``rooms`` table carried a
``status`` string, and ``book_room`` simply set it:

    room.status = "Occupied"          # any string is legal
    guest = Guest(..., room_id=room.id)

There were no arrival or departure dates on the booking at all -- only
``check_in_date = datetime.now()`` stamped at insert -- so the model could not
answer "is room 101 free on the 14th?" even in principle. ``checkout_guest``
set ``check_out_date`` but never removed the guest row, so ``total_guests``
counted everyone who had ever stayed, and ``query.first()`` could return a
departed guest.

Three ideas replace it.

**1. A stay is a half-open interval of dates.** ``Stay(check_in, check_out)``
covers ``[check_in, check_out)``: a guest leaving on the 14th does not occupy
the night of the 14th, so the next guest may arrive that morning. The legacy
test, reproduced here as ``legacy_overlaps``, was inclusive:

    return start <= other_end and end >= other_start

which makes those two bookings collide. The demo runs both on the same pair.

**2. Status is a state machine, not a string.** ``Booking`` has five states and
one table of allowed moves:

    HELD -> CONFIRMED | CANCELLED
    CONFIRMED -> CHECKED_IN | CANCELLED
    CHECKED_IN -> CHECKED_OUT
    CHECKED_OUT, CANCELLED -> (nothing)

so ``booking.check_in(day)`` on a held booking is refused, and the error lists
the moves that were allowed instead.

**3. A rate is a strategy object.** ``Rate.for_night(day)`` returns integer
cents for one night; ``total(stay)`` sums it over the stay. ``FlatRate``,
``WeekendRate`` and ``SeasonRate`` implement the same method, so the price of a
stay is polymorphic and the hotel never branches on a room type.

Money is integer cents throughout. The legacy ``price_per_night`` was a
``Float``, and its ``phone = Column(String(10))`` did not enforce ten digits
because SQLite ignores the length -- the demo proves that with an in-memory
database.

Standard library only: no ORM, no database file, no network.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "hotel.json"

#: The legacy status assignment: a string column with no rules.
LEGACY_STATUS = 'room.status = "Occupied"'

#: The legacy overlap test, inclusive at both ends.
LEGACY_OVERLAP = "start <= other_end and end >= other_start"

#: Friday and Saturday are the weekend nights (Monday is 0).
WEEKEND_NIGHTS = (4, 5)


class HotelError(ValueError):
    """A date, a price, a room or a booking that cannot be accepted."""


class BookingError(HotelError):
    """A move the state machine does not allow."""


# --------------------------------------------------------------------------- #
# Dates
# --------------------------------------------------------------------------- #
def as_date(value, label: str = "a date") -> date:
    """A ``date``, or a strict ``YYYY-MM-DD`` string."""
    if isinstance(value, date) and not isinstance(value, bool):
        return value
    if not isinstance(value, str):
        raise HotelError(f"{label} must be a date or YYYY-MM-DD, got "
                         f"{type(value).__name__}")
    if len(value) != 10 or value[4] != "-" or value[7] != "-":
        raise HotelError(f"{value!r} is not YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise HotelError(f"{value!r} is not a real date: {exc}") from None
    if parsed.isoformat() != value:
        raise HotelError(f"{value!r} is not in canonical form")
    return parsed


# --------------------------------------------------------------------------- #
# A stay
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Stay:
    """The nights between two dates: ``[check_in, check_out)``."""

    check_in: date
    check_out: date

    def __post_init__(self) -> None:
        if not isinstance(self.check_in, date) or \
                not isinstance(self.check_out, date):
            raise HotelError("a stay needs two dates")
        if self.check_out <= self.check_in:
            raise HotelError(
                f"a checkout on {self.check_out} is not after the check-in "
                f"on {self.check_in}")

    @classmethod
    def of(cls, check_in, check_out) -> "Stay":
        return cls(as_date(check_in, "the check-in"),
                   as_date(check_out, "the checkout"))

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days

    def each_night(self):
        for offset in range(self.nights):
            yield self.check_in + timedelta(days=offset)

    def contains(self, day: date) -> bool:
        """True for a night in the stay; the checkout date is not a night."""
        return self.check_in <= day < self.check_out

    def overlaps(self, other: "Stay") -> bool:
        """Half-open overlap: back-to-back stays do not collide."""
        return self.check_in < other.check_out and other.check_in < self.check_out

    def __str__(self) -> str:
        return f"{self.check_in.isoformat()}..{self.check_out.isoformat()}"


def legacy_overlaps(start: date, end: date, other_start: date,
                    other_end: date) -> bool:
    """The legacy inclusive test, which makes back-to-back stays collide."""
    return start <= other_end and end >= other_start


# --------------------------------------------------------------------------- #
# Rates
# --------------------------------------------------------------------------- #
class Rate(ABC):
    """One night's price in integer cents."""

    @abstractmethod
    def for_night(self, day: date) -> int:
        """The price of the night beginning on ``day``."""

    def total(self, stay: Stay) -> int:
        return sum(self.for_night(day) for day in stay.each_night())

    @abstractmethod
    def describe(self) -> str:
        """A short ASCII label for reports."""

    def to_dict(self) -> dict:
        raise NotImplementedError

    def __eq__(self, other) -> bool:
        return type(self) is type(other) and self.to_dict() == other.to_dict()

    def __hash__(self) -> int:
        return hash((type(self).__name__, json.dumps(self.to_dict(),
                                                    sort_keys=True)))


def check_cents(value, label="a price") -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise HotelError(f"{label} is an integer number of cents, got "
                         f"{type(value).__name__}")
    if value < 0:
        raise HotelError(f"{label} must not be negative")
    return value


class FlatRate(Rate):
    """The same price every night."""

    def __init__(self, cents: int):
        self.cents = check_cents(cents)

    def for_night(self, day: date) -> int:
        return self.cents

    def describe(self) -> str:
        return f"FlatRate {self.cents}"

    def to_dict(self) -> dict:
        return {"kind": "flat", "cents": self.cents}


class WeekendRate(Rate):
    """One price for Friday and Saturday nights, another for the rest."""

    def __init__(self, weekday_cents: int, weekend_cents: int):
        self.weekday_cents = check_cents(weekday_cents, "the weekday price")
        self.weekend_cents = check_cents(weekend_cents, "the weekend price")

    def for_night(self, day: date) -> int:
        if day.weekday() in WEEKEND_NIGHTS:
            return self.weekend_cents
        return self.weekday_cents

    def describe(self) -> str:
        return f"WeekendRate {self.weekday_cents}/{self.weekend_cents}"

    def to_dict(self) -> dict:
        return {"kind": "weekend", "weekday_cents": self.weekday_cents,
                "weekend_cents": self.weekend_cents}


class SeasonRate(Rate):
    """A base price, raised by a percentage inside a date window."""

    def __init__(self, base_cents: int, peak_start, peak_end,
                 peak_basis_points: int):
        self.base_cents = check_cents(base_cents, "the base price")
        self.peak = Stay.of(peak_start, peak_end)
        if isinstance(peak_basis_points, bool) \
                or not isinstance(peak_basis_points, int):
            raise HotelError("a peak is an integer number of basis points")
        if not 0 <= peak_basis_points <= 100000:
            raise HotelError("a peak must be between 0 and 100000 basis points")
        self.peak_basis_points = peak_basis_points

    def for_night(self, day: date) -> int:
        if self.peak.contains(day):
            raw = self.base_cents * (10000 + self.peak_basis_points)
            return (raw + 5000) // 10000
        return self.base_cents

    def describe(self) -> str:
        return (f"SeasonRate {self.base_cents} +{self.peak_basis_points / 100:g}% "
                f"from {self.peak.check_in}")

    def to_dict(self) -> dict:
        return {"kind": "season", "base_cents": self.base_cents,
                "peak_start": self.peak.check_in.isoformat(),
                "peak_end": self.peak.check_out.isoformat(),
                "peak_basis_points": self.peak_basis_points}


def rate_from_dict(row) -> Rate:
    if not isinstance(row, dict):
        raise HotelError("a rate must be an object")
    kind = row.get("kind")
    if kind == "flat":
        return FlatRate(row.get("cents"))
    if kind == "weekend":
        return WeekendRate(row.get("weekday_cents"), row.get("weekend_cents"))
    if kind == "season":
        return SeasonRate(row.get("base_cents"), row.get("peak_start"),
                          row.get("peak_end"), row.get("peak_basis_points"))
    raise HotelError(f"{kind!r} is not a rate kind")


# --------------------------------------------------------------------------- #
# Guest and room
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Guest:
    """A validated guest record."""

    name: str
    phone: str
    email: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise HotelError("a guest needs a name")
        if not isinstance(self.phone, str) or not self.phone.isdigit() \
                or len(self.phone) != 10:
            raise HotelError(
                f"a phone must be exactly 10 digits, got {self.phone!r}")
        if not isinstance(self.email, str) or "@" not in self.email \
                or "." not in self.email.split("@")[-1]:
            raise HotelError(f"{self.email!r} is not an email address")
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "email", self.email.strip().lower())

    def to_dict(self) -> dict:
        return {"name": self.name, "phone": self.phone, "email": self.email}

    def __str__(self) -> str:
        return self.name


class Room:
    """A room number, a capacity and a rate strategy."""

    def __init__(self, number: str, kind: str, rate: Rate, capacity: int = 2):
        if not isinstance(number, str) or not number.strip():
            raise HotelError("a room needs a number")
        if not isinstance(kind, str) or not kind.strip():
            raise HotelError("a room needs a type")
        if not isinstance(rate, Rate):
            raise HotelError("a room needs a Rate, not a number")
        if isinstance(capacity, bool) or not isinstance(capacity, int) \
                or capacity < 1:
            raise HotelError("a capacity is a whole number of at least one")
        self.number = number.strip()
        self.kind = kind.strip().title()
        self.rate = rate
        self.capacity = capacity

    def price(self, stay: Stay) -> int:
        return self.rate.total(stay)

    def __eq__(self, other) -> bool:
        return isinstance(other, Room) and other.number == self.number

    def __hash__(self) -> int:
        return hash(self.number)

    def __repr__(self) -> str:
        return (f"<Room {self.number} {self.kind} {self.capacity}p "
                f"{self.rate.describe()}>")

    def to_dict(self) -> dict:
        return {"number": self.number, "kind": self.kind,
                "capacity": self.capacity, "rate": self.rate.to_dict()}


# --------------------------------------------------------------------------- #
# Bookings
# --------------------------------------------------------------------------- #
class Status(str, Enum):
    HELD = "held"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    CANCELLED = "cancelled"


#: The only moves the state machine allows.
ALLOWED = {
    Status.HELD: (Status.CONFIRMED, Status.CANCELLED),
    Status.CONFIRMED: (Status.CHECKED_IN, Status.CANCELLED),
    Status.CHECKED_IN: (Status.CHECKED_OUT,),
    Status.CHECKED_OUT: (),
    Status.CANCELLED: (),
}

#: Statuses that still hold the room.
ACTIVE = (Status.HELD, Status.CONFIRMED, Status.CHECKED_IN)


class Booking:
    """A guest, a room, a stay and a status with rules."""

    def __init__(self, reference, room, guest, stay, status=Status.CONFIRMED,
                 history=None, notes=""):
        if not isinstance(reference, str) or not reference.strip():
            raise HotelError("a booking needs a reference")
        if not isinstance(room, Room):
            raise HotelError("a booking needs a Room")
        if not isinstance(guest, Guest):
            raise HotelError("a booking needs a Guest")
        if not isinstance(stay, Stay):
            raise HotelError("a booking needs a Stay")
        if not isinstance(status, Status):
            raise HotelError(f"{status!r} is not a booking status")
        self.reference = reference.strip()
        self.room = room
        self.guest = guest
        self.stay = stay
        self.status = status
        self.notes = notes
        self.history: list[tuple[Status, str]] = list(history or [])

    # -- transitions ------------------------------------------------------- #
    def _move(self, target: Status, day, why: str = "") -> "Booking":
        if not isinstance(target, Status):
            raise HotelError(f"{target!r} is not a booking status")
        if target not in ALLOWED[self.status]:
            allowed = ", ".join(item.value for item in ALLOWED[self.status]) \
                or "nothing"
            raise BookingError(
                f"{self.reference} is {self.status.value}; allowed from here: "
                f"{allowed}; {target.value} is not one of them")
        day = as_date(day, "the change date")
        self.status = target
        self.history.append((target, day.isoformat()))
        return self

    def confirm(self, day) -> "Booking":
        return self._move(Status.CONFIRMED, day)

    def check_in(self, day) -> "Booking":
        day = as_date(day, "the check-in date")
        if not self.stay.contains(day):
            raise BookingError(
                f"{day} is outside {self.stay}; the room is booked for those "
                f"nights only")
        return self._move(Status.CHECKED_IN, day)

    def check_out(self, day) -> "Booking":
        return self._move(Status.CHECKED_OUT, day)

    def cancel(self, day) -> "Booking":
        return self._move(Status.CANCELLED, day)

    # -- pricing ----------------------------------------------------------- #
    def price(self) -> int:
        return self.room.price(self.stay)

    def folio(self) -> list[str]:
        lines = [f"{self.reference}  {self.guest.name}  room {self.room.number}"
                 f"  {self.stay}  ({self.status.value})"]
        for day in self.stay.each_night():
            cents = self.room.rate.for_night(day)
            lines.append(f"  {day.isoformat()} {day.strftime('%a')} "
                         f"{cents:>8}")
        lines.append(f"  {self.stay.nights} night(s), total {self.price():>8}")
        return lines

    @property
    def holds_room(self) -> bool:
        return self.status in ACTIVE

    def __repr__(self) -> str:
        return (f"<Booking {self.reference} {self.room.number} "
                f"{self.stay} {self.status.value}>")

    def to_dict(self) -> dict:
        return {"reference": self.reference, "room": self.room.number,
                "guest": self.guest.to_dict(),
                "check_in": self.stay.check_in.isoformat(),
                "check_out": self.stay.check_out.isoformat(),
                "status": self.status.value, "notes": self.notes,
                "history": [[status.value, day]
                            for status, day in self.history]}


# --------------------------------------------------------------------------- #
# The hotel
# --------------------------------------------------------------------------- #
class Hotel:
    """Rooms, bookings and the rules that join them."""

    def __init__(self, name: str = "Ledger Hotel"):
        if not isinstance(name, str) or not name.strip():
            raise HotelError("the hotel needs a name")
        self.name = name.strip()
        self._rooms: dict[str, Room] = {}
        self._bookings: dict[str, Booking] = {}
        self._sequence = 0

    # -- rooms ------------------------------------------------------------- #
    def add_room(self, room: Room) -> Room:
        if not isinstance(room, Room):
            raise HotelError("only a Room can be added")
        if room.number in self._rooms:
            raise HotelError(f"room {room.number} is already in the hotel")
        self._rooms[room.number] = room
        return room

    @property
    def rooms(self) -> tuple[Room, ...]:
        return tuple(self._rooms[key] for key in sorted(self._rooms))

    def room(self, number) -> Room:
        try:
            return self._rooms[str(number)]
        except KeyError:
            raise HotelError(f"no room {number!r}") from None

    @property
    def bookings(self) -> tuple[Booking, ...]:
        return tuple(self._bookings[key] for key in sorted(self._bookings))

    def booking(self, reference) -> Booking:
        try:
            return self._bookings[str(reference)]
        except KeyError:
            raise HotelError(f"no booking {reference!r}") from None

    def __len__(self) -> int:
        return len(self._bookings)

    def __iter__(self):
        return iter(self.bookings)

    def __contains__(self, reference) -> bool:
        return str(reference) in self._bookings

    def __repr__(self) -> str:
        return (f"<Hotel {self.name!r} {len(self._rooms)} rooms "
                f"{len(self._bookings)} bookings>")

    # -- availability ------------------------------------------------------ #
    def clashes(self, room: Room, stay: Stay, ignore=None) -> list[Booking]:
        """Bookings on that room whose nights intersect ``stay``."""
        found = []
        for booking in self.bookings:
            if booking.room != room or not booking.holds_room:
                continue
            if ignore is not None and booking.reference == ignore:
                continue
            if booking.stay.overlaps(stay):
                found.append(booking)
        return found

    def is_free(self, number, stay) -> bool:
        stay = stay if isinstance(stay, Stay) else Stay.of(*stay)
        return not self.clashes(self.room(number), stay)

    def free_rooms(self, stay) -> list[Room]:
        stay = stay if isinstance(stay, Stay) else Stay.of(*stay)
        return [room for room in self.rooms if not self.clashes(room, stay)]

    # -- booking ----------------------------------------------------------- #
    def book(self, number, guest, stay, status=Status.CONFIRMED,
             notes="") -> Booking:
        room = self.room(number)
        if not isinstance(guest, Guest):
            raise HotelError("a booking needs a Guest")
        if not isinstance(stay, Stay):
            stay = Stay.of(*stay) if isinstance(stay, (tuple, list)) else stay
        if not isinstance(stay, Stay):
            raise HotelError("a booking needs a Stay")
        if status not in ACTIVE:
            raise HotelError(f"a new booking cannot start as {status.value}")
        found = self.clashes(room, stay)
        if found:
            raise HotelError(
                f"room {room.number} is taken on {stay}: "
                f"{', '.join(booking.reference for booking in found)}")
        self._sequence += 1
        booking = Booking(f"BK-{self._sequence:04d}", room, guest, stay,
                          status, notes=notes)
        self._bookings[booking.reference] = booking
        return booking

    def cancel(self, reference, day) -> Booking:
        return self.booking(reference).cancel(day)

    def check_in(self, reference, day) -> Booking:
        return self.booking(reference).check_in(day)

    def check_out(self, reference, day) -> Booking:
        return self.booking(reference).check_out(day)

    # -- reports ----------------------------------------------------------- #
    def occupancy(self, stay) -> dict:
        stay = stay if isinstance(stay, Stay) else Stay.of(*stay)
        sold = 0
        revenue = 0
        for room in self.rooms:
            for day in stay.each_night():
                night = Stay(day, day + timedelta(days=1))
                taken = [booking for booking in self.bookings
                         if booking.room == room and booking.holds_room
                         and booking.stay.overlaps(night)]
                if taken:
                    sold += 1
                    revenue += taken[0].room.rate.for_night(day)
        capacity = len(self.rooms) * stay.nights
        percent = (sold * 10000 // capacity) if capacity else 0
        return {"nights": stay.nights, "capacity": capacity, "sold": sold,
                "vacant": capacity - sold, "basis_points": percent,
                "revenue": revenue}

    def revenue(self) -> int:
        return sum(booking.price() for booking in self.bookings
                   if booking.status is not Status.CANCELLED)

    def consistency(self) -> list[tuple[str, bool]]:
        """Four invariants over the bookings."""
        checks = []
        overlapping = True
        seen: list[Booking] = []
        for booking in self.bookings:
            if not booking.holds_room:
                continue
            for other in seen:
                if other.room == booking.room and other.stay.overlaps(
                        booking.stay):
                    overlapping = False
            seen.append(booking)
        checks.append(("no two active bookings overlap", overlapping))
        checks.append(("every booking names a room in the hotel",
                       all(booking.room.number in self._rooms
                           for booking in self.bookings)))
        checks.append(("a checked-in booking starts on its arrival date",
                       all(booking.history and booking.history[-1][1] ==
                           booking.stay.check_in.isoformat()
                           for booking in self.bookings
                           if booking.status is Status.CHECKED_IN)))
        checks.append(("a cancelled booking holds no room",
                       all(not booking.holds_room for booking in self.bookings
                           if booking.status is Status.CANCELLED)))
        return checks

    def problems(self) -> list[str]:
        return [name for name, passed in self.consistency() if not passed]

    # -- persistence ------------------------------------------------------- #
    def to_dict(self) -> dict:
        return {"name": self.name, "sequence": self._sequence,
                "rooms": [room.to_dict() for room in self.rooms],
                "bookings": [booking.to_dict() for booking in self.bookings]}

    @classmethod
    def from_dict(cls, payload) -> "Hotel":
        if not isinstance(payload, dict):
            raise HotelError("a hotel document must be an object")
        unknown = set(payload) - {"name", "sequence", "rooms", "bookings"}
        if unknown:
            raise HotelError(f"unknown hotel keys: {sorted(unknown)}")
        for key in ("name", "rooms", "bookings"):
            if key not in payload:
                raise HotelError(f"the hotel document is missing {key!r}")
        hotel = cls(payload["name"])
        if not isinstance(payload["rooms"], list):
            raise HotelError("'rooms' must be a list")
        if not isinstance(payload["bookings"], list):
            raise HotelError("'bookings' must be a list")
        for row in payload["rooms"]:
            if not isinstance(row, dict):
                raise HotelError("a room must be an object")
            unknown = set(row) - {"number", "kind", "capacity", "rate"}
            if unknown:
                raise HotelError(f"unknown room keys: {sorted(unknown)}")
            for key in ("number", "kind", "capacity", "rate"):
                if key not in row:
                    raise HotelError(f"a room is missing {key!r}")
            hotel.add_room(Room(row["number"], row["kind"],
                                rate_from_dict(row["rate"]), row["capacity"]))
        for row in payload["bookings"]:
            hotel._restore(row)
        sequence = payload.get("sequence", 0)
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            raise HotelError("'sequence' must be a whole number")
        if sequence < len(hotel):
            raise HotelError("'sequence' cannot be smaller than the number "
                             "of bookings")
        hotel._sequence = sequence
        return hotel

    def _restore(self, row) -> Booking:
        if not isinstance(row, dict):
            raise HotelError("a booking must be an object")
        unknown = set(row) - {"reference", "room", "guest", "check_in",
                              "check_out", "status", "notes", "history"}
        if unknown:
            raise HotelError(f"unknown booking keys: {sorted(unknown)}")
        for key in ("reference", "room", "guest", "check_in", "check_out",
                    "status"):
            if key not in row:
                raise HotelError(f"a booking is missing {key!r}")
        guest_row = row["guest"]
        if not isinstance(guest_row, dict):
            raise HotelError("a guest must be an object")
        if set(guest_row) != {"name", "phone", "email"}:
            raise HotelError("a guest needs exactly name, phone and email")
        guest = Guest(guest_row["name"], guest_row["phone"],
                      guest_row["email"])
        stay = Stay.of(row["check_in"], row["check_out"])
        try:
            status = Status(row["status"])
        except ValueError:
            raise HotelError(f"{row['status']!r} is not a booking status") \
                from None
        history = []
        for entry in row.get("history", []):
            if not isinstance(entry, list) or len(entry) != 2:
                raise HotelError("a history entry is [status, date]")
            try:
                history.append((Status(entry[0]), as_date(entry[1]).isoformat()))
            except ValueError:
                raise HotelError(f"{entry[0]!r} is not a booking status") \
                    from None
        booking = Booking(row["reference"], self.room(row["room"]), guest,
                          stay, status, history, row.get("notes", ""))
        if booking.reference in self._bookings:
            raise HotelError(f"{booking.reference} appears twice")
        self._bookings[booking.reference] = booking
        return booking


def load_hotel(path=DATA_FILE) -> Hotel:
    path = Path(path)
    if not path.exists():
        raise HotelError(f"hotel file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HotelError(f"{path.name} is not valid JSON: {exc}") from None
    return Hotel.from_dict(payload)


def save_hotel(path, hotel: Hotel) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(hotel.to_dict(), indent=2) + "\n",
                    encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    import sqlite3

    print("=" * 74)
    print(" HOTEL - dates a booking needs, a state machine, a rate strategy")
    print("=" * 74)

    # 1. the legacy overlap test makes back-to-back stays collide
    leaving = Stay.of("2026-03-10", "2026-03-12")
    arriving = Stay.of("2026-03-12", "2026-03-14")
    assert not leaving.overlaps(arriving)
    assert legacy_overlaps(leaving.check_in, leaving.check_out,
                          arriving.check_in, arriving.check_out)
    assert arriving.overlaps(Stay.of("2026-03-13", "2026-03-15"))
    print(f"  a guest out on the 12th and one in on the 12th: overlaps() "
          f"False, legacy_overlaps() True")

    # 2. the legacy status column accepted any string
    namespace = {"room": type("Room", (), {"status": "Available"})()}
    exec(LEGACY_STATUS, namespace)                      # noqa: S102
    namespace["room"].status = "Occupied"
    namespace["room"].status = "Somehow Occupied"
    assert namespace["room"].status == "Somehow Occupied"
    try:
        Booking("BK-9001", Room("999", "Single", FlatRate(1000)),
                Guest("A B", "1234567890", "a@b.co"),
                Stay.of("2026-03-01", "2026-03-02")).check_out("2026-03-02")
    except BookingError as exc:
        refused = str(exc)
    else:
        raise AssertionError("a confirmed booking checked out")
    assert "allowed from here: checked_in, cancelled" in refused
    print(f"  legacy 'room.status' took any string; a confirmed booking "
          f"cannot check out: {refused}")

    # 3. integer cents per night, and three strategies
    flat = FlatRate(8500)
    weekend = WeekendRate(11000, 14000)
    season = SeasonRate(20000, "2026-06-01", "2026-09-01", 2500)
    march = Stay.of("2026-03-02", "2026-03-06")          # Mon..Thu
    assert flat.total(march) == 4 * 8500
    assert weekend.total(march) == 4 * 11000
    fri_to_sun = Stay.of("2026-03-06", "2026-03-08")     # Fri, Sat
    assert weekend.total(fri_to_sun) == 2 * 14000
    assert [day.weekday() for day in fri_to_sun.each_night()] == [4, 5]
    peak = Stay.of("2026-06-01", "2026-06-03")
    assert season.total(peak) == 2 * 25000
    assert season.for_night(date(2026, 5, 31)) == 20000
    assert SeasonRate(12000, "2026-06-01", "2026-09-01", 1250).for_night(
        date(2026, 6, 1)) == 13500
    assert SeasonRate(1, "2026-06-01", "2026-09-01", 5000).for_night(
        date(2026, 6, 1)) == 2                            # 1.5 cents -> 2
    print(f"  rates: 4 weeknights flat {flat.total(march)}, weekend "
          f"{weekend.total(march)}, Fri+Sat {weekend.total(fri_to_sun)}, "
          f"2 peak nights {season.total(peak)}")

    # 4. a stay is half-open, and only real dates are accepted
    assert Stay.of("2026-03-02", "2026-03-05").nights == 3
    assert list(Stay.of("2026-03-02", "2026-03-05").each_night())[-1] == \
        date(2026, 3, 4)
    assert Stay.of("2026-03-02", "2026-03-05").contains(date(2026, 3, 2))
    assert not Stay.of("2026-03-02", "2026-03-05").contains(date(2026, 3, 5))
    refused = 0
    for bad in (("2026-03-05", "2026-03-05"), ("2026-03-05", "2026-03-02"),
                ("2026-3-5", "2026-03-06"), ("2026-02-30", "2026-03-02")):
        try:
            Stay.of(*bad)
        except HotelError:
            refused += 1
        else:
            raise AssertionError(f"{bad} should have been refused")
    assert refused == 4
    print(f"  3 nights from the 2nd ends on the 4th; 4 impossible stays "
          f"refused (same day, backwards, unpadded, the 30th of February)")

    # 5. the room refuses a second, overlapping booking
    hotel = Hotel("Demo Hotel")
    hotel.add_room(Room("101", "Single", flat, capacity=1))
    hotel.add_room(Room("102", "Double", weekend, capacity=2))
    first = hotel.book("101", Guest("Asha Rao", "9876543210",
                                    "asha@example.com"), march)
    assert first.reference == "BK-0001"
    try:
        hotel.book("101", Guest("Bilal Khan", "9876543211",
                                "bilal@example.com"),
                   Stay.of("2026-03-04", "2026-03-07"))
    except HotelError as exc:
        clash = str(exc)
    else:
        raise AssertionError("an overlapping booking was accepted")
    assert "BK-0001" in clash
    second = hotel.book("101", Guest("Bilal Khan", "9876543211",
                                     "bilal@example.com"),
                        Stay.of("2026-03-06", "2026-03-08"))
    assert second.reference == "BK-0002"
    assert hotel.is_free("101", Stay.of("2026-03-20", "2026-03-22"))
    assert hotel.free_rooms(march) == [hotel.room("102")]
    print(f"  a clash names the booking that owns the room ({clash[:38]}...), "
          f"and check-out day is free for the next guest")

    # 6. the state machine, move by move
    assert first.status is Status.CONFIRMED
    first.check_in("2026-03-02")
    assert first.status is Status.CHECKED_IN
    try:
        first.check_in("2026-03-03")
    except BookingError as exc:
        move_message = str(exc)
    else:
        raise AssertionError("check-in ran twice")
    first.check_out("2026-03-06")
    assert first.status is Status.CHECKED_OUT
    final_move = ""
    for method, day in ((first.cancel, "2026-03-07"),
                        (first.check_in, "2026-03-07"),
                        (first.check_out, "2026-03-07")):
        try:
            method(day)
        except BookingError as exc:
            final_move = str(exc)
        else:
            raise AssertionError("a finished booking moved again")
    third = hotel.book("102", Guest("Chen Wei", "9876543212",
                                    "chen@example.com"), fri_to_sun)
    third.cancel("2026-03-01")
    assert third.status is Status.CANCELLED and not third.holds_room
    assert "checked_out; allowed from here: nothing" in final_move
    print(f"  confirmed -> checked_in -> checked_out; then every move is "
          f"refused ({final_move[:44]}...)")

    # 7. guests are validated, and SQLite would not have done it
    refused_guests = 0
    for name, phone, email in (
            ("A", "123", "a@b.co"),
            ("A", "12345678901", "a@b.co"),
            ("A", "12345abcde", "a@b.co"),
            ("A", "1234567890", "not-an-email"),
            ("   ", "1234567890", "a@b.co")):
        try:
            Guest(name, phone, email)
        except HotelError:
            refused_guests += 1
        else:
            raise AssertionError(f"{name!r}/{phone!r}/{email!r} was accepted")
    assert refused_guests == 5
    assert Guest(" Asha ", "9876543210", "ASHA@Example.COM").email == \
        "asha@example.com"
    with sqlite3.connect(":memory:") as memory:
        memory.execute("CREATE TABLE guests (phone VARCHAR(10))")
        memory.execute("INSERT INTO guests VALUES (?)", ("9" * 40,))
        stored = memory.execute("SELECT length(phone) FROM guests").fetchone()
    assert stored == (40,)
    print(f"  {refused_guests} bad guests refused; SQLite VARCHAR(10) still "
          f"stored {stored[0]} characters")

    # 8. the seeded hotel is consistent and priced
    seeded = load_hotel()
    assert len(seeded.rooms) == 6 and len(seeded) == 5
    assert all(passed for _, passed in seeded.consistency()), \
        seeded.problems()
    back_to_back = [booking for booking in seeded.bookings
                    if booking.room.number == "101"]
    assert [booking.stay.check_in.isoformat() for booking in back_to_back] == \
        ["2026-03-02", "2026-03-05"]
    assert back_to_back[0].stay.check_out == back_to_back[1].stay.check_in
    assert not back_to_back[0].stay.overlaps(back_to_back[1].stay)
    report = seeded.occupancy(Stay.of("2026-03-02", "2026-03-05"))
    assert report["nights"] == 3 and report["capacity"] == 18
    assert report["sold"] == 5
    assert report["vacant"] == 13
    assert report["basis_points"] == 2777            # 5/18, truncated
    assert report["revenue"] == 47500               # 3 x 8500 + 2 x 11000
    assert seeded.revenue() == 117500
    print(f"  seeded: 6 rooms, 5 bookings (one cancelled), room 101 booked "
          f"back to back on the 5th, occupancy {report['sold']}/"
          f"{report['capacity']} nights = {report['basis_points']} bp, "
          f"revenue {seeded.revenue()} cents")

    # 9. save and load
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "copy.json"
        save_hotel(target, seeded)
        first_bytes = target.read_bytes()
        save_hotel(target, load_hotel(target))
        assert target.read_bytes() == first_bytes
        assert load_hotel(target).to_dict() == seeded.to_dict()
    print("  the seeded hotel saves and reloads byte for byte")

    print()
    print("Cross-checks OK: the legacy inclusive test made a stay ending on "
          "the 12th collide with one starting on the 12th while half-open "
          "intervals did not, the legacy status column stored any string and "
          "a confirmed booking refused to check out, 3 rate strategies priced "
          "the same 4 nights at 34000 / 44000 / 28000 / 50000 cents and a "
          "12.5% peak moved 12000 to 13500 with 1.5 cents rounding to 2, 4 "
          "impossible stays were refused, an overlapping booking was refused "
          "by reference while the check-out day stayed free, a booking walked "
          "confirmed -> checked_in -> checked_out and then refused every "
          "further move, 5 bad guests were refused, SQLite stored a 40 "
          "character phone in a VARCHAR(10), the seeded hotel was consistent "
          "with a back-to-back pair on room 101 at 5/18 nights and 117500 "
          "cents of revenue, and it round-tripped byte for byte")
    print("\nDemo completed successfully.")
    return 0
