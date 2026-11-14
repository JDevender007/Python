"""Command line interface for the hotel.

    python src/main.py --demo
    python src/main.py                                  # every room
    python src/main.py --availability 2026-03-10:2026-03-12
    python src/main.py --book 203:Meera Iyer:9876500000:meera@example.com:2026-04-01:2026-04-03
    python src/main.py --check-in BK-0002 --date 2026-03-03
    python src/main.py --folio BK-0001
    python src/main.py --occupancy 2026-03-02:2026-03-05
    python src/main.py --consistency
    python src/main.py --legacy
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

from hotel import (
    DATA_FILE,
    LEGACY_OVERLAP,
    LEGACY_STATUS,
    BookingError,
    Guest,
    HotelError,
    Stay,
    load_hotel,
    run_demo,
    save_hotel,
)

BANNER = """
========================================
 LEDGER HOTEL
   rooms, stays, one state machine
========================================
"""


def _split(spec: str, parts: int, shape: str) -> list[str]:
    pieces = [piece.strip() for piece in spec.split(":")]
    if len(pieces) != parts or not all(pieces):
        raise HotelError(f"expected {shape}, got {spec!r}")
    return pieces


def _stay(spec: str) -> Stay:
    check_in, check_out = _split(spec, 2, "IN:OUT as YYYY-MM-DD:YYYY-MM-DD")
    return Stay.of(check_in, check_out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="A hotel built from half-open stays and a state machine.")
    parser.add_argument("--demo", action="store_true",
                        help="run the bundled self-checking demo")
    parser.add_argument("--file", type=Path, default=DATA_FILE,
                        help="hotel file (default: data/hotel.json)")
    parser.add_argument("--rooms", action="store_true",
                        help="one line per room (the default)")
    parser.add_argument("--availability", metavar="IN:OUT",
                        help="rooms free for those nights")
    parser.add_argument("--book", metavar="ROOM:NAME:PHONE:EMAIL:IN:OUT",
                        help="take a booking")
    parser.add_argument("--cancel", metavar="REF", help="cancel a booking")
    parser.add_argument("--check-in", metavar="REF", dest="check_in",
                        help="check a booking in")
    parser.add_argument("--check-out", metavar="REF", dest="check_out",
                        help="check a booking out")
    parser.add_argument("--folio", metavar="REF",
                        help="night-by-night price of one booking")
    parser.add_argument("--occupancy", metavar="IN:OUT",
                        help="sold nights, capacity and revenue")
    parser.add_argument("--consistency", action="store_true",
                        help="run the four invariants")
    parser.add_argument("--date", metavar="YYYY-MM-DD",
                        help="the date to stamp on today's change")
    parser.add_argument("--legacy", action="store_true",
                        help="show the legacy defects the demo proves")
    parser.add_argument("--write", type=Path, metavar="PATH",
                        help="save the hotel after the change")
    parser.add_argument("--json", type=Path, metavar="PATH",
                        help="write the result as JSON to PATH")
    parser.add_argument("--quiet", action="store_true",
                        help="write no standard output")
    args = parser.parse_args(argv)

    if args.demo:
        if args.quiet:
            with contextlib.redirect_stdout(io.StringIO()):
                run_demo()
        else:
            run_demo()
        return 0

    day = args.date or "2026-03-01"
    try:
        if args.legacy:
            payload = {
                "mode": "legacy",
                "status": LEGACY_STATUS,
                "overlap": LEGACY_OVERLAP,
                "dates": "the legacy booking had no arrival or departure",
                "note": "checkout_guest never removed the guest row",
            }
            if not args.quiet:
                print(BANNER)
                print(f"  status   {LEGACY_STATUS}")
                print("  and any other string was accepted: no rules")
                print(f"  overlap  {LEGACY_OVERLAP}")
                print("  so a guest leaving on the 12th collided with one")
                print("  arriving on the 12th")
                print(f"  {payload['note']}")
            if args.json:
                args.json.write_text(json.dumps(payload, indent=2),
                                     encoding="utf-8")
            return 0

        hotel = load_hotel(args.file)
        payload: dict = {"mode": "rooms", "hotel": hotel.name, "date": day}

        if args.availability:
            stay = _stay(args.availability)
            free = hotel.free_rooms(stay)
            payload = {"mode": "availability", "stay": str(stay),
                       "nights": stay.nights,
                       "free": [room.number for room in free],
                       "taken": len(hotel.rooms) - len(free)}
            if not args.quiet:
                print(BANNER)
                print(f"  {stay} - {stay.nights} night(s)")
                for room in free:
                    print(f"  free  {room.number}  {room.kind}  "
                          f"{room.rate.for_night(stay.check_in)} cents/night")
                print(f"\n  {len(free)} of {len(hotel.rooms)} rooms free")
        elif args.book:
            number, name, phone, email, check_in, check_out = _split(
                args.book, 6, "ROOM:NAME:PHONE:EMAIL:IN:OUT")
            booking = hotel.book(number, Guest(name, phone, email),
                                 Stay.of(check_in, check_out))
            payload = {"mode": "book", "reference": booking.reference,
                       "room": booking.room.number, "stay": str(booking.stay),
                       "nights": booking.stay.nights,
                       "cents": booking.price(),
                       "status": booking.status.value}
            if not args.quiet:
                print(BANNER)
                print(f"  {booking.reference}  {booking.guest.name}  "
                      f"room {booking.room.number}  {booking.stay}")
                print(f"  {booking.stay.nights} night(s), "
                      f"{booking.price()} cents")
        elif args.cancel or args.check_in or args.check_out:
            reference = args.cancel or args.check_in or args.check_out
            booking = hotel.booking(reference)
            before = booking.status
            if args.cancel:
                booking.cancel(day)
            elif args.check_in:
                booking.check_in(day)
            else:
                booking.check_out(day)
            payload = {"mode": "move", "reference": booking.reference,
                       "from": before.value, "to": booking.status.value,
                       "date": day}
            if not args.quiet:
                print(BANNER)
                print(f"  {booking.reference}  {before.value} -> "
                      f"{booking.status.value}  on {day}")
        elif args.folio:
            booking = hotel.booking(args.folio)
            lines = booking.folio()
            payload = {"mode": "folio", "reference": booking.reference,
                       "lines": lines, "cents": booking.price(),
                       "status": booking.status.value}
            if not args.quiet:
                print(BANNER)
                for line in lines:
                    print(line)
        elif args.occupancy:
            stay = _stay(args.occupancy)
            report = hotel.occupancy(stay)
            payload = {"mode": "occupancy", "stay": str(stay), **report}
            if not args.quiet:
                print(BANNER)
                print(f"  {stay} - {report['nights']} night(s)")
                print(f"  sold     {report['sold']} of {report['capacity']} "
                      f"room-nights ({report['basis_points']} bp)")
                print(f"  revenue  {report['revenue']} cents")
        elif args.consistency:
            checks = hotel.consistency()
            payload = {"mode": "consistency",
                       "checks": [{"name": name, "passed": passed}
                                  for name, passed in checks],
                       "clean": all(passed for _, passed in checks)}
            if not args.quiet:
                print(BANNER)
                for name, passed in checks:
                    print(f"  {'PASS' if passed else 'FAIL'}  {name}")
                print(f"\n  {sum(1 for _, ok in checks if ok)}/{len(checks)} "
                      f"checks passed")
        else:
            rooms = hotel.rooms
            payload = {"mode": "rooms",
                       "rooms": [{"number": room.number, "kind": room.kind,
                                  "capacity": room.capacity,
                                  "rate": room.rate.to_dict()}
                                 for room in rooms]}
            if not args.quiet:
                print(BANNER)
                for room in rooms:
                    print(f"  {room.number:<4} {room.kind:<8} "
                          f"{room.capacity}p  {room.rate.describe()}")
                print(f"\n  {len(rooms)} rooms, {len(hotel)} bookings")

        if args.write:
            save_hotel(args.write, hotel)
            payload["written"] = args.write.name
            if not args.quiet:
                print(f"\n  written to {payload['written']}")

        if args.json:
            args.json.write_text(json.dumps(payload, indent=2),
                                 encoding="utf-8")
        return 0
    except (HotelError, BookingError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
