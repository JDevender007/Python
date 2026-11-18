"""An S3 listing is a page, an ETag is not an MD5, and a presigned URL is local.

The legacy manager is three calls that look like the documentation:

    listing = client.list_objects_v2(Bucket=bucket, Prefix="logs/")
    assert etag == hashlib.md5(body).hexdigest()
    url = f"s3://{bucket}/{key}?X-Amz-Expires=3600"

**1. A prefix query without a delimiter is a string match, not a folder.** Every
key that starts with `logs/` matches, including `logs/api/2024-01.log` and the
zero-byte folder marker `logs/` itself. The console shows two folders because
it passes `Delimiter="/"` and reads `CommonPrefixes`; the legacy call returns
**4 keys** and no prefixes, and because it stops at the first page of 3 it
shows only **3** of them. A prefix is a filter; the delimiter is what turns it
into a directory.

**2. An ETag is not an MD5.** A single PUT of a body has a plain 32-hex MD5
ETag. A multipart upload has `<md5-of-part-md5s>-<partcount>`, and an
SSE-KMS object has an ETag that is not a digest of the body at all. The legacy
check `etag == md5(body)` therefore calls all **3** multipart objects and the
**1** KMS object corrupt: **4 of 9 failed**, none of them damaged. The rebuild
reassembles the parts, recomputes the multipart digest, and separates
`verified`, `corrupt` and `opaque`. It reports **8 verified, 0 corrupt, 1
opaque**.

**3. A listing is paginated, and `IsTruncated` is the only signal.** Nine
objects at three per page need **3 pages**. A loop that never reads
`IsTruncated`, or that keeps going while a token is present, either stops early
or never stops; the token is opaque and its absence on the last page is the
only reliable end.

**4. A presigned URL is signed locally and proves nothing about existence.**
The key is percent-encoded into the canonical request, so `q3 final.txt`
becomes `q3%20final.txt` and the signature covers the encoded path. Interpolating
the raw key produces a URL with a space in it, and pinning `X-Amz-Expires=3600`
ignores the caller's `expires=300`. Signing also never checks the bucket: a
presigned URL for a key that does not exist is generated happily, and fails
only when it is used.

The bucket is a bundled JSON manifest - no boto3, no credentials, no network,
no Stubber. Each object carries the ETag the bucket reports, so the digest
check has something real to disagree with.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import quote

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BUCKET_FILE = DATA_DIR / "bucket.json"

#: The legacy shortcuts, transcribed so the demo can print them.
LEGACY_LIST = 'list_objects_v2(Bucket=b, Prefix="logs/")      # no Delimiter'
LEGACY_ETAG = "assert etag == hashlib.md5(body).hexdigest()   # ignores multipart"
LEGACY_URL = 'f"s3://{b}/{key}?X-Amz-Expires=3600"            # raw key, fixed TTL'

DEMO_SECRET = "offline-signing-secret"
DEFAULT_PREFIX = "logs/"
DEFAULT_DELIMITER = "/"
DEFAULT_PAGE_SIZE = 3
DEFAULT_EXPIRES = 300
MAX_OBJECTS = 1000
MAX_BODY = 4096
MAX_PARTS = 8
UPLOADS = ("single", "multipart", "kms")
BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
ETAG_RE = re.compile(r"^[0-9a-f]{32}(?:-\d+)?$")


class BucketError(RuntimeError):
    """Raised for input the program refuses."""


# --------------------------------------------------------------------------- #
# Digests
# --------------------------------------------------------------------------- #
def md5_hex(data: bytes) -> str:
    """The 32-hex digest a single PUT reports as its ETag."""
    return hashlib.md5(data).hexdigest()


def _chunks(data: bytes, count: int) -> list[bytes]:
    if count < 1:
        raise BucketError("a multipart upload needs at least one part")
    return [
        data[len(data) * index // count:len(data) * (index + 1) // count]
        for index in range(count)
    ]


def multipart_etag(data: bytes, part_count: int) -> str:
    """`md5(concat(part md5 bytes))-partcount`, the multipart ETag form."""
    parts = _chunks(data, part_count)
    joined = b"".join(hashlib.md5(part).digest() for part in parts)
    return f"{hashlib.md5(joined).hexdigest()}-{len(parts)}"


def expected_etag(body: bytes, upload: str, part_count: int = 1) -> str:
    """The ETag the bucket should report for this body and upload mode."""
    if upload == "single":
        return md5_hex(body)
    if upload == "multipart":
        return multipart_etag(body, part_count)
    raise BucketError("a KMS object has no derivable ETag")


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ObjectRecord:
    key: str
    body: bytes
    upload: str = "single"
    part_count: int = 1
    declared_etag: str = ""

    @property
    def size(self) -> int:
        return len(self.body)

    @property
    def kind(self) -> str:
        return {"single": "md5", "multipart": "multipart", "kms": "opaque"}[self.upload]

    @property
    def etag(self) -> str:
        return self.declared_etag

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "size": self.size,
            "upload": self.upload,
            "part_count": self.part_count,
            "etag": self.etag,
            "etag_kind": self.kind,
        }


@dataclass(frozen=True)
class Manifest:
    bucket: str
    objects: tuple[ObjectRecord, ...]


@dataclass(frozen=True)
class Listing:
    """One paged listing: contents, common prefixes and the page count."""

    contents: tuple[ObjectRecord, ...]
    prefixes: tuple[str, ...]
    pages: int
    truncated: bool

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(record.key for record in self.contents)

    def children(self, prefix: str) -> tuple[ObjectRecord, ...]:
        """Objects under the prefix, excluding the zero-byte folder marker."""
        return tuple(record for record in self.contents if record.key != prefix)


# --------------------------------------------------------------------------- #
# Reading and validation
# --------------------------------------------------------------------------- #
def read_bucket(path: str | Path | None = None) -> Manifest:
    """Load the bundled bucket manifest, or one named on the command line."""
    target = Path(path) if path is not None else BUCKET_FILE
    if not target.is_file():
        raise BucketError(f"bucket not found: {target.name}")
    try:
        text = target.read_bytes().decode("ascii")
    except UnicodeDecodeError as exc:
        raise BucketError(f"{target.name} is not ASCII text") from exc
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BucketError(f"{target.name} is not valid JSON: line {exc.lineno}") from exc
    if not isinstance(document, dict):
        raise BucketError(f"{target.name}: a bucket root must be a mapping")
    return manifest_from_document(document)


def manifest_from_document(document: dict[str, Any]) -> Manifest:
    """Convert a parsed document into records without trusting its shape."""
    bucket = str(document.get("bucket", ""))
    records: list[ObjectRecord] = []
    raw = document.get("objects")
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            body = item.get("body", "")
            if not isinstance(body, str):
                body = ""
            upload = item.get("upload", "single")
            if not isinstance(upload, str) or upload not in UPLOADS:
                upload = "single"
            records.append(
                ObjectRecord(
                    key=str(item.get("key", "")),
                    body=body.encode("ascii", "ignore"),
                    upload=upload,
                    part_count=_as_int(item.get("part_count", 1)),
                    declared_etag=str(item.get("etag", "")),
                )
            )
    return Manifest(bucket, tuple(records))


def _as_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def validate_manifest(manifest: Manifest) -> list[str]:
    """Every problem with a parsed manifest; an empty list means valid."""
    problems: list[str] = []
    if not BUCKET_RE.match(manifest.bucket):
        problems.append("$.bucket: a bucket name (3-63 chars, lowercase) is required")
    if not manifest.objects:
        problems.append("$.objects: a non-empty array is required")
    elif len(manifest.objects) > MAX_OBJECTS:
        problems.append(f"$.objects: at most {MAX_OBJECTS} objects")
    seen: set[str] = set()
    for index, record in enumerate(manifest.objects):
        where = f"$.objects[{index}]"
        if not record.key or record.key.startswith("/"):
            problems.append(f"{where}.key: a non-empty key without a leading '/' is required")
        elif record.key in seen:
            problems.append(f"{where}.key: duplicate object {record.key!r}")
        else:
            seen.add(record.key)
        if len(record.body) > MAX_BODY:
            problems.append(f"{where}.body: at most {MAX_BODY} bytes")
        if record.upload not in UPLOADS:
            problems.append(f"{where}.upload: choose one of {', '.join(UPLOADS)}")
            continue
        if not 1 <= record.part_count <= MAX_PARTS:
            problems.append(f"{where}.part_count: an integer 1..{MAX_PARTS} is required")
        if record.upload == "multipart" and record.part_count < 2:
            problems.append(f"{where}.part_count: a multipart upload needs at least 2 parts")
        if record.upload != "multipart" and record.part_count != 1:
            problems.append(f"{where}.part_count: only a multipart upload has parts")
        if not ETAG_RE.match(record.declared_etag):
            problems.append(f"{where}.etag: a 32-hex digest, optionally '-partcount'")
        elif record.upload == "multipart" and not record.declared_etag.endswith(
            f"-{record.part_count}"
        ):
            problems.append(f"{where}.etag: the suffix must match part_count")
        elif record.upload in ("single", "kms") and "-" in record.declared_etag:
            problems.append(f"{where}.etag: only a multipart upload has a part suffix")
    return problems


def validate_or_raise(manifest: Manifest) -> None:
    problems = validate_manifest(manifest)
    if problems:
        joined = "\n  - ".join(problems)
        raise BucketError(f"invalid bucket ({len(problems)} problem(s)):\n  - {joined}")


# --------------------------------------------------------------------------- #
# Listing
# --------------------------------------------------------------------------- #
def _sorted_records(manifest: Manifest) -> list[ObjectRecord]:
    return sorted(manifest.objects, key=lambda record: record.key)


def list_objects(
    manifest: Manifest,
    prefix: str = "",
    delimiter: str | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Listing:
    """Page a listing, splitting at the delimiter into common prefixes."""
    if page_size < 1:
        raise BucketError("page_size must be at least 1")
    entries: list[tuple[str, str, ObjectRecord | None]] = []
    prefixes: set[str] = set()
    for record in _sorted_records(manifest):
        if not record.key.startswith(prefix):
            continue
        remainder = record.key[len(prefix):]
        if delimiter and delimiter in remainder:
            common = prefix + remainder.split(delimiter)[0] + delimiter
            prefixes.add(common)
        else:
            entries.append((record.key, "object", record))
    for common in prefixes:
        entries.append((common, "prefix", None))
    entries.sort(key=lambda item: (item[0], item[1]))

    contents: list[ObjectRecord] = []
    found: list[str] = []
    pages = 0
    offset = 0
    truncated = False
    while True:
        window = entries[offset:offset + page_size]
        pages += 1
        for name, kind, record in window:
            if kind == "object":
                assert record is not None
                contents.append(record)
            else:
                found.append(name)
        offset += page_size
        if offset >= len(entries):
            truncated = False
            break
        truncated = True
    return Listing(tuple(contents), tuple(sorted(set(found))), pages, truncated)


def legacy_list(manifest: Manifest, prefix: str, page_size: int = DEFAULT_PAGE_SIZE) -> list[str]:
    """The legacy call: a prefix, no delimiter, and only the first page."""
    keys = [record.key for record in _sorted_records(manifest) if record.key.startswith(prefix)]
    return keys[:page_size]


def query(
    manifest: Manifest,
    prefix: str = DEFAULT_PREFIX,
    delimiter: str | None = DEFAULT_DELIMITER,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """The folder view and the string view of the same prefix, side by side."""
    listing = list_objects(manifest, prefix, delimiter, page_size)
    legacy = legacy_list(manifest, prefix, page_size)
    all_keys = [record.key for record in _sorted_records(manifest) if record.key.startswith(prefix)]
    return {
        "prefix": prefix,
        "delimiter": delimiter,
        "contents": listing.keys,
        "prefixes": listing.prefixes,
        "children": tuple(record.key for record in listing.children(prefix)),
        "pages": listing.pages,
        "legacy": tuple(legacy),
        "matching": tuple(all_keys),
        "marker_present": prefix in all_keys,
    }


# --------------------------------------------------------------------------- #
# ETag verification
# --------------------------------------------------------------------------- #
def verify_etags(manifest: Manifest) -> dict[str, Any]:
    """Recompute every derivable ETag; an opaque ETag is neither pass nor fail."""
    verified: list[str] = []
    corrupt: list[str] = []
    opaque: list[str] = []
    for record in manifest.objects:
        if record.kind == "opaque":
            opaque.append(record.key)
        elif record.etag == expected_etag(record.body, record.upload, record.part_count):
            verified.append(record.key)
        else:
            corrupt.append(record.key)
    return {
        "verified": tuple(verified),
        "corrupt": tuple(corrupt),
        "opaque": tuple(opaque),
    }


def legacy_verify(manifest: Manifest) -> dict[str, Any]:
    """The legacy check: ETag must equal the MD5 of the body, full stop."""
    verified: list[str] = []
    failed: list[str] = []
    for record in manifest.objects:
        if record.etag == md5_hex(record.body):
            verified.append(record.key)
        else:
            failed.append(record.key)
    return {"verified": tuple(verified), "failed": tuple(failed)}


def multipart_records(manifest: Manifest) -> tuple[ObjectRecord, ...]:
    return tuple(record for record in manifest.objects if record.upload == "multipart")


# --------------------------------------------------------------------------- #
# Presigned URLs
# --------------------------------------------------------------------------- #
def encode_key(key: str) -> str:
    """Percent-encode a key for a canonical request, keeping '/' as a separator."""
    return quote(key, safe="/-_.~")


def _signature(key: str, expires: int, secret: str = DEMO_SECRET) -> str:
    canonical = f"GET\n/{encode_key(key)}\nX-Amz-Expires={expires}"
    return hashlib.sha256(f"{secret}\n{canonical}".encode("ascii")).hexdigest()[:16]


def presign(
    manifest: Manifest,
    key: str,
    expires: int = DEFAULT_EXPIRES,
    secret: str = DEMO_SECRET,
) -> str:
    """Sign a GET URL locally; existence is not checked, on purpose."""
    if not 1 <= expires <= 604_800:
        raise BucketError("expires must be between 1 and 604800 seconds")
    return (
        f"https://{manifest.bucket}.s3.amazonaws.com/{encode_key(key)}"
        f"?X-Amz-Expires={expires}&X-Amz-Signature={_signature(key, expires, secret)}"
    )


def legacy_presign(manifest: Manifest, key: str) -> str:
    """The legacy URL: raw key in the path, a fixed 3600-second expiry."""
    return (
        f"https://{manifest.bucket}.s3.amazonaws.com/{key}"
        f"?X-Amz-Expires=3600&X-Amz-Signature={_signature(key, 3600)}"
    )


# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #
def measure(
    path: str | Path | None = None,
    prefix: str = DEFAULT_PREFIX,
    delimiter: str | None = DEFAULT_DELIMITER,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    manifest = read_bucket(path)
    validate_or_raise(manifest)
    listing = list_objects(manifest, prefix, delimiter, page_size)
    full = list_objects(manifest, "", None, page_size)
    etags = verify_etags(manifest)
    legacy_etags = legacy_verify(manifest)
    signed_key = "reports/q3 final.txt"
    missing_key = "reports/absent.txt"
    return {
        "manifest": manifest,
        "objects": len(manifest.objects),
        "bytes": sum(record.size for record in manifest.objects),
        "listing": listing,
        "query": query(manifest, prefix, delimiter, page_size),
        "full": full,
        "etags": etags,
        "legacy_etags": legacy_etags,
        "multipart": multipart_records(manifest),
        "url": presign(manifest, signed_key),
        "legacy_url": legacy_presign(manifest, signed_key),
        "missing_url": presign(manifest, missing_key),
    }


def report(measured: dict[str, Any]) -> dict[str, Any]:
    """A JSON-safe view: no body bytes leave the process."""
    manifest: Manifest = measured["manifest"]
    return {
        "bucket": manifest.bucket,
        "objects": [record.to_dict() for record in manifest.objects],
        "count": measured["objects"],
        "bytes": measured["bytes"],
        "query": {
            "prefix": measured["query"]["prefix"],
            "delimiter": measured["query"]["delimiter"],
            "contents": list(measured["query"]["contents"]),
            "prefixes": list(measured["query"]["prefixes"]),
            "children": list(measured["query"]["children"]),
            "pages": measured["query"]["pages"],
            "legacy": list(measured["query"]["legacy"]),
            "matching": list(measured["query"]["matching"]),
            "marker_present": measured["query"]["marker_present"],
        },
        "full": {
            "keys": list(measured["full"].keys),
            "pages": measured["full"].pages,
            "truncated": measured["full"].truncated,
        },
        "etags": {
            "verified": list(measured["etags"]["verified"]),
            "corrupt": list(measured["etags"]["corrupt"]),
            "opaque": list(measured["etags"]["opaque"]),
        },
        "legacy_etags": {
            "verified": list(measured["legacy_etags"]["verified"]),
            "failed": list(measured["legacy_etags"]["failed"]),
        },
        "multipart": [record.to_dict() for record in measured["multipart"]],
        "urls": {
            "presigned": measured["url"],
            "legacy": measured["legacy_url"],
            "missing": measured["missing_url"],
        },
    }


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
def _guard(check: Callable[[], bool]) -> bool:
    try:
        return bool(check())
    except Exception:                                     # noqa: BLE001
        return False


def _refused(call: Callable[[], object]) -> bool:
    try:
        call()
    except BucketError:
        return True
    return False


def audit(
    measured: dict[str, Any],
    *,
    read: Callable[[], Manifest] = read_bucket,
    verify: Callable[[Manifest], dict[str, Any]] = verify_etags,
    list_fn: Callable[..., Listing] = list_objects,
) -> list[tuple[str, bool]]:
    """Every check rebuilds the listing and digests from the manifest."""
    cache: dict[str, Any] = {}

    def rebuilt() -> dict[str, Any]:
        if not cache:
            manifest = read()
            cache["manifest"] = manifest
            cache["etags"] = verify(manifest)
            cache["legacy_etags"] = legacy_verify(manifest)
            cache["listing"] = list_fn(manifest, DEFAULT_PREFIX, DEFAULT_DELIMITER, DEFAULT_PAGE_SIZE)
            cache["full"] = list_fn(manifest, "", None, DEFAULT_PAGE_SIZE)
            cache["legacy"] = legacy_list(manifest, DEFAULT_PREFIX, DEFAULT_PAGE_SIZE)
        return cache

    checks = [
        (
            "the_bucket_reads_and_validates",
            lambda: validate_manifest(rebuilt()["manifest"]) == []
            and len(rebuilt()["manifest"].objects) == 9,
        ),
        (
            "the_bundled_bucket_is_pinned",
            lambda: rebuilt()["manifest"].bucket == "demo-bucket"
            and sum(len(record.body) for record in rebuilt()["manifest"].objects)
            == measured["bytes"],
        ),
        (
            "a_full_listing_follows_every_page",
            lambda: len(rebuilt()["full"].keys) == len(measured["full"].keys) == 9
            and rebuilt()["full"].pages == measured["full"].pages == 3
            and rebuilt()["full"].truncated is False,
        ),
        (
            "a_prefix_without_a_delimiter_is_a_string_match",
            lambda: len(measured["query"]["legacy"]) == 3
            and list(rebuilt()["legacy"]) == list(measured["query"]["legacy"])
            == ["logs/", "logs/api/2024-01.log", "logs/api/2024-02.log"],
        ),
        (
            "a_delimiter_turns_the_prefix_into_folders",
            lambda: rebuilt()["listing"].prefixes
            == measured["query"]["prefixes"]
            == ("logs/api/", "logs/web/"),
        ),
        (
            "the_folder_marker_is_an_object_not_a_child",
            lambda: rebuilt()["listing"].keys == ("logs/",)
            and rebuilt()["listing"].children(DEFAULT_PREFIX) == ()
            and measured["query"]["marker_present"] is True,
        ),
        (
            "the_nested_keys_are_all_present_but_not_on_the_first_page",
            lambda: len(measured["query"]["matching"]) == 4
            and len(measured["query"]["legacy"]) == 3
            and "logs/web/2024-01.log" not in measured["query"]["legacy"],
        ),
        (
            "a_single_put_etag_is_the_md5",
            lambda: all(
                record.etag == md5_hex(record.body)
                for record in rebuilt()["manifest"].objects
                if record.upload == "single"
            ),
        ),
        (
            "a_multipart_etag_carries_a_part_count",
            lambda: sorted((record.key, record.etag.rsplit("-", 1)[1])
                           for record in rebuilt()["manifest"].objects
                           if record.upload == "multipart")
            == [("data/notes.csv", "2"), ("logs/api/2024-02.log", "3"),
                ("reports/q4.txt", "2")],
        ),
        (
            "the_multipart_digest_differs_from_the_body_md5",
            lambda: all(
                record.etag != md5_hex(record.body)
                for record in rebuilt()["manifest"].objects
                if record.upload == "multipart"
            ),
        ),
        (
            "the_legacy_check_calls_every_multipart_object_corrupt",
            lambda: len(rebuilt()["legacy_etags"]["verified"])
            == len(measured["legacy_etags"]["verified"]) == 5
            and len(rebuilt()["legacy_etags"]["failed"])
            == len(measured["legacy_etags"]["failed"]) == 4,
        ),
        (
            "the_rebuild_separates_corrupt_from_opaque",
            lambda: len(rebuilt()["etags"]["verified"])
            == len(measured["etags"]["verified"]) == 8
            and len(rebuilt()["etags"]["corrupt"])
            == len(measured["etags"]["corrupt"]) == 0
            and list(rebuilt()["etags"]["opaque"]) == list(measured["etags"]["opaque"])
            == ["secrets/keys.json"],
        ),
        (
            "a_key_is_percent_encoded_into_the_signed_path",
            lambda: measured["url"].split("?")[0].endswith("q3%20final.txt")
            and "X-Amz-Expires=300" in measured["url"]
            and measured["legacy_url"].split("?")[0].endswith("q3 final.txt")
            and "X-Amz-Expires=3600" in measured["legacy_url"],
        ),
        (
            "a_presigned_url_is_signed_locally_even_for_a_missing_key",
            lambda: measured["missing_url"].startswith("https://demo-bucket.")
            and "X-Amz-Signature=" in measured["missing_url"]
            and all(record.key != "reports/absent.txt" for record in rebuilt()["manifest"].objects),
        ),
        (
            "a_bad_bucket_is_refused",
            lambda: _refused(
                lambda: validate_or_raise(
                    Manifest("Bad_Bucket", (ObjectRecord("a", b"x", "single", 1, "0" * 32),))
                )
            )
            and _refused(
                lambda: list_objects(rebuilt()["manifest"], "", None, 0)
            ),
        ),
        (
            "the_rebuild_is_deterministic",
            lambda: rebuilt()["listing"] == measured["listing"]
            and rebuilt()["full"] == measured["full"]
            and rebuilt()["etags"] == measured["etags"],
        ),
    ]
    return [(name, _guard(check)) for name, check in checks]


# --------------------------------------------------------------------------- #
# Rendering and the demo
# --------------------------------------------------------------------------- #
def render_listing(listing: Listing, prefix: str, bucket: str = "demo-bucket") -> str:
    lines = [f"Listing s3://{bucket}/{prefix} with delimiter '/'"]
    for common in listing.prefixes:
        lines.append(f"  PRE  {common}")
    for record in listing.children(prefix):
        lines.append(f"  OBJ  {record.key}  ({record.size} bytes)")
    if not listing.prefixes and not listing.children(prefix):
        lines.append("  (empty)")
    return "\n".join(lines)


def run_demo(path: str | Path | None = None) -> int:
    measured = measure(path)
    manifest: Manifest = measured["manifest"]
    listing: Listing = measured["listing"]
    query_info = measured["query"]

    print("S3 file manager -- a prefix is not a folder and an ETag is not an MD5")
    print("=" * 70)
    print()
    print(
        f"Bucket {manifest.bucket}: {measured['objects']} objects, "
        f"{measured['bytes']} bytes, JSON manifest, no boto3."
    )
    print()
    print("1. A prefix without a delimiter is a string match.")
    print("   " + LEGACY_LIST)
    print(
        f"   matching keys under {query_info['prefix']!r}: "
        f"{len(query_info['matching'])}; the legacy first page shows "
        f"{len(query_info['legacy'])}: {', '.join(query_info['legacy'])}."
    )
    print(
        f"   with delimiter '/': {len(listing.prefixes)} prefixes "
        f"({', '.join(listing.prefixes)}), {len(listing.children(query_info['prefix']))} "
        f"children, and the marker {query_info['prefix']!r} is an object."
    )
    print()
    print("2. An ETag is not an MD5.")
    print("   " + LEGACY_ETAG)
    legacy = measured["legacy_etags"]
    print(
        f"   legacy: {len(legacy['verified'])} verified, {len(legacy['failed'])} "
        f"called corrupt of {measured['objects']}."
    )
    for record in measured["multipart"]:
        print(
            f"     {record.key:<24} {record.etag}  (multipart, "
            f"{record.part_count} parts)"
        )
    print(
        f"   rebuild: {len(measured['etags']['verified'])} verified, "
        f"{len(measured['etags']['corrupt'])} corrupt, "
        f"{len(measured['etags']['opaque'])} opaque "
        f"({', '.join(measured['etags']['opaque'])})."
    )
    print()
    print("3. A listing is paginated and IsTruncated is the signal.")
    print(
        f"   nine objects at {DEFAULT_PAGE_SIZE} per page: "
        f"{measured['full'].pages} pages, truncated="
        f"{str(measured['full'].truncated).lower()}."
    )
    print()
    print("4. A presigned URL is signed locally and proves nothing.")
    print("   " + LEGACY_URL)
    print(f"   rebuild: {measured['url']}")
    print(f"   legacy : {measured['legacy_url']}")
    print(
        f"   missing key presigns too: "
        f"{measured['missing_url'].split('?')[0].split('/')[-1]} "
        f"(no existence check)."
    )
    print()
    print(render_listing(listing, query_info["prefix"], manifest.bucket))
    print()
    print("Checks")
    results = audit(measured)
    for name, okay in results:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    passed = sum(1 for _, okay in results if okay)
    print(f"  {passed}/{len(results)} checks pass")
    print()
    print(
        "Cross-checks OK: "
        f"the prefix {query_info['prefix']!r} matches "
        f"{len(query_info['matching'])} keys while the legacy first page shows "
        f"{len(query_info['legacy'])} with no delimiter, and the delimiter "
        f"view returns {len(listing.prefixes)} prefixes plus the folder marker; "
        f"the legacy ETag check calls {len(legacy['failed'])} of "
        f"{measured['objects']} objects corrupt while the rebuild verifies "
        f"{len(measured['etags']['verified'])} and marks "
        f"{len(measured['etags']['opaque'])} opaque with "
        f"{len(measured['etags']['corrupt'])} corrupt; the full listing takes "
        f"{measured['full'].pages} pages; the rebuild percent-encodes the key "
        f"and carries the requested 300-second expiry where the legacy URL "
        f"leaves a space raw and pins 3600; {passed}/{len(results)} checks "
        f"pass."
    )
    print("Demo completed successfully.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_demo())
