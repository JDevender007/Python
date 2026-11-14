"""Tests for Hotel_Management_System: stays, rates, the state machine, the hotel."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                        # noqa: E402
from hotel import (                                       # noqa: E402
    ACTIVE,
    ALLOWED,
    DATA_FILE,
    LEGACY_OVERLAP,
    LEGACY_STATUS,
    WEEKEND_NIGHTS,
    Booking,
    BookingError,
    FlatRate,
    Guest,
    Hotel,
    HotelError,
    Rate,
    Room,
    SeasonRate,
    Status,
    Stay,
    WeekendRate,
    as_date,
    legacy_overlaps,
    load_hotel,
    rate_from_dict,
    run_demo,
    save_hotel,
)

MARCH = Stay.of("2026-03-02", "2026-03-05")            # Mon, Tue, Wed


def a_guest(name="Asha Rao", phone="9876543210", email="asha@example.com"):
    return Guest(name, phone, email)


def a_room(number="101", rate=None, kind="Single", capacity=1):
    return Room(number, kind, FlatRate(8500) if rate is None else rate,
                capacity)


@pytest.fixture()
def hotel() -> Hotel:
    house = Hotel("Test Hotel")
    house.add_room(Room("101", "Single", FlatRate(8500), 1))
    house.add_room(Room("102", "Double", WeekendRate(11000, 14000), 2))
    house.add_room(Room("201", "Suite",
                        SeasonRate(20000, "2026-06-01", "2026-09-01", 2500), 4))
    return house


# --------------------------------------------------------------------------- #
# as_date
# --------------------------------------------------------------------------- #
def test_as_date_accepts_iso():
    assert as_date("2026-03-02") == date(2026, 3, 2)


def test_as_date_accepts_a_date_object():
    assert as_date(date(2026, 3, 2)) == date(2026, 3, 2)


@pytest.mark.parametrize("bad", ["2026-3-2", "2026-03-2", "2026/03/02",
                                 "02-03-2026", "2026-03", "20260302", ""])
def test_as_date_refuses_non_canonical_shapes(bad):
    with pytest.raises(HotelError):
        as_date(bad)


def test_as_date_refuses_the_30th_of_february():
    with pytest.raises(HotelError, match="not a real date"):
        as_date("2026-02-30")


def test_as_date_refuses_a_non_date():
    with pytest.raises(HotelError, match="must be a date"):
        as_date(20260302)


def test_as_date_refuses_a_boolean():
    with pytest.raises(HotelError, match="must be a date"):
        as_date(True)


def test_as_date_uses_the_label_in_its_message():
    with pytest.raises(HotelError, match="the check-out must be a date"):
        as_date(5, "the check-out")


# --------------------------------------------------------------------------- #
# Stay
# --------------------------------------------------------------------------- #
def test_a_stay_counts_its_nights():
    assert Stay.of("2026-03-02", "2026-03-05").nights == 3


def test_a_one_night_stay():
    assert Stay.of("2026-03-02", "2026-03-03").nights == 1


def test_a_stay_enumerates_its_nights():
    assert [day.isoformat() for day in MARCH.each_night()] == [
        "2026-03-02", "2026-03-03", "2026-03-04"]


def test_a_stay_contains_its_first_night():
    assert MARCH.contains(date(2026, 3, 2))


def test_a_stay_does_not_contain_its_checkout_day():
    assert not MARCH.contains(date(2026, 3, 5))


def test_a_stay_does_not_contain_a_day_before_it():
    assert not MARCH.contains(date(2026, 3, 1))


def test_a_stay_reports_itself_as_two_iso_dates():
    assert str(MARCH) == "2026-03-02..2026-03-05"


def test_back_to_back_stays_do_not_overlap():
    leaving = Stay.of("2026-03-02", "2026-03-05")
    arriving = Stay.of("2026-03-05", "2026-03-07")
    assert not leaving.overlaps(arriving)
    assert not arriving.overlaps(leaving)


def test_stays_sharing_a_night_overlap():
    assert MARCH.overlaps(Stay.of("2026-03-04", "2026-03-06"))


def test_a_stay_inside_another_overlaps_it():
    assert MARCH.overlaps(Stay.of("2026-03-03", "2026-03-04"))


def test_disjoint_stays_do_not_overlap():
    assert not MARCH.overlaps(Stay.of("2026-03-10", "2026-03-12"))


def test_a_zero_night_stay_is_refused():
    with pytest.raises(HotelError, match="not after the check-in"):
        Stay.of("2026-03-02", "2026-03-02")


def test_a_backwards_stay_is_refused():
    with pytest.raises(HotelError, match="not after the check-in"):
        Stay.of("2026-03-05", "2026-03-02")


def test_a_stay_needs_two_dates():
    with pytest.raises(HotelError, match="needs two dates"):
        Stay("2026-03-02", date(2026, 3, 5))


def test_a_stay_is_frozen():
    with pytest.raises(Exception):
        MARCH.check_in = date(2026, 3, 9)                 # type: ignore[misc]


def test_stays_of_equal_dates_are_equal():
    assert Stay.of("2026-03-02", "2026-03-05") == MARCH


# --------------------------------------------------------------------------- #
# The legacy overlap
# --------------------------------------------------------------------------- #
def test_the_legacy_test_collides_on_back_to_back_stays():
    assert legacy_overlaps(date(2026, 3, 2), date(2026, 3, 5),
                           date(2026, 3, 5), date(2026, 3, 7))


def test_the_legacy_test_agrees_with_the_fixed_one_when_stays_clash():
    assert legacy_overlaps(date(2026, 3, 2), date(2026, 3, 5),
                           date(2026, 3, 4), date(2026, 3, 6))


# --------------------------------------------------------------------------- #
# FlatRate
# --------------------------------------------------------------------------- #
def test_a_flat_rate_is_the_same_every_night():
    rate = FlatRate(8500)
    assert rate.for_night(date(2026, 3, 2)) == 8500
    assert rate.for_night(date(2026, 3, 7)) == 8500


def test_a_flat_rate_totals_a_stay():
    assert FlatRate(8500).total(MARCH) == 25500


def test_a_flat_rate_describes_itself():
    assert FlatRate(8500).describe() == "FlatRate 8500"


def test_a_flat_rate_round_trips_through_a_dict():
    assert rate_from_dict(FlatRate(8500).to_dict()) == FlatRate(8500)


def test_flat_rates_are_equal_by_value():
    assert FlatRate(8500) == FlatRate(8500)
    assert FlatRate(8500) != FlatRate(7500)


def test_a_rate_is_hashable():
    assert len({FlatRate(8500), FlatRate(8500), FlatRate(7500)}) == 2


def test_rates_of_different_classes_are_not_equal():
    assert FlatRate(11000) != WeekendRate(11000, 11000)


def test_a_rate_refuses_a_float_price():
    with pytest.raises(HotelError, match="integer number of cents"):
        FlatRate(85.0)


def test_a_rate_refuses_a_negative_price():
    with pytest.raises(HotelError, match="must not be negative"):
        FlatRate(-1)


def test_a_rate_refuses_a_boolean_price():
    with pytest.raises(HotelError, match="integer number of cents"):
        FlatRate(True)


def test_the_rate_base_class_cannot_be_instantiated():
    with pytest.raises(TypeError):
        Rate()                                            # type: ignore[abstract]


# --------------------------------------------------------------------------- #
# WeekendRate
# --------------------------------------------------------------------------- #
def test_the_weekend_nights_are_friday_and_saturday():
    assert WEEKEND_NIGHTS == (4, 5)


def test_a_weekend_rate_charges_the_weekday_price_on_monday():
    assert WeekendRate(11000, 14000).for_night(date(2026, 3, 2)) == 11000


def test_a_weekend_rate_charges_the_weekend_price_on_friday():
    assert WeekendRate(11000, 14000).for_night(date(2026, 3, 6)) == 14000


def test_a_weekend_rate_charges_the_weekend_price_on_saturday():
    assert WeekendRate(11000, 14000).for_night(date(2026, 3, 7)) == 14000


def test_a_weekend_rate_charges_the_weekday_price_on_sunday():
    assert WeekendRate(11000, 14000).for_night(date(2026, 3, 8)) == 11000


def test_a_weekend_rate_totals_three_weeknights():
    assert WeekendRate(11000, 14000).total(MARCH) == 33000


def test_a_weekend_rate_totals_friday_and_saturday():
    assert WeekendRate(11000, 14000).total(
        Stay.of("2026-03-06", "2026-03-08")) == 28000


def test_a_weekend_rate_describes_both_prices():
    assert WeekendRate(11000, 14000).describe() == "WeekendRate 11000/14000"


def test_a_weekend_rate_refuses_a_negative_weekday_price():
    with pytest.raises(HotelError, match="the weekday price"):
        WeekendRate(-1, 14000)


def test_a_weekend_rate_round_trips():
    assert rate_from_dict(WeekendRate(11000, 14000).to_dict()) == \
        WeekendRate(11000, 14000)


# --------------------------------------------------------------------------- #
# SeasonRate
# --------------------------------------------------------------------------- #
def test_a_season_rate_charges_the_base_outside_the_peak():
    rate = SeasonRate(20000, "2026-06-01", "2026-09-01", 2500)
    assert rate.for_night(date(2026, 5, 31)) == 20000


def test_a_season_rate_charges_the_base_on_the_peak_start():
    rate = SeasonRate(20000, "2026-06-01", "2026-09-01", 2500)
    assert rate.for_night(date(2026, 6, 1)) == 25000


def test_a_season_rate_charges_the_base_after_the_peak_end():
    rate = SeasonRate(20000, "2026-06-01", "2026-09-01", 2500)
    assert rate.for_night(date(2026, 9, 1)) == 20000


def test_a_season_rate_totals_peak_nights():
    rate = SeasonRate(20000, "2026-06-01", "2026-09-01", 2500)
    assert rate.total(Stay.of("2026-06-01", "2026-06-03")) == 50000


def test_a_season_rate_rounds_half_up():
    rate = SeasonRate(1, "2026-06-01", "2026-09-01", 5000)
    assert rate.for_night(date(2026, 6, 1)) == 2        # 1.5 cents -> 2


def test_a_season_rate_rounds_a_third_of_a_cent_down():
    rate = SeasonRate(1, "2026-06-01", "2026-09-01", 4000)
    assert rate.for_night(date(2026, 6, 1)) == 1        # 1.4 cents -> 1


def test_a_season_rate_round_trips():
    rate = SeasonRate(20000, "2026-06-01", "2026-09-01", 2500)
    assert rate_from_dict(rate.to_dict()) == rate


def test_a_season_rate_refuses_a_float_basis_points():
    with pytest.raises(HotelError, match="basis points"):
        SeasonRate(100, "2026-06-01", "2026-09-01", 25.0)


def test_a_season_rate_refuses_a_peak_above_one_hundred_percent():
    with pytest.raises(HotelError, match="between 0 and 100000"):
        SeasonRate(100, "2026-06-01", "2026-09-01", 100001)


def test_a_season_rate_refuses_a_backwards_peak():
    with pytest.raises(HotelError):
        SeasonRate(100, "2026-09-01", "2026-06-01", 2500)


# --------------------------------------------------------------------------- #
# rate_from_dict
# --------------------------------------------------------------------------- #
def test_rate_from_dict_refuses_a_non_object():
    with pytest.raises(HotelError, match="must be an object"):
        rate_from_dict([])


def test_rate_from_dict_refuses_an_unknown_kind():
    with pytest.raises(HotelError, match="not a rate kind"):
        rate_from_dict({"kind": "monthly"})


def test_rate_from_dict_refuses_a_missing_price():
    with pytest.raises(HotelError, match="integer number of cents"):
        rate_from_dict({"kind": "flat"})


# --------------------------------------------------------------------------- #
# Guest
# --------------------------------------------------------------------------- #
def test_a_guest_trims_the_name():
    assert Guest("  Asha Rao  ", "9876543210", "a@b.co").name == "Asha Rao"


def test_a_guest_lowercases_its_email():
    assert Guest("A", "9876543210", "ASHA@Example.COM").email == \
        "asha@example.com"


def test_a_guest_reports_its_name():
    assert str(a_guest()) == "Asha Rao"


@pytest.mark.parametrize("bad", [("", "9876543210", "a@b.co"),
                                 ("   ", "9876543210", "a@b.co")])
def test_a_guest_needs_a_name(bad):
    with pytest.raises(HotelError, match="needs a name"):
        Guest(*bad)


@pytest.mark.parametrize("phone", ["123", "12345678901", "12345abcde",
                                   "98765 43210", "", "+919876543210"])
def test_a_guest_needs_ten_digits(phone):
    with pytest.raises(HotelError, match="exactly 10 digits"):
        Guest("A", phone, "a@b.co")


@pytest.mark.parametrize("email", ["not-an-email", "a.b.co", "",
                                   "asha.example.com"])
def test_a_guest_needs_an_email(email):
    with pytest.raises(HotelError, match="is not an email address"):
        Guest("A", "9876543210", email)


def test_the_email_test_is_deliberately_loose():
    """`@` plus a dot after it is the whole rule; the demo says so."""
    assert Guest("A", "9876543210", "a@.co").email == "a@.co"
    assert Guest("A", "9876543210", "@b.co").email == "@b.co"


def test_a_guest_is_frozen():
    with pytest.raises(Exception):
        a_guest().name = "B"                              # type: ignore[misc]


def test_a_guest_round_trips():
    guest = a_guest()
    assert Guest(**guest.to_dict()) == guest


# --------------------------------------------------------------------------- #
# Room
# --------------------------------------------------------------------------- #
def test_a_room_titles_its_kind():
    assert Room("101", "single", FlatRate(8500)).kind == "Single"


def test_a_room_prices_a_stay():
    assert a_room().price(MARCH) == 25500


def test_a_room_equals_another_with_the_same_number():
    assert a_room("101") == a_room("101", rate=FlatRate(9999))


def test_a_room_differs_by_number():
    assert a_room("101") != a_room("102")


def test_a_room_hashes_by_number():
    assert len({a_room("101"), a_room("101")}) == 1


def test_a_room_repr_names_it():
    text = repr(a_room("101"))
    assert "101" in text and "Single" in text and "FlatRate 8500" in text


def test_a_room_round_trips():
    room = Room("102", "Double", WeekendRate(11000, 14000), 2)
    assert Room(room.to_dict()["number"], room.to_dict()["kind"],
                rate_from_dict(room.to_dict()["rate"]),
                room.to_dict()["capacity"]) == room


def test_a_room_needs_a_number():
    with pytest.raises(HotelError, match="needs a number"):
        Room("  ", "Single", FlatRate(8500))


def test_a_room_needs_a_kind():
    with pytest.raises(HotelError, match="needs a type"):
        Room("101", "  ", FlatRate(8500))


def test_a_room_needs_a_rate_object():
    with pytest.raises(HotelError, match="needs a Rate"):
        Room("101", "Single", 8500)


def test_a_room_refuses_a_zero_capacity():
    with pytest.raises(HotelError, match="at least one"):
        Room("101", "Single", FlatRate(8500), 0)


def test_a_room_refuses_a_float_capacity():
    with pytest.raises(HotelError, match="whole number"):
        Room("101", "Single", FlatRate(8500), 2.0)


# --------------------------------------------------------------------------- #
# The state machine
# --------------------------------------------------------------------------- #
def test_the_status_values():
    assert [status.value for status in Status] == [
        "held", "confirmed", "checked_in", "checked_out", "cancelled"]


def test_held_can_be_confirmed_or_cancelled():
    assert ALLOWED[Status.HELD] == (Status.CONFIRMED, Status.CANCELLED)


def test_confirmed_can_check_in_or_cancel():
    assert ALLOWED[Status.CONFIRMED] == (Status.CHECKED_IN, Status.CANCELLED)


def test_checked_in_can_only_check_out():
    assert ALLOWED[Status.CHECKED_IN] == (Status.CHECKED_OUT,)


def test_a_finished_booking_can_do_nothing():
    assert ALLOWED[Status.CHECKED_OUT] == ()
    assert ALLOWED[Status.CANCELLED] == ()


def test_only_three_statuses_hold_a_room():
    assert ACTIVE == (Status.HELD, Status.CONFIRMED, Status.CHECKED_IN)
    assert Status.CHECKED_OUT not in ACTIVE


def a_booking(status=Status.CONFIRMED, stay=None, history=None):
    return Booking("BK-0001", a_room(), a_guest(), stay or MARCH, status,
                   history)


def test_a_new_booking_holds_its_room():
    assert a_booking().holds_room


def test_a_booking_confirms():
    booking = a_booking(Status.HELD)
    booking.confirm("2026-03-01")
    assert booking.status is Status.CONFIRMED


def test_confirming_a_confirmed_booking_is_refused():
    with pytest.raises(BookingError, match="allowed from here"):
        a_booking().confirm("2026-03-01")


def test_a_booking_checks_in_on_its_arrival_date():
    booking = a_booking()
    booking.check_in("2026-03-02")
    assert booking.status is Status.CHECKED_IN
    assert booking.history[-1] == (Status.CHECKED_IN, "2026-03-02")


def test_a_booking_refuses_a_check_in_before_the_stay():
    with pytest.raises(BookingError, match="outside"):
        a_booking().check_in("2026-03-01")


def test_a_booking_refuses_a_check_in_on_the_checkout_day():
    with pytest.raises(BookingError, match="outside"):
        a_booking().check_in("2026-03-05")


def test_a_booking_checks_out():
    booking = a_booking()
    booking.check_in("2026-03-02")
    booking.check_out("2026-03-05")
    assert booking.status is Status.CHECKED_OUT
    assert not booking.holds_room


def test_a_confirmed_booking_cannot_check_out():
    with pytest.raises(BookingError,
                       match="allowed from here: checked_in, cancelled"):
        a_booking().check_out("2026-03-05")


def test_a_held_booking_cannot_check_in():
    with pytest.raises(BookingError,
                       match="allowed from here: confirmed, cancelled"):
        a_booking(Status.HELD).check_in("2026-03-02")


def test_a_booking_cancels():
    booking = a_booking()
    booking.cancel("2026-03-01")
    assert booking.status is Status.CANCELLED and not booking.holds_room


def test_a_cancelled_booking_cannot_be_cancelled_again():
    booking = a_booking()
    booking.cancel("2026-03-01")
    with pytest.raises(BookingError, match="allowed from here: nothing"):
        booking.cancel("2026-03-02")


def test_a_checked_out_booking_cannot_move():
    booking = a_booking()
    booking.check_in("2026-03-02")
    booking.check_out("2026-03-05")
    with pytest.raises(BookingError, match="nothing"):
        booking.cancel("2026-03-06")


def test_a_move_records_its_date():
    booking = a_booking()
    booking.check_in("2026-03-03")
    assert booking.history == [(Status.CHECKED_IN, "2026-03-03")]


def test_a_move_to_a_non_status_is_refused():
    with pytest.raises(HotelError, match="is not a booking status"):
        a_booking()._move("checked_in", "2026-03-02")


def test_a_move_with_a_bad_date_is_refused():
    with pytest.raises(HotelError):
        a_booking().check_in("2026-3-2")


def test_a_booking_prices_its_stay():
    assert a_booking().price() == 25500


def test_a_booking_folio_lists_every_night():
    lines = a_booking().folio()
    assert "BK-0001" in lines[0] and "Asha Rao" in lines[0]
    assert len(lines) == 5                            # header, 3 nights, total
    assert lines[-1].strip().endswith("25500")


def test_a_booking_repr_names_it():
    text = repr(a_booking())
    assert "BK-0001" in text and "101" in text and "confirmed" in text


def test_a_booking_round_trips():
    booking = a_booking()
    booking.check_in("2026-03-02")
    payload = booking.to_dict()
    assert payload["status"] == "checked_in"
    assert payload["history"] == [["checked_in", "2026-03-02"]]
    assert payload["guest"]["name"] == "Asha Rao"


def test_a_booking_needs_a_reference():
    with pytest.raises(HotelError, match="needs a reference"):
        Booking("  ", a_room(), a_guest(), MARCH)


def test_a_booking_needs_a_room():
    with pytest.raises(HotelError, match="needs a Room"):
        Booking("BK-1", "101", a_guest(), MARCH)


def test_a_booking_needs_a_guest():
    with pytest.raises(HotelError, match="needs a Guest"):
        Booking("BK-1", a_room(), "Asha", MARCH)


def test_a_booking_needs_a_stay():
    with pytest.raises(HotelError, match="needs a Stay"):
        Booking("BK-1", a_room(), a_guest(), "2026-03-02")


def test_a_booking_needs_a_status():
    with pytest.raises(HotelError, match="is not a booking status"):
        Booking("BK-1", a_room(), a_guest(), MARCH, "confirmed")


# --------------------------------------------------------------------------- #
# The hotel
# --------------------------------------------------------------------------- #
def test_a_hotel_needs_a_name():
    with pytest.raises(HotelError, match="needs a name"):
        Hotel("   ")


def test_a_hotel_counts_its_rooms_and_bookings(hotel):
    assert len(hotel.rooms) == 3 and len(hotel) == 0


def test_a_hotel_looks_a_room_up_by_number(hotel):
    assert hotel.room("101").number == "101"


def test_a_hotel_refuses_an_unknown_room(hotel):
    with pytest.raises(HotelError, match="no room"):
        hotel.room("999")


def test_a_hotel_refuses_a_duplicate_room(hotel):
    with pytest.raises(HotelError, match="already in the hotel"):
        hotel.add_room(Room("101", "Double", FlatRate(9000)))


def test_a_hotel_refuses_a_non_room(hotel):
    with pytest.raises(HotelError, match="only a Room"):
        hotel.add_room("103")


def test_a_hotel_lists_rooms_in_number_order(hotel):
    assert [room.number for room in hotel.rooms] == ["101", "102", "201"]


def test_a_hotel_repr_names_it(hotel):
    assert "Test Hotel" in repr(hotel) and "3 rooms" in repr(hotel)


def test_a_hotel_books_and_numbers_the_booking(hotel):
    booking = hotel.book("101", a_guest(), MARCH)
    assert booking.reference == "BK-0001" and len(hotel) == 1


def test_a_hotel_numbers_bookings_in_sequence(hotel):
    assert hotel.book("101", a_guest(), MARCH).reference == "BK-0001"
    assert hotel.book("102", a_guest("Bilal Khan", "9876543211",
                                     "b@example.com"),
                      MARCH).reference == "BK-0002"


def test_a_hotel_contains_a_reference(hotel):
    hotel.book("101", a_guest(), MARCH)
    assert "BK-0001" in hotel and "BK-0009" not in hotel


def test_a_hotel_iterates_its_bookings(hotel):
    hotel.book("101", a_guest(), MARCH)
    assert [booking.reference for booking in hotel] == ["BK-0001"]


def test_a_hotel_refuses_a_clashing_booking(hotel):
    hotel.book("101", a_guest(), MARCH)
    with pytest.raises(HotelError, match="BK-0001"):
        hotel.book("101", a_guest("Bilal Khan", "9876543211",
                                  "b@example.com"),
                   Stay.of("2026-03-04", "2026-03-07"))


def test_a_hotel_allows_a_back_to_back_booking(hotel):
    hotel.book("101", a_guest(), MARCH)
    second = hotel.book("101", a_guest("Bilal Khan", "9876543211",
                                       "b@example.com"),
                        Stay.of("2026-03-05", "2026-03-07"))
    assert second.reference == "BK-0002"


def test_a_hotel_accepts_a_stay_as_two_dates(hotel):
    assert hotel.book("101", a_guest(), ("2026-03-02", "2026-03-05"))


def test_a_hotel_refuses_a_new_booking_that_already_finished(hotel):
    with pytest.raises(HotelError, match="cannot start as checked_out"):
        hotel.book("101", a_guest(), MARCH, Status.CHECKED_OUT)


def test_a_hotel_accepts_a_held_booking(hotel):
    assert hotel.book("101", a_guest(), MARCH, Status.HELD).status is \
        Status.HELD


def test_a_hotel_books_a_held_booking_like_any_other(hotel):
    hotel.book("101", a_guest(), MARCH, Status.HELD)
    with pytest.raises(HotelError, match="taken"):
        hotel.book("101", a_guest("C", "9876543212", "c@example.com"), MARCH)


def test_a_hotel_refuses_a_non_guest(hotel):
    with pytest.raises(HotelError, match="needs a Guest"):
        hotel.book("101", "Asha", MARCH)


def test_a_hotel_ignores_a_cancelled_booking_for_clashes(hotel):
    first = hotel.book("101", a_guest(), MARCH)
    first.cancel("2026-03-01")
    assert hotel.book("101", a_guest("Bilal Khan", "9876543211",
                                     "b@example.com"),
                      MARCH).reference == "BK-0002"


def test_a_hotel_ignore_argument_excludes_one_booking(hotel):
    first = hotel.book("101", a_guest(), MARCH)
    assert hotel.clashes(hotel.room("101"), MARCH)
    assert hotel.clashes(hotel.room("101"), MARCH,
                         ignore=first.reference) == []


def test_a_hotel_reports_availability(hotel):
    assert hotel.is_free("101", MARCH)
    hotel.book("101", a_guest(), MARCH)
    assert not hotel.is_free("101", MARCH)


def test_a_hotel_is_free_accepts_a_tuple(hotel):
    assert hotel.is_free("101", ("2026-03-02", "2026-03-05"))


def test_a_hotel_lists_the_free_rooms(hotel):
    hotel.book("101", a_guest(), MARCH)
    assert [room.number for room in hotel.free_rooms(MARCH)] == ["102", "201"]


def test_a_hotel_moves_a_booking_through_its_reference(hotel):
    hotel.book("101", a_guest(), MARCH)
    hotel.check_in("BK-0001", "2026-03-02")
    assert hotel.booking("BK-0001").status is Status.CHECKED_IN
    hotel.check_out("BK-0001", "2026-03-05")
    assert hotel.booking("BK-0001").status is Status.CHECKED_OUT


def test_a_hotel_cancels_through_its_reference(hotel):
    hotel.book("101", a_guest(), MARCH)
    hotel.cancel("BK-0001", "2026-03-01")
    assert hotel.booking("BK-0001").status is Status.CANCELLED


def test_a_hotel_refuses_an_unknown_booking(hotel):
    with pytest.raises(HotelError, match="no booking"):
        hotel.booking("BK-9999")


# --------------------------------------------------------------------------- #
# Occupancy and revenue
# --------------------------------------------------------------------------- #
def test_occupancy_of_an_empty_hotel(hotel):
    report = hotel.occupancy(MARCH)
    assert report == {"nights": 3, "capacity": 9, "sold": 0, "vacant": 9,
                      "basis_points": 0, "revenue": 0}


def test_occupancy_counts_sold_room_nights(hotel):
    hotel.book("101", a_guest(), MARCH)
    report = hotel.occupancy(MARCH)
    assert report["sold"] == 3 and report["vacant"] == 6
    assert report["basis_points"] == 3333


def test_occupancy_revenue_uses_the_rate_strategy(hotel):
    hotel.book("102", a_guest(), MARCH)               # Mon, Tue, Wed
    assert hotel.occupancy(MARCH)["revenue"] == 33000


def test_occupancy_stops_at_the_window_edges(hotel):
    hotel.book("101", a_guest(), Stay.of("2026-03-03", "2026-03-06"))
    report = hotel.occupancy(Stay.of("2026-03-02", "2026-03-05"))
    assert report["sold"] == 2                        # the 3rd and the 4th


def test_occupancy_ignores_a_cancelled_booking(hotel):
    hotel.book("101", a_guest(), MARCH).cancel("2026-03-01")
    assert hotel.occupancy(MARCH)["sold"] == 0


def test_occupancy_truncates_the_percentage(hotel):
    hotel.book("101", a_guest(), MARCH)
    assert hotel.occupancy(MARCH)["basis_points"] == 3333


def test_revenue_sums_every_live_booking(hotel):
    hotel.book("101", a_guest(), MARCH)               # 3 x 8500
    hotel.book("102", a_guest("B", "9876543211", "b@example.com"), MARCH)
    assert hotel.revenue() == 25500 + 33000


def test_revenue_ignores_a_cancelled_booking(hotel):
    hotel.book("101", a_guest(), MARCH).cancel("2026-03-01")
    assert hotel.revenue() == 0


def test_revenue_counts_a_checked_out_booking(hotel):
    hotel.book("101", a_guest(), MARCH)
    hotel.check_in("BK-0001", "2026-03-02")
    hotel.check_out("BK-0001", "2026-03-05")
    assert hotel.revenue() == 25500


# --------------------------------------------------------------------------- #
# Consistency
# --------------------------------------------------------------------------- #
def test_a_new_hotel_is_consistent(hotel):
    checks = hotel.consistency()
    assert len(checks) == 4
    assert all(passed for _, passed in checks)
    assert hotel.problems() == []


def test_consistency_names_its_checks(hotel):
    names = [name for name, _ in hotel.consistency()]
    assert "no two active bookings overlap" in names
    assert "a cancelled booking holds no room" in names


def test_consistency_catches_two_overlapping_bookings(hotel):
    first = hotel.book("101", a_guest(), MARCH)
    second = hotel.book("102", a_guest("B", "9876543211", "b@example.com"),
                        Stay.of("2026-03-10", "2026-03-12"))
    second.stay = MARCH
    second.room = first.room
    assert "no two active bookings overlap" in hotel.problems()


def test_consistency_catches_a_checked_in_booking_off_its_arrival(hotel):
    booking = hotel.book("101", a_guest(), MARCH)
    booking.status = Status.CHECKED_IN
    booking.history = [(Status.CHECKED_IN, "2026-03-03")]
    assert "a checked-in booking starts on its arrival date" in \
        hotel.problems()


def test_consistency_catches_a_checked_in_booking_without_history(hotel):
    booking = hotel.book("101", a_guest(), MARCH)
    booking.status = Status.CHECKED_IN
    booking.history = []
    assert "a checked-in booking starts on its arrival date" in \
        hotel.problems()


def test_consistency_passes_a_checked_in_booking_on_its_arrival(hotel):
    hotel.book("101", a_guest(), MARCH)
    hotel.check_in("BK-0001", "2026-03-02")
    assert hotel.problems() == []


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
def test_a_hotel_round_trips_through_a_dict(hotel):
    hotel.book("101", a_guest(), MARCH)
    hotel.book("201", a_guest("B", "9876543211", "b@example.com"),
               Stay.of("2026-06-01", "2026-06-03"))
    hotel.check_in("BK-0001", "2026-03-02")
    copy = Hotel.from_dict(hotel.to_dict())
    assert copy.to_dict() == hotel.to_dict()
    assert copy.revenue() == hotel.revenue()
    assert copy.consistency() == hotel.consistency()


def test_a_hotel_dict_records_the_sequence(hotel):
    hotel.book("101", a_guest(), MARCH)
    assert hotel.to_dict()["sequence"] == 1


def test_a_hotel_from_dict_refuses_a_non_object():
    with pytest.raises(HotelError, match="must be an object"):
        Hotel.from_dict([])


def test_a_hotel_from_dict_refuses_an_unknown_key():
    with pytest.raises(HotelError, match="unknown hotel keys"):
        Hotel.from_dict({"name": "x", "rooms": [], "bookings": [],
                         "extra": 1})


def test_a_hotel_from_dict_requires_its_keys():
    with pytest.raises(HotelError, match="missing 'bookings'"):
        Hotel.from_dict({"name": "x", "rooms": []})


def test_a_hotel_from_dict_refuses_a_non_list_of_rooms():
    with pytest.raises(HotelError, match="'rooms' must be a list"):
        Hotel.from_dict({"name": "x", "rooms": {}, "bookings": []})


def test_a_hotel_from_dict_refuses_a_non_list_of_bookings():
    with pytest.raises(HotelError, match="'bookings' must be a list"):
        Hotel.from_dict({"name": "x", "rooms": [], "bookings": {}})


def test_a_hotel_from_dict_refuses_a_non_object_room():
    with pytest.raises(HotelError, match="a room must be an object"):
        Hotel.from_dict({"name": "x", "rooms": [[]], "bookings": []})


def test_a_hotel_from_dict_refuses_an_unknown_room_key():
    with pytest.raises(HotelError, match="unknown room keys"):
        Hotel.from_dict({"name": "x", "rooms": [{"number": "101",
                                                 "kind": "Single",
                                                 "capacity": 1,
                                                 "rate": {"kind": "flat",
                                                          "cents": 8500},
                                                 "floor": 1}],
                         "bookings": []})


def test_a_hotel_from_dict_refuses_a_room_missing_a_key():
    with pytest.raises(HotelError, match="missing 'capacity'"):
        Hotel.from_dict({"name": "x", "rooms": [{"number": "101",
                                                 "kind": "Single",
                                                 "rate": {"kind": "flat",
                                                          "cents": 8500}}],
                         "bookings": []})


def test_a_hotel_from_dict_refuses_a_bad_sequence():
    with pytest.raises(HotelError, match="whole number"):
        Hotel.from_dict({"name": "x", "rooms": [], "bookings": [],
                         "sequence": "4"})


def test_a_hotel_from_dict_refuses_a_sequence_below_the_bookings():
    payload = {"name": "x", "sequence": 0,
               "rooms": [{"number": "101", "kind": "Single", "capacity": 1,
                          "rate": {"kind": "flat", "cents": 8500}}],
               "bookings": [{"reference": "BK-0001", "room": "101",
                             "guest": {"name": "A", "phone": "9876543210",
                                       "email": "a@b.co"},
                             "check_in": "2026-03-02",
                             "check_out": "2026-03-05",
                             "status": "confirmed"}]}
    with pytest.raises(HotelError, match="cannot be smaller"):
        Hotel.from_dict(payload)


def test_a_hotel_from_dict_refuses_a_non_object_booking():
    with pytest.raises(HotelError, match="a booking must be an object"):
        Hotel.from_dict({"name": "x", "rooms": [], "bookings": [[]]})


def test_a_hotel_from_dict_refuses_an_unknown_booking_key():
    with pytest.raises(HotelError, match="unknown booking keys"):
        Hotel.from_dict({"name": "x", "rooms": [], "bookings": [
            {"reference": "BK-0001", "room": "101", "guest": {},
             "check_in": "2026-03-02", "check_out": "2026-03-05",
             "status": "confirmed", "extras": 1}]})


def test_a_hotel_from_dict_refuses_a_booking_missing_a_key():
    with pytest.raises(HotelError, match="missing 'status'"):
        Hotel.from_dict({"name": "x", "rooms": [], "bookings": [
            {"reference": "BK-0001", "room": "101", "guest": {},
             "check_in": "2026-03-02", "check_out": "2026-03-05"}]})


def test_a_hotel_from_dict_refuses_a_non_object_guest():
    with pytest.raises(HotelError, match="a guest must be an object"):
        Hotel.from_dict({"name": "x", "rooms": [], "bookings": [
            {"reference": "BK-0001", "room": "101", "guest": "Asha",
             "check_in": "2026-03-02", "check_out": "2026-03-05",
             "status": "confirmed"}]})


def test_a_hotel_from_dict_refuses_a_guest_with_extra_keys():
    with pytest.raises(HotelError, match="exactly name, phone and email"):
        Hotel.from_dict({"name": "x", "rooms": [], "bookings": [
            {"reference": "BK-0001", "room": "101",
             "guest": {"name": "A", "phone": "9876543210",
                       "email": "a@b.co", "age": 30},
             "check_in": "2026-03-02", "check_out": "2026-03-05",
             "status": "confirmed"}]})


def test_a_hotel_from_dict_refuses_an_unknown_booking_status():
    with pytest.raises(HotelError, match="is not a booking status"):
        Hotel.from_dict({"name": "x", "rooms": [], "bookings": [
            {"reference": "BK-0001", "room": "101",
             "guest": {"name": "A", "phone": "9876543210",
                       "email": "a@b.co"},
             "check_in": "2026-03-02", "check_out": "2026-03-05",
             "status": "arrived"}]})


def test_a_hotel_from_dict_refuses_a_malformed_history_entry():
    with pytest.raises(HotelError, match="is \\[status, date\\]"):
        Hotel.from_dict({"name": "x", "rooms": [], "bookings": [
            {"reference": "BK-0001", "room": "101",
             "guest": {"name": "A", "phone": "9876543210",
                       "email": "a@b.co"},
             "check_in": "2026-03-02", "check_out": "2026-03-05",
             "status": "confirmed", "history": [["confirmed"]]}]})


def test_a_hotel_from_dict_refuses_a_bad_history_status():
    with pytest.raises(HotelError, match="is not a booking status"):
        Hotel.from_dict({"name": "x", "rooms": [], "bookings": [
            {"reference": "BK-0001", "room": "101",
             "guest": {"name": "A", "phone": "9876543210",
                       "email": "a@b.co"},
             "check_in": "2026-03-02", "check_out": "2026-03-05",
             "status": "confirmed",
             "history": [["arrived", "2026-03-01"]]}]})


def test_a_hotel_from_dict_refuses_a_duplicate_reference():
    row = {"reference": "BK-0001", "room": "101",
           "guest": {"name": "A", "phone": "9876543210",
                     "email": "a@b.co"},
           "check_in": "2026-03-02", "check_out": "2026-03-05",
           "status": "confirmed"}
    with pytest.raises(HotelError, match="appears twice"):
        Hotel.from_dict({"name": "x",
                         "rooms": [{"number": "101", "kind": "Single",
                                    "capacity": 1,
                                    "rate": {"kind": "flat", "cents": 8500}}],
                         "bookings": [row, row]})


def test_a_hotel_from_dict_refuses_a_booking_on_an_unknown_room():
    with pytest.raises(HotelError, match="no room"):
        Hotel.from_dict({"name": "x", "rooms": [], "bookings": [
            {"reference": "BK-0001", "room": "101",
             "guest": {"name": "A", "phone": "9876543210",
                       "email": "a@b.co"},
             "check_in": "2026-03-02", "check_out": "2026-03-05",
             "status": "confirmed"}]})


def test_the_data_file_is_named_for_its_purpose():
    assert DATA_FILE.name == "hotel.json"
    assert DATA_FILE.parent.name == "data"


def test_the_seeded_hotel_loads_and_is_consistent():
    seeded = load_hotel()
    assert len(seeded.rooms) == 6 and len(seeded) == 5
    assert seeded.problems() == []


def test_the_seeded_rooms_have_the_pinned_rates():
    rates = {room.number: room.rate for room in load_hotel().rooms}
    assert rates["101"] == FlatRate(8500)
    assert rates["102"] == WeekendRate(11000, 14000)
    assert rates["103"] == WeekendRate(12000, 15000)
    assert rates["201"] == SeasonRate(20000, "2026-06-01", "2026-09-01", 2500)
    assert rates["202"] == FlatRate(7500)
    assert rates["203"] == FlatRate(13500)


def test_the_seeded_revenue_is_pinned():
    assert load_hotel().revenue() == 117500


def test_the_seeded_occupancy_is_pinned():
    report = load_hotel().occupancy(Stay.of("2026-03-02", "2026-03-05"))
    assert report == {"nights": 3, "capacity": 18, "sold": 5, "vacant": 13,
                      "basis_points": 2777, "revenue": 47500}


def test_the_seeded_back_to_back_pair_touches():
    seeded = load_hotel()
    pair = [booking for booking in seeded.bookings
            if booking.room.number == "101"]
    assert len(pair) == 2
    assert pair[0].stay.check_out == pair[1].stay.check_in
    assert not pair[0].stay.overlaps(pair[1].stay)


def test_the_seeded_cancelled_booking_holds_nothing():
    cancelled = [booking for booking in load_hotel().bookings
                 if booking.status is Status.CANCELLED]
    assert len(cancelled) == 1 and not cancelled[0].holds_room


def test_the_seeded_checked_in_booking_has_two_history_entries():
    seeded = load_hotel()
    booking = seeded.booking("BK-0001")
    assert booking.status is Status.CHECKED_IN
    assert [status.value for status, _ in booking.history] == \
        ["confirmed", "checked_in"]


def test_load_hotel_refuses_a_missing_file(tmp_path):
    with pytest.raises(HotelError, match="not found"):
        load_hotel(tmp_path / "nope.json")


def test_load_hotel_refuses_invalid_json(tmp_path):
    path = tmp_path / "hotel.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(HotelError, match="not valid JSON"):
        load_hotel(path)


def test_save_hotel_writes_a_readable_file(tmp_path):
    seeded = load_hotel()
    target = tmp_path / "out.json"
    save_hotel(target, seeded)
    assert load_hotel(target).to_dict() == seeded.to_dict()


def test_save_hotel_creates_directories(tmp_path):
    target = tmp_path / "a" / "b" / "hotel.json"
    save_hotel(target, Hotel())
    assert target.is_file()


def test_save_hotel_ends_with_a_newline(tmp_path):
    target = tmp_path / "out.json"
    save_hotel(target, Hotel())
    assert target.read_text(encoding="utf-8").endswith("}\n")


def test_save_hotel_is_byte_identical_on_a_second_save(tmp_path):
    target = tmp_path / "out.json"
    seeded = load_hotel()
    save_hotel(target, seeded)
    first = target.read_bytes()
    save_hotel(target, load_hotel(target))
    assert target.read_bytes() == first


def test_the_legacy_constants_are_the_ones_the_demo_proves():
    assert LEGACY_STATUS == 'room.status = "Occupied"'
    assert LEGACY_OVERLAP == "start <= other_end and end >= other_start"


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_demo_returns_zero(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    assert capsys.readouterr().out == first


def test_demo_shows_the_two_overlap_answers(capsys):
    run_demo()
    assert "overlaps() False, legacy_overlaps() True" in capsys.readouterr().out


def test_demo_shows_the_state_machine_refusal(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "allowed from here: checked_in, cancelled" in out


def test_demo_shows_the_sqlite_length(capsys):
    run_demo()
    assert "stored 40 characters" in capsys.readouterr().out


def test_demo_prints_no_non_ascii(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert all(ord(character) < 128 for character in out)


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


def test_cli_lists_the_seeded_rooms(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "6 rooms, 5 bookings" in out
    assert "SeasonRate 20000 +25% from 2026-06-01" in out


def test_cli_availability_lists_free_rooms(capsys):
    assert cli.main(["--availability", "2026-03-10:2026-03-12"]) == 0
    out = capsys.readouterr().out
    assert "6 of 6 rooms free" in out


def test_cli_availability_reports_taken_rooms(capsys):
    assert cli.main(["--availability", "2026-03-03:2026-03-04"]) == 0
    out = capsys.readouterr().out
    assert "4 of 6 rooms free" in out
    assert "free  103" in out


def test_cli_availability_refuses_a_bad_spec(capsys):
    assert cli.main(["--availability", "2026-03-02"]) == 2
    assert "expected IN:OUT" in capsys.readouterr().err


def test_cli_books_a_room(capsys):
    assert cli.main(["--book", "203:Meera Iyer:9876500000:"
                               "meera@example.com:2026-04-01:2026-04-03"]) == 0
    out = capsys.readouterr().out
    assert "BK-0006" in out and "Meera Iyer" in out
    assert "2 night(s), 27000 cents" in out


def test_cli_book_refuses_a_clash(capsys):
    assert cli.main(["--book", "101:X:9876500000:x@example.com:"
                               "2026-03-04:2026-03-06"]) == 2
    assert "taken" in capsys.readouterr().err


def test_cli_book_refuses_a_bad_phone(capsys):
    assert cli.main(["--book", "203:X:123:x@example.com:"
                               "2026-04-01:2026-04-03"]) == 2
    assert "10 digits" in capsys.readouterr().err


def test_cli_book_refuses_a_malformed_spec(capsys):
    assert cli.main(["--book", "203:Meera"]) == 2
    assert "expected ROOM:NAME" in capsys.readouterr().err


def test_cli_folio_lists_the_nights(capsys):
    assert cli.main(["--folio", "BK-0003"]) == 0
    out = capsys.readouterr().out
    assert "15000" in out and "42000" in out
    assert "Fri" in out and "Sat" in out


def test_cli_occupancy(capsys):
    assert cli.main(["--occupancy", "2026-03-02:2026-03-05"]) == 0
    out = capsys.readouterr().out
    assert "5 of 18 room-nights (2777 bp)" in out
    assert "47500 cents" in out


def test_cli_consistency_passes(capsys):
    assert cli.main(["--consistency"]) == 0
    assert "4/4 checks passed" in capsys.readouterr().out


def test_cli_check_in(capsys):
    assert cli.main(["--check-in", "BK-0002", "--date", "2026-03-03"]) == 0
    out = capsys.readouterr().out
    assert "confirmed -> checked_in" in out and "2026-03-03" in out


def test_cli_check_in_refuses_a_day_outside_the_stay(capsys):
    assert cli.main(["--check-in", "BK-0002", "--date", "2026-04-01"]) == 2
    assert "outside" in capsys.readouterr().err


def test_cli_cancel(capsys):
    assert cli.main(["--cancel", "BK-0002"]) == 0
    assert "confirmed -> cancelled" in capsys.readouterr().out


def test_cli_cancel_of_a_cancelled_booking_exits_two(capsys):
    assert cli.main(["--cancel", "BK-0005"]) == 2
    assert "allowed from here: nothing" in capsys.readouterr().err


def test_cli_check_out(capsys):
    assert cli.main(["--check-out", "BK-0001", "--date", "2026-03-05"]) == 0
    assert "checked_in -> checked_out" in capsys.readouterr().out


def test_cli_legacy_mode(capsys):
    assert cli.main(["--legacy"]) == 0
    out = capsys.readouterr().out
    assert 'room.status = "Occupied"' in out
    assert "start <= other_end" in out


def test_cli_json_occupancy(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--occupancy", "2026-03-02:2026-03-05",
                     "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["mode"] == "occupancy"
    assert payload["sold"] == 5 and payload["revenue"] == 47500


def test_cli_json_rooms(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["mode"] == "rooms" and len(payload["rooms"]) == 6
    assert payload["rooms"][0]["rate"]["kind"] == "flat"


def test_cli_json_consistency(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--consistency", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["clean"] is True and len(payload["checks"]) == 4


def test_cli_write_saves_the_booking(tmp_path, capsys):
    target = tmp_path / "saved.json"
    assert cli.main(["--book", "203:Meera Iyer:9876500000:"
                               "meera@example.com:2026-04-01:2026-04-03",
                     "--write", str(target)]) == 0
    capsys.readouterr()
    assert len(load_hotel(target)) == 6


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "nope.json"]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--occupancy", "2026-03-02:2026-03-05", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
