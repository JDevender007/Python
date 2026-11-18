"""A retried POST is a second POST, unless it carries a key that makes it one.

The legacy retry was a loop around a request:

    def post(payload, tries=3):
        for _ in range(tries):
            try:
                return client.post("/orders", payload)
            except Exception:
                continue
        return None

**1. Retrying a POST is creating a second resource.** A connection that times out
*after* the server committed the write leaves the client certain it failed. The loop
tries again, the server creates a second order, and the customer is charged twice.
Nothing in the request says "this is the same order as before".

**2. `return None` after the last try erases the difference between "no answer" and
"an answer of nothing".** The order may well exist. The caller gets `None`, treats it
as "nothing happened", and the only record of the truth is in the server's table.

**3. A `401` is not retryable.** An expired token fails the first attempt, and it will
fail the second and the third for the very same reason. Three attempts cost three
round trips and hide the cause behind a generic failure.

**4. A retry with no wait is not a retry, it is a burst.** The three attempts leave the
socket as fast as the loop can run, which is exactly what a service that is already
struggling does not need.

**5. Safety needs two separate things, and neither is a retry count.** The request needs
an **idempotency key** the server can dedupe on, and the client needs to know which
statuses are worth another attempt (`5xx`, `429`, a timeout) and which are final (`401`,
`400`, `409`).

So this module models the whole exchange: a store that dedupes on a key, a server with a
**script** of what each attempt meets, a token with an expiry, a backoff schedule that is
deterministic by construction, and both loops -- the legacy one and the keyed one -- run
over the identical script so the difference is a number, not an opinion.

The demonstration is offline: one bundled order and five scripted scenarios.
Standard library only: no requests, no HTTP client, no API key.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ORDER_FILE = DATA_DIR / "order.txt"

#: The legacy retry, transcribed: the same POST again, then `None`.
LEGACY_POST = ('for _ in range(tries):\n'
               '    try:\n'
               '        return client.post("/orders", payload)\n'
               '    except Exception:\n'
               '        continue\n'
               'return None')

#: What one attempt can meet. Two of them are 504s that differ in the store.
OUTCOMES = ("ok", "timeout", "commit-then-timeout", "unavailable",
            "unauthorized")

#: How a run ended.
ENDINGS = ("created", "gave-up", "unauthorized")

#: The five scripted scenarios: a name, what each attempt meets, and when the
#: loop starts (`None` means "one moment past this token's own expiry").
SCENARIOS = (
    ("flaky", ("timeout", "timeout", "ok"), 0),
    ("commit-then-timeout", ("commit-then-timeout", "ok"), 0),
    ("commit-then-silence", ("timeout", "commit-then-timeout", "unavailable"),
     0),
    ("unavailable", ("unavailable", "unavailable", "unavailable"), 0),
    ("expired-token", ("ok", "ok", "ok"), None),
)

#: The most attempts the lab will make, the first wait, and the ceiling.
MAX_TRIES = 5
BACKOFF_BASE = 1
BACKOFF_CAP = 8


class RetryError(Exception):
    """A token, a store, a script or a run that cannot be read, and why not."""


# --------------------------------------------------------------------------- #
# Reading values
# --------------------------------------------------------------------------- #
def _whole(value, field: str, minimum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise RetryError(f"{field} is a whole number, got {value!r}")
    if value < minimum:
        raise RetryError(f"{field} is at least {minimum}, got {value}")
    return value


def _key(value) -> str:
    """An idempotency key: one non-empty word, because it travels in a header."""
    if not isinstance(value, str):
        raise RetryError(f"a key is text, got {type(value).__name__}")
    body = value.strip()
    if not body:
        raise RetryError(f"a key needs a value, got {value!r}")
    if any(character.isspace() for character in body):
        raise RetryError(f"a key is one word, got {value!r}")
    return body


# --------------------------------------------------------------------------- #
# A token
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Token:
    """A token that was issued at a second and is good for a number of seconds.

    Half-open, like every sane expiry: issued <= now < issued + lifetime.
    """

    issued: int
    lifetime: int

    def __post_init__(self) -> None:
        _whole(self.issued, "an issue time", 0)
        _whole(self.lifetime, "a lifetime", 1)

    def expires_at(self) -> int:
        return self.issued + self.lifetime

    def valid_at(self, now: int) -> bool:
        now = _whole(now, "a moment", 0)
        return self.issued <= now < self.expires_at()

    def remaining_at(self, now: int) -> int:
        now = _whole(now, "a moment", 0)
        return max(0, self.expires_at() - now)

    def line(self) -> str:
        return (f"token good from {self.issued} to {self.expires_at() - 1} "
                f"({self.lifetime} second(s))")


# --------------------------------------------------------------------------- #
# An order
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Order:
    """What the client is asking the server to create, in whole cents."""

    quantity: int
    unit_cents: int

    def __post_init__(self) -> None:
        _whole(self.quantity, "a quantity", 1)
        _whole(self.unit_cents, "a unit price", 0)

    def total_cents(self) -> int:
        return self.quantity * self.unit_cents

    def line(self) -> str:
        return (f"{self.quantity} x {self.unit_cents} cents = "
                f"{self.total_cents()} cents")


# --------------------------------------------------------------------------- #
# A reply
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Reply:
    """One attempt's answer: a status, an id if the client learned one, and why."""

    status: int
    order_id: int | None
    detail: str

    def __post_init__(self) -> None:
        _whole(self.status, "a status", 100)
        if self.status > 599:
            raise RetryError(f"a status is at most 599, got {self.status}")
        if self.order_id is not None:
            _whole(self.order_id, "an order id", 1)
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise RetryError("a reply needs the sentence that says why")

    def created(self) -> bool:
        return self.status == 201

    def retryable(self) -> bool:
        """Is another attempt worth making? `401` and `400` are final."""
        if self.status == 201:
            return False
        if self.status in (401, 403, 400, 404, 409, 422):
            return False
        return True

    def line(self) -> str:
        ident = "-" if self.order_id is None else str(self.order_id)
        return f"HTTP {self.status} id={ident} {self.detail}"


# --------------------------------------------------------------------------- #
# A store that can dedupe
# --------------------------------------------------------------------------- #
class Store:
    """The server's table, with an index from idempotency key to the row it made."""

    def __init__(self) -> None:
        self._rows: list[Order] = []
        self._by_key: dict[str, int] = {}

    def __len__(self) -> int:
        return len(self._rows)

    def rows(self) -> tuple[Order, ...]:
        return tuple(self._rows)

    def keys(self) -> tuple[str, ...]:
        return tuple(self._by_key)

    def create(self, order: Order, key: str | None = None) -> tuple[int, bool]:
        """Create an order, or hand back the one this key already made.

        Returns `(id, created)`. `created` is `False` when the key was seen before,
        which is the whole point: the second attempt is answered, not repeated.
        """
        if not isinstance(order, Order):
            raise RetryError(f"a store holds orders, got {type(order).__name__}")
        if key is not None:
            key = _key(key)
            if key in self._by_key:
                return self._by_key[key], False
        self._rows.append(order)
        ident = len(self._rows)
        if key is not None:
            self._by_key[key] = ident
        return ident, True

    def order(self, ident: int) -> Order:
        ident = _whole(ident, "an order id", 1)
        if ident > len(self._rows):
            raise RetryError(f"there is no order {ident}")
        return self._rows[ident - 1]


# --------------------------------------------------------------------------- #
# A server with a script
# --------------------------------------------------------------------------- #
class Server:
    """One server, one store, and a script of what each attempt meets.

    The token is checked **before** the script: a request that arrives with an
    expired token never reaches the handler, so no script entry can rescue it.
    """

    def __init__(self, store: Store, token: Token, script) -> None:
        if not isinstance(store, Store):
            raise RetryError(f"a server needs a store, got "
                             f"{type(store).__name__}")
        if not isinstance(token, Token):
            raise RetryError(f"a server needs a token, got "
                             f"{type(token).__name__}")
        held = tuple(script)
        if not held:
            raise RetryError("a script needs at least one attempt")
        for number, step in enumerate(held, start=1):
            if step not in OUTCOMES:
                raise RetryError(f"attempt {number} is one of "
                                 f"{', '.join(OUTCOMES)}, got {step!r}")
        self.store = store
        self.token = token
        self.script = held
        self.position = 0
        self.requests = 0
        self.seen: list[str] = []

    def post(self, order: Order, key: str | None = None,
             now: int = 0) -> Reply:
        """One attempt, answering exactly as the script says it would."""
        self.requests += 1
        if key is not None:
            key = _key(key)
        if not self.token.valid_at(now):
            self.seen.append("expired")
            return Reply(401, None,
                         f"the token expired at {self.token.expires_at()}, "
                         f"and this attempt arrived at {now}")
        step = self.script[self.position] if self.position < len(self.script) \
            else "ok"
        self.position += 1
        self.seen.append(step)

        if step == "ok":
            ident, _ = self.store.create(order, key)
            return Reply(201, ident, "the order was created")
        if step == "commit-then-timeout":
            ident, created = self.store.create(order, key)
            detail = ("the write was committed and the answer was lost"
                      if created else
                      "the write was already committed under this key")
            return Reply(504, None, detail)
        if step == "timeout":
            return Reply(504, None, "no answer: the connection timed out")
        if step == "unavailable":
            return Reply(503, None, "the service is unavailable")
        return Reply(401, None, "the token was rejected")


# --------------------------------------------------------------------------- #
# A run
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Run:
    """What one loop did: its replies, how long it waited, and what it created."""

    mode: str
    outcome: str
    order_id: int | None
    replies: tuple[Reply, ...]
    waited: int
    rows: int

    def __post_init__(self) -> None:
        if self.mode not in ("legacy", "keyed"):
            raise RetryError(f"a run is legacy or keyed, got {self.mode!r}")
        if self.outcome not in ENDINGS:
            raise RetryError(f"a run ends {', '.join(ENDINGS)}, got "
                             f"{self.outcome!r}")
        if not self.replies:
            raise RetryError("a run needs at least one attempt")
        _whole(self.waited, "a wait", 0)
        _whole(self.rows, "a row count", 0)
        if self.outcome == "created" and self.order_id is None:
            raise RetryError("a run that created something has an order id")

    def __len__(self) -> int:
        return len(self.replies)

    def attempts(self) -> int:
        return len(self.replies)

    def statuses(self) -> tuple[int, ...]:
        return tuple(reply.status for reply in self.replies)

    def last(self) -> Reply:
        return self.replies[-1]

    def line(self) -> str:
        ident = "-" if self.order_id is None else str(self.order_id)
        statuses = " ".join(str(status) for status in self.statuses())
        return (f"{self.mode:<7} {self.attempts():>2} attempt(s) "
                f"{self.outcome:<13} id={ident:<4} rows={self.rows} "
                f"waited={self.waited:<2} {statuses}")


def backoff_delays(tries: int, base: int = BACKOFF_BASE,
                   cap: int = BACKOFF_CAP) -> tuple[int, ...]:
    """The waits between attempts: base, base*2, base*4, up to the cap.

    Deterministic on purpose. A real client adds jitter, and a demonstration that
    prints a random number cannot be checked against anything.
    """
    tries = _whole(tries, "a try count", 1)
    if tries > MAX_TRIES:
        raise RetryError(f"at most {MAX_TRIES} tries, got {tries}")
    base = _whole(base, "a base wait", 1)
    cap = _whole(cap, "a cap", 1)
    if cap < base:
        raise RetryError(f"a cap of {cap} is below the base wait of {base}")
    waits: list[int] = []
    for number in range(tries - 1):
        step = base * (2 ** number)
        waits.append(min(step, cap))
    return tuple(waits)


# --------------------------------------------------------------------------- #
# The two loops
# --------------------------------------------------------------------------- #
def legacy_post(server: Server, order: Order, tries: int = 3,
                now: int = 0) -> Run:
    """The legacy loop: the same POST again, no key, no wait, `None` at the end.

    It has no idea which statuses are worth another attempt, so an expired token
    is retried exactly like a timeout: as many times as the loop is allowed.
    """
    tries = _whole(tries, "a try count", 1)
    before = len(server.store)
    replies: list[Reply] = []
    ident: int | None = None
    for _ in range(tries):
        reply = server.post(order, None, now)
        replies.append(reply)
        if reply.created():
            ident = reply.order_id
            break
    if ident is not None:
        outcome = "created"
    elif replies[-1].status == 401:
        outcome = "unauthorized"
    else:
        outcome = "gave-up"
    return Run("legacy", outcome, ident, tuple(replies), 0,
               len(server.store) - before)


def post_with_key(server: Server, order: Order, key: str, tries: int = 3,
                  now: int = 0) -> Run:
    """The keyed loop: one key, a growing wait, and a `401` that stops it dead."""
    tries = _whole(tries, "a try count", 1)
    key = _key(key)
    waits = backoff_delays(tries)
    before = len(server.store)
    replies: list[Reply] = []
    outcome = "gave-up"
    ident: int | None = None
    clock = now
    waited = 0
    for number in range(tries):
        reply = server.post(order, key, clock)
        replies.append(reply)
        if reply.created():
            outcome, ident = "created", reply.order_id
            break
        if not reply.retryable():
            outcome = "unauthorized" if reply.status == 401 else "gave-up"
            break
        if number < tries - 1:
            clock += waits[number]
            waited += waits[number]
    return Run("keyed", outcome, ident, tuple(replies), waited,
               len(server.store) - before)


# --------------------------------------------------------------------------- #
# Reading the bundle
# --------------------------------------------------------------------------- #
def parse_order(text: str) -> tuple[Order, Token, int]:
    """Read the order, the token and the moment the loop starts."""
    values: dict[str, int] = {}
    for number, line in enumerate(text.replace("\r\n", "\n").split("\n"),
                                  start=1):
        if not line.strip() or line.lstrip().startswith(";"):
            continue
        fields = line.split()
        if len(fields) != 2:
            raise RetryError(f"line {number}: a setting is a name and a value")
        name, raw = fields
        if name not in ("quantity", "unit-cents", "issued", "lifetime", "now"):
            raise RetryError(f"line {number}: {name!r} is not a setting this "
                             f"bundle carries")
        if name in values:
            raise RetryError(f"line {number}: {name!r} is set twice")
        if not raw.lstrip("-").isdigit():
            raise RetryError(f"line {number}: {name!r} takes a whole number, "
                             f"got {raw!r}")
        values[name] = int(raw)
    for name in ("quantity", "unit-cents", "issued", "lifetime", "now"):
        if name not in values:
            raise RetryError(f"the bundle does not set {name!r}")
    order = Order(values["quantity"], values["unit-cents"])
    token = Token(values["issued"], values["lifetime"])
    return order, token, values["now"]


def read_order(path=None) -> tuple[Order, Token, int]:
    target = Path(ORDER_FILE if path is None else path)
    if not target.is_file():
        raise RetryError(f"file not found: {target}")
    return parse_order(target.read_text(encoding="utf-8"))


def script_for(name: str) -> tuple[str, ...]:
    """The script a scenario runs, refusing a name the lab does not hold."""
    for held, script, _ in SCENARIOS:
        if held == name:
            return script
    raise RetryError(f"no scenario named {name!r}")


def offset_for(name: str) -> int | None:
    """How long after `now` a scenario starts, or `None` for "past its token"."""
    for held, _, offset in SCENARIOS:
        if held == name:
            return offset
    raise RetryError(f"no scenario named {name!r}")


def start_for(token: Token, now: int, offset: int | None) -> int:
    """The second a scenario's first attempt arrives at."""
    if offset is None:
        return token.expires_at()
    return now + _whole(offset, "an offset", 0)


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:                                     # noqa: BLE001
        return False


def audit(runs: dict[str, tuple[Run, Run]], order: Order,
          waits: tuple[int, ...], make_store) -> list[tuple[str, bool]]:
    """Eleven checks, each re-derived from the runs, the order and the waits.

    `waits` is the schedule the keyed loop actually used, so a check about the
    waits can be falsified by handing in a schedule that is not the one it claims.
    `make_store` is a factory, so the two store checks each get a store of their
    own instead of sharing the rows the check before them left behind.
    """
    def pair(name: str) -> tuple[Run, Run]:
        if name not in runs:
            raise RetryError(f"no run pair named {name!r}")
        return runs[name]

    def the_legacy_loop_creates_two_rows_for_one_committed_order() -> bool:
        legacy, _ = pair("commit-then-timeout")
        return legacy.mode == "legacy" and legacy.rows == 2 and \
            legacy.outcome == "created"

    def the_keyed_loop_creates_one_row_for_the_same_script() -> bool:
        _, keyed = pair("commit-then-timeout")
        return keyed.rows == 1 and keyed.outcome == "created"

    def a_lost_answer_still_leaves_the_order_in_the_store() -> bool:
        legacy, keyed = pair("commit-then-silence")
        return legacy.outcome == "gave-up" and legacy.order_id is None and \
            legacy.rows == 1 and keyed.outcome == "gave-up" and \
            keyed.order_id is None and keyed.rows == 1

    def a_timeout_is_worth_retrying_and_the_third_attempt_lands() -> bool:
        legacy, keyed = pair("flaky")
        return legacy.statuses() == (504, 504, 201) and \
            keyed.statuses() == (504, 504, 201) and \
            legacy.outcome == "created" and keyed.outcome == "created"

    def an_expired_token_fails_every_attempt() -> bool:
        legacy, keyed = pair("expired-token")
        return legacy.statuses() == (401, 401, 401) and \
            keyed.statuses() == (401,) and \
            legacy.outcome == "unauthorized" and \
            keyed.outcome == "unauthorized"

    def the_keyed_loop_stops_at_the_first_fatal_status() -> bool:
        legacy, keyed = pair("expired-token")
        return legacy.attempts() == 3 and keyed.attempts() == 1

    def the_waits_grow_are_capped_and_never_vary() -> bool:
        held = tuple(waits)
        if not held:
            return False
        if held != tuple(sorted(held)):
            return False
        if max(held) != BACKOFF_CAP:
            return False
        return held == backoff_delays(len(held) + 1)

    def the_legacy_loop_waits_nothing_and_the_keyed_loop_does() -> bool:
        legacy, keyed = pair("unavailable")
        return legacy.waited == 0 and keyed.waited == sum(waits[:2]) and \
            keyed.attempts() == 3

    def a_repeated_key_returns_the_row_the_first_attempt_made() -> bool:
        probe = make_store()
        first, made_one = probe.create(order, "demo-key")
        again, made_two = probe.create(order, "demo-key")
        return made_one is True and made_two is False and first == again and \
            len(probe) == 1

    def a_different_key_creates_a_different_order() -> bool:
        probe = make_store()
        first, _ = probe.create(order, "key-one")
        second, _ = probe.create(order, "key-two")
        return first != second and len(probe) == 2

    def every_run_counts_the_attempts_it_made() -> bool:
        if not runs:
            return False
        for name in runs:
            for run in runs[name]:
                if len(run.replies) < 1 or run.rows > len(run.replies):
                    return False
        return True

    checks = [
        ("the legacy loop creates two rows for one committed order",
         the_legacy_loop_creates_two_rows_for_one_committed_order),
        ("the keyed loop creates one row for the same script",
         the_keyed_loop_creates_one_row_for_the_same_script),
        ("a lost answer still leaves the order in the store",
         a_lost_answer_still_leaves_the_order_in_the_store),
        ("a timeout is worth retrying and the third attempt lands",
         a_timeout_is_worth_retrying_and_the_third_attempt_lands),
        ("an expired token fails every attempt",
         an_expired_token_fails_every_attempt),
        ("the keyed loop stops at the first fatal status",
         the_keyed_loop_stops_at_the_first_fatal_status),
        ("the waits grow, are capped and never vary",
         the_waits_grow_are_capped_and_never_vary),
        ("the legacy loop waits nothing and the keyed loop does",
         the_legacy_loop_waits_nothing_and_the_keyed_loop_does),
        ("a repeated key returns the row the first attempt made",
         a_repeated_key_returns_the_row_the_first_attempt_made),
        ("a different key creates a different order",
         a_different_key_creates_a_different_order),
        ("every run counts the attempts it made",
         every_run_counts_the_attempts_it_made),
    ]
    return [(name, _guard(function)) for name, function in checks]


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
TRIES = 3


def run_pair(order: Order, token: Token, now: int, script,
             start: int) -> tuple[Run, Run]:
    """Both loops over the identical script, each against its own fresh server."""
    legacy_server = Server(Store(), token, script)
    legacy = legacy_post(legacy_server, order, TRIES, start)
    keyed_server = Server(Store(), token, script)
    keyed = post_with_key(keyed_server, order, "order-7f3a", TRIES, start)
    return legacy, keyed


def run_demo() -> int:
    order, token, now = read_order()

    print("=" * 78)
    print(" RETRY LAB - a retried POST is a second POST")
    print("=" * 78)

    print("\n  the legacy retry, transcribed:")
    for line in LEGACY_POST.split("\n"):
        print(f"    {line}")

    print(f"\n  the order: {order.line()}")
    print(f"  {token.line()}")
    print(f"  the loops start at second {now} and try at most {TRIES} times")

    runs: dict[str, tuple[Run, Run]] = {}
    starts: dict[str, int] = {}
    for name, script, offset in SCENARIOS:
        start = start_for(token, now, offset)
        legacy, keyed = run_pair(order, token, now, script, start)
        runs[name] = (legacy, keyed)
        starts[name] = start

    print("\n  five scripts, run by both loops (504 = no answer, 201 = "
          "created):")
    print(f"    {'scenario':<20} {'at':>3} {'mode':<7} {'attempts':>8} "
          f"{'outcome':<15} {'id':<5} {'rows':>4} {'waited':>6}  statuses")
    for name, _, _ in SCENARIOS:
        for run in runs[name]:
            ident = "-" if run.order_id is None else str(run.order_id)
            statuses = " ".join(str(status) for status in run.statuses())
            print(f"    {name:<20} {starts[name]:>3} {run.mode:<7} "
                  f"{run.attempts():>8} {run.outcome:<15} {ident:<5} "
                  f"{run.rows:>4} {run.waited:>6}  {statuses}")

    print("\n  the same exchange, told twice:")
    for name in ("commit-then-timeout", "expired-token", "unavailable"):
        legacy, keyed = runs[name]
        print(f"    {name} (at second {starts[name]}):")
        print(f"      legacy {legacy.line()}")
        print(f"      keyed  {keyed.line()}")

    total_legacy = sum(runs[name][0].rows for name, _, _ in SCENARIOS)
    total_keyed = sum(runs[name][1].rows for name, _, _ in SCENARIOS)
    intended = sum(1 for name, _, _ in SCENARIOS if runs[name][1].rows)

    print("\n  what each loop left in the store:")
    print(f"    {intended} order(s) were meant to exist: the keyed loop left "
          f"{total_keyed} row(s)")
    print(f"    the legacy loop left {total_legacy} row(s)")
    print(f"    the extra row is the order that was committed and then "
          f"created a second time")

    print("\n  a repeated key, at the store:")
    fresh = Store()
    first, made = fresh.create(order, "order-7f3a")
    second, made_again = fresh.create(order, "order-7f3a")
    print(f"    key order-7f3a -> id {first} (created={made})")
    print(f"    key order-7f3a -> id {second} (created={made_again}), "
          f"and the store holds {len(fresh)}")
    print(f"    one key, one order -- the second attempt is answered, not "
          f"repeated")

    print("\n  the waits the keyed loop uses, and the legacy loop does not:")
    print(f"    3 tries -> {backoff_delays(3)}   5 tries -> "
          f"{backoff_delays(5)}   (base {BACKOFF_BASE}, cap {BACKOFF_CAP})")

    checks = audit(runs, order, backoff_delays(MAX_TRIES), Store)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    flaky_legacy, _ = runs["flaky"]
    committed_legacy, committed_keyed = runs["commit-then-timeout"]
    expired_legacy, expired_keyed = runs["expired-token"]

    print("\nCross-checks OK: " +
          f"{len(SCENARIOS)} scenarios and {intended} intended order(s), the "
          f"legacy loop left {total_legacy} row(s) where the keyed loop left "
          f"{total_keyed}, the committed-then-lost order became "
          f"{committed_legacy.rows} rows without a key and "
          f"{committed_keyed.rows} with one, the expired token cost "
          f"{expired_legacy.attempts()} attempt(s) for the legacy loop and "
          f"{expired_keyed.attempts()} for the keyed one, the flaky script "
          f"reached {flaky_legacy.statuses()} either way, the waits are "
          f"{backoff_delays(3)} and never vary, and "
          f"{sum(1 for _, okay in checks if okay)}/{len(checks)} checks hold")

    print("Demo completed successfully.")
    return 0
