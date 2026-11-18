"""Tests for the S3 File Manager project."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from s3_manager import (  # noqa: E402
    BUCKET_FILE,
    DATA_DIR,
    DEFAULT_DELIMITER,
    DEFAULT_EXPIRES,
    DEFAULT_PAGE_SIZE,
    DEFAULT_PREFIX,
    LEGACY_ETAG,
    LEGACY_LIST,
    LEGACY_URL,
    MAX_BODY,
    MAX_OBJECTS,
    MAX_PARTS,
    BucketError,
    Listing,
    Manifest,
    ObjectRecord,
    audit,
    encode_key,
    expected_etag,
    legacy_list,
    legacy_presign,
    legacy_verify,
    list_objects,
    manifest_from_document,
    md5_hex,
    measure,
    multipart_etag,
    multipart_records,
    presign,
    query,
    read_bucket,
    render_listing,
    report,
    run_demo,
    validate_manifest,
    validate_or_raise,
    verify_etags,
)
from main import main  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
def single(key: str, body: str = "body") -> ObjectRecord:
    data = body.encode("ascii")
    return ObjectRecord(key, data, "single", 1, md5_hex(data))


def multipart(key: str, body: str, parts: int) -> ObjectRecord:
    data = body.encode("ascii")
    return ObjectRecord(key, data, "multipart", parts, multipart_etag(data, parts))


def kms(key: str, body: str = "x") -> ObjectRecord:
    return ObjectRecord(key, body.encode("ascii"), "kms", 1, "0" * 32)


def manifest(*records: ObjectRecord) -> Manifest:
    return Manifest("demo-bucket", tuple(records))


def write_bucket(tmp_path: Path, document: object) -> Path:
    target = tmp_path / "bucket.json"
    target.write_text(json.dumps(document), encoding="utf-8")
    return target


def document_for(records: list[dict]) -> dict:
    return {"bucket": "demo-bucket", "objects": records}


# --------------------------------------------------------------------------- #
# Digests
# --------------------------------------------------------------------------- #
def test_md5_of_empty_bytes_is_the_well_known_digest():
    assert md5_hex(b"") == "d41d8cd98f00b204e9800998ecf8427e"


def test_md5_of_abc_is_the_well_known_digest():
    assert md5_hex(b"abc") == "900150983cd24fb0d6963f7d28e17f72"


def test_a_single_put_etag_is_thirty_two_hex_characters():
    assert len(md5_hex(b"quarterly")) == 32


def test_multipart_etag_ends_with_the_part_count():
    assert multipart_etag(b"abcdef", 3).endswith("-3")


def test_multipart_etag_is_a_digest_plus_a_suffix():
    etag = multipart_etag(b"abcdef", 2)
    digest, suffix = etag.rsplit("-", 1)
    assert len(digest) == 32 and suffix == "2"


def test_multipart_etag_differs_from_the_body_md5():
    assert multipart_etag(b"abcdef", 2) != md5_hex(b"abcdef")


def test_multipart_etag_depends_on_the_part_count():
    assert multipart_etag(b"abcdef", 2) != multipart_etag(b"abcdef", 3)


def test_multipart_etag_with_one_part_is_still_a_multipart_digest():
    assert multipart_etag(b"abcdef", 1).endswith("-1")


def test_multipart_etag_of_empty_bytes_keeps_every_part():
    assert multipart_etag(b"", 2).endswith("-2")


def test_multipart_etag_refuses_a_zero_part_count():
    with pytest.raises(BucketError, match="at least one part"):
        multipart_etag(b"x", 0)


def test_expected_etag_for_a_single_upload():
    assert expected_etag(b"abc", "single") == md5_hex(b"abc")


def test_expected_etag_for_a_multipart_upload():
    assert expected_etag(b"abc", "multipart", 2) == multipart_etag(b"abc", 2)


def test_expected_etag_refuses_a_kms_object():
    with pytest.raises(BucketError, match="no derivable ETag"):
        expected_etag(b"abc", "kms")


def test_the_seeded_multipart_etags_are_pinned():
    manifest = read_bucket()
    etags = {record.key: record.etag for record in manifest.objects}
    assert etags["data/notes.csv"] == "e56cf7fcf775d0dfa1d7989a26aaad20-2"
    assert etags["logs/api/2024-02.log"] == "bccf4c49dc12606f2d3bf06a1876fe66-3"
    assert etags["reports/q4.txt"] == "4fef504003bf31cc74a67bfdcd1804c0-2"


def test_the_seeded_single_etag_is_pinned():
    manifest = read_bucket()
    etags = {record.key: record.etag for record in manifest.objects}
    assert etags["reports/q3 final.txt"] == "cf65e1ce220c95aafaa02c82d52791aa"


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
def test_a_record_reports_its_size():
    assert single("a", "abc").size == 3


def test_a_record_maps_its_upload_to_an_etag_kind():
    assert single("a").kind == "md5"
    assert multipart("b", "abcdef", 2).kind == "multipart"
    assert kms("c").kind == "opaque"


def test_a_record_reports_itself_as_a_dict():
    assert single("a", "abc").to_dict() == {
        "key": "a",
        "size": 3,
        "upload": "single",
        "part_count": 1,
        "etag": md5_hex(b"abc"),
        "etag_kind": "md5",
    }


def test_a_record_is_frozen():
    record = single("a")
    with pytest.raises(Exception):
        record.key = "b"  # type: ignore[misc]


def test_a_listing_keys_property_keeps_order():
    listing = Listing((single("a"), single("b")), (), 1, False)
    assert listing.keys == ("a", "b")


def test_listing_children_exclude_the_folder_marker():
    listing = Listing((single("logs/"), single("logs/a.log")), (), 1, False)
    assert [record.key for record in listing.children("logs/")] == ["logs/a.log"]


def test_listing_children_of_an_empty_listing_are_empty():
    assert Listing((), (), 1, False).children("logs/") == ()


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #
def test_read_bucket_reads_the_bundled_manifest():
    manifest = read_bucket()
    assert manifest.bucket == "demo-bucket"
    assert len(manifest.objects) == 9


def test_read_bucket_reads_an_explicit_path(tmp_path):
    target = write_bucket(
        tmp_path,
        document_for([{"key": "a", "body": "x", "upload": "single",
                       "etag": md5_hex(b"x")}]),
    )
    assert read_bucket(target).objects[0].key == "a"


def test_read_bucket_refuses_a_missing_file(tmp_path):
    with pytest.raises(BucketError, match="bucket not found: absent.json"):
        read_bucket(tmp_path / "absent.json")


def test_read_bucket_refuses_non_ascii_bytes(tmp_path):
    target = tmp_path / "bad.json"
    target.write_bytes(b'{"bucket": "d\xc3\xa9mo"}')
    with pytest.raises(BucketError, match="bad.json is not ASCII text"):
        read_bucket(target)


def test_read_bucket_names_the_line_of_broken_json(tmp_path):
    target = tmp_path / "broken.json"
    target.write_text('{"bucket": "x",}', encoding="utf-8")
    with pytest.raises(BucketError, match="broken.json is not valid JSON: line 1"):
        read_bucket(target)


def test_read_bucket_refuses_a_list_root(tmp_path):
    target = tmp_path / "list.json"
    target.write_text("[]", encoding="utf-8")
    with pytest.raises(BucketError, match="a bucket root must be a mapping"):
        read_bucket(target)


def test_manifest_from_document_ignores_a_non_list_objects_field():
    assert manifest_from_document({"bucket": "b", "objects": {}}).objects == ()


def test_manifest_from_document_ignores_non_object_entries():
    assert manifest_from_document(
        {"bucket": "b", "objects": ["a", 1]}
    ).objects == ()


def test_manifest_from_document_turns_a_non_text_body_into_empty():
    built = manifest_from_document(
        {"bucket": "b", "objects": [{"key": "a", "body": 1, "etag": "0" * 32}]}
    )
    assert built.objects[0].body == b""


def test_manifest_from_document_turns_an_unknown_upload_into_single():
    built = manifest_from_document(
        {"bucket": "b", "objects": [{"key": "a", "upload": "quantum", "etag": "0" * 32}]}
    )
    assert built.objects[0].upload == "single"


def test_manifest_from_document_turns_a_boolean_part_count_into_zero():
    built = manifest_from_document(
        {"bucket": "b", "objects": [{"key": "a", "part_count": True, "etag": "0" * 32}]}
    )
    assert built.objects[0].part_count == 0


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def test_the_bundled_bucket_validates():
    assert validate_manifest(read_bucket()) == []


def test_a_bad_bucket_name_is_reported():
    broken = replace(manifest(single("a")), bucket="Bad_Bucket")
    assert any("$.bucket" in item for item in validate_manifest(broken))


def test_an_empty_object_list_is_reported():
    assert any("non-empty array" in item for item in validate_manifest(Manifest("demo", ())))


def test_too_many_objects_are_reported():
    records = tuple(single(f"k{index}") for index in range(MAX_OBJECTS + 1))
    assert any(f"at most {MAX_OBJECTS}" in item for item in validate_manifest(manifest(*records)))


def test_the_object_cap_itself_is_allowed():
    records = tuple(single(f"k{index}") for index in range(MAX_OBJECTS))
    assert validate_manifest(manifest(*records)) == []


def test_an_empty_key_is_reported():
    broken = manifest(replace(single("a"), key=""))
    assert any("non-empty key" in item for item in validate_manifest(broken))


def test_a_leading_slash_key_is_reported():
    broken = manifest(replace(single("a"), key="/a"))
    assert any("leading '/'" in item for item in validate_manifest(broken))


def test_a_duplicate_key_is_reported():
    broken = manifest(single("a"), single("a"))
    assert any("duplicate object 'a'" in item for item in validate_manifest(broken))


def test_an_oversized_body_is_reported():
    broken = manifest(single("a", "x" * (MAX_BODY + 1)))
    assert any(f"at most {MAX_BODY} bytes" in item for item in validate_manifest(broken))


def test_an_unknown_upload_mode_is_reported():
    broken = manifest(replace(single("a"), upload="quantum"))
    assert any("upload: choose one of" in item for item in validate_manifest(broken))


def test_a_zero_part_count_is_reported():
    broken = manifest(replace(single("a"), part_count=0))
    assert any("part_count: an integer 1.." in item for item in validate_manifest(broken))


def test_a_part_count_above_the_cap_is_reported():
    broken = manifest(replace(single("a"), part_count=MAX_PARTS + 1))
    assert any("part_count: an integer 1.." in item for item in validate_manifest(broken))


def test_a_multipart_upload_with_one_part_is_reported():
    broken = manifest(replace(multipart("a", "abcdef", 2), part_count=1))
    assert any("at least 2 parts" in item for item in validate_manifest(broken))


def test_a_single_upload_with_parts_is_reported():
    broken = manifest(replace(single("a"), part_count=2))
    assert any("only a multipart upload has parts" in item for item in validate_manifest(broken))


def test_a_bad_etag_is_reported():
    broken = manifest(replace(single("a"), declared_etag="nope"))
    assert any("32-hex digest" in item for item in validate_manifest(broken))


def test_a_multipart_etag_must_match_the_part_count():
    broken = manifest(replace(multipart("a", "abcdef", 2), declared_etag="0" * 32 + "-3"))
    assert any("suffix must match part_count" in item for item in validate_manifest(broken))


def test_a_single_etag_may_not_carry_a_part_suffix():
    broken = manifest(replace(single("a"), declared_etag="0" * 32 + "-2"))
    assert any("only a multipart upload has a part suffix" in item
               for item in validate_manifest(broken))


def test_a_kms_etag_may_not_carry_a_part_suffix():
    broken = manifest(replace(kms("a"), declared_etag="0" * 32 + "-2"))
    assert any("only a multipart upload has a part suffix" in item
               for item in validate_manifest(broken))


def test_problems_accumulate():
    broken = Manifest("Bad_Bucket", (replace(single("a"), part_count=0),))
    assert len(validate_manifest(broken)) >= 3


def test_validate_or_raise_names_the_problem_count():
    with pytest.raises(BucketError, match=r"invalid bucket \(2 problem"):
        validate_or_raise(Manifest("Bad_Bucket", ()))


def test_validate_or_raise_accepts_the_bundled_bucket():
    assert validate_or_raise(read_bucket()) is None


# --------------------------------------------------------------------------- #
# Listing
# --------------------------------------------------------------------------- #
def test_a_full_listing_contains_every_key_in_order():
    listing = list_objects(read_bucket(), "", None, 100)
    assert list(listing.keys) == [
        "data/archive.zip",
        "data/notes.csv",
        "logs/",
        "logs/api/2024-01.log",
        "logs/api/2024-02.log",
        "logs/web/2024-01.log",
        "reports/q3 final.txt",
        "reports/q4.txt",
        "secrets/keys.json",
    ]


def test_a_full_listing_follows_three_pages_of_three():
    listing = list_objects(read_bucket())
    assert listing.pages == 3
    assert listing.truncated is False
    assert len(listing.keys) == 9


def test_page_size_one_takes_nine_pages():
    assert list_objects(read_bucket(), "", None, 1).pages == 9


def test_page_size_nine_takes_one_page():
    assert list_objects(read_bucket(), "", None, 9).pages == 1


def test_a_prefix_without_a_delimiter_lists_every_matching_key():
    listing = list_objects(read_bucket(), "logs/", None, 100)
    assert len(listing.keys) == 4
    assert listing.prefixes == ()


def test_a_delimiter_splits_the_prefix_into_common_prefixes():
    listing = list_objects(read_bucket(), "logs/", "/", 100)
    assert listing.prefixes == ("logs/api/", "logs/web/")


def test_a_delimiter_keeps_the_folder_marker_as_an_object():
    listing = list_objects(read_bucket(), "logs/", "/", 100)
    assert listing.keys == ("logs/",)


def test_the_folder_marker_has_no_children():
    listing = list_objects(read_bucket(), "logs/", "/", 100)
    assert listing.children("logs/") == ()


def test_data_prefix_lists_its_two_objects_without_prefixes():
    listing = list_objects(read_bucket(), "data/", "/", 100)
    assert listing.keys == ("data/archive.zip", "data/notes.csv")
    assert listing.prefixes == ()


def test_a_prefix_matching_nothing_is_an_empty_listing():
    listing = list_objects(read_bucket(), "absent/", "/", 100)
    assert listing.keys == () and listing.prefixes == () and listing.pages == 1


def test_an_exact_key_as_prefix_matches_only_itself():
    listing = list_objects(read_bucket(), "logs/api/2024-01.log", "/", 100)
    assert listing.keys == ("logs/api/2024-01.log",)


def test_a_duplicate_common_prefix_appears_once():
    listing = list_objects(read_bucket(), "logs/", "/", 100)
    assert listing.prefixes.count("logs/api/") == 1


def test_the_root_with_a_delimiter_has_four_prefixes():
    listing = list_objects(read_bucket(), "", "/", 100)
    assert listing.prefixes == ("data/", "logs/", "reports/", "secrets/")


def test_page_size_must_be_at_least_one():
    with pytest.raises(BucketError, match="page_size must be at least 1"):
        list_objects(read_bucket(), "", None, 0)


def test_a_listing_pages_over_prefixes_and_objects_together():
    listing = list_objects(read_bucket(), "", "/", 3)
    assert listing.pages == 2


def test_the_legacy_list_stops_at_the_first_page():
    assert legacy_list(read_bucket(), "logs/") == [
        "logs/",
        "logs/api/2024-01.log",
        "logs/api/2024-02.log",
    ]


def test_the_legacy_list_misses_the_fourth_key():
    keys = legacy_list(read_bucket(), "logs/")
    assert len(keys) == 3
    assert "logs/web/2024-01.log" not in keys


def test_the_legacy_full_list_shows_three_of_nine():
    assert len(legacy_list(read_bucket(), "")) == 3


def test_the_legacy_list_can_be_widened_explicitly():
    assert len(legacy_list(read_bucket(), "logs/", 100)) == 4


def test_the_legacy_list_of_an_unknown_prefix_is_empty():
    assert legacy_list(read_bucket(), "absent/") == []


def test_query_keeps_the_folder_view_and_the_string_view_apart():
    info = query(read_bucket())
    assert info["prefix"] == "logs/"
    assert info["delimiter"] == "/"
    assert info["contents"] == ("logs/",)
    assert info["prefixes"] == ("logs/api/", "logs/web/")
    assert info["children"] == ()
    assert info["legacy"] == (
        "logs/",
        "logs/api/2024-01.log",
        "logs/api/2024-02.log",
    )


def test_query_finds_all_four_matching_keys():
    info = query(read_bucket())
    assert len(info["matching"]) == 4
    assert info["marker_present"] is True


def test_query_can_run_without_a_delimiter():
    info = query(read_bucket(), "logs/", None)
    assert info["prefixes"] == ()
    assert len(info["contents"]) == 4


def test_a_query_prefix_default_is_logs():
    assert DEFAULT_PREFIX == "logs/"


# --------------------------------------------------------------------------- #
# ETag verification
# --------------------------------------------------------------------------- #
def test_the_bundled_verification_passes_eight_and_marks_one_opaque():
    result = verify_etags(read_bucket())
    assert len(result["verified"]) == 8
    assert result["corrupt"] == ()
    assert result["opaque"] == ("secrets/keys.json",)


def test_every_single_upload_verifies_as_its_md5():
    manifest = read_bucket()
    for record in manifest.objects:
        if record.upload == "single":
            assert record.etag == md5_hex(record.body)


def test_the_bundled_legacy_check_fails_four():
    result = legacy_verify(read_bucket())
    assert len(result["verified"]) == 5
    assert len(result["failed"]) == 4


def test_the_legacy_failures_are_the_multipart_objects_and_the_kms_one():
    assert set(legacy_verify(read_bucket())["failed"]) == {
        "data/notes.csv",
        "logs/api/2024-02.log",
        "reports/q4.txt",
        "secrets/keys.json",
    }


def test_a_corrupt_single_upload_is_reported():
    record = replace(single("a", "abc"), declared_etag="0" * 32)
    assert verify_etags(manifest(record))["corrupt"] == ("a",)


def test_a_corrupt_multipart_upload_is_reported():
    record = replace(multipart("a", "abcdef", 2), declared_etag="0" * 32 + "-2")
    assert verify_etags(manifest(record))["corrupt"] == ("a",)


def test_an_opaque_record_is_never_called_corrupt():
    record = replace(kms("a"), declared_etag="f" * 32)
    result = verify_etags(manifest(record))
    assert result["opaque"] == ("a",)
    assert result["corrupt"] == ()


def test_a_correct_multipart_record_verifies():
    record = multipart("a", "abcdef", 3)
    assert verify_etags(manifest(record))["verified"] == ("a",)


def test_the_legacy_check_fails_a_correct_multipart_record():
    record = multipart("a", "abcdef", 3)
    assert legacy_verify(manifest(record))["failed"] == ("a",)


def test_multipart_records_are_the_three_seeded_ones():
    keys = [record.key for record in multipart_records(read_bucket())]
    assert keys == ["data/notes.csv", "logs/api/2024-02.log", "reports/q4.txt"]


def test_multipart_records_carry_two_three_and_two_parts():
    assert [record.part_count for record in multipart_records(read_bucket())] == [2, 3, 2]


# --------------------------------------------------------------------------- #
# Presigned URLs
# --------------------------------------------------------------------------- #
def test_encode_key_keeps_slashes():
    assert encode_key("logs/a.log") == "logs/a.log"


def test_encode_key_percent_encodes_a_space():
    assert encode_key("reports/q3 final.txt") == "reports/q3%20final.txt"


def test_encode_key_percent_encodes_a_plus():
    assert encode_key("a+b") == "a%2Bb"


def test_presign_encodes_the_key_in_the_path():
    url = presign(read_bucket(), "reports/q3 final.txt")
    assert "/reports/q3%20final.txt?" in url


def test_presign_carries_the_requested_expiry():
    assert "X-Amz-Expires=300" in presign(read_bucket(), "a")


def test_presign_uses_the_supplied_expiry():
    assert "X-Amz-Expires=60" in presign(read_bucket(), "a", 60)


def test_presign_refuses_a_zero_expiry():
    with pytest.raises(BucketError, match="between 1 and 604800"):
        presign(read_bucket(), "a", 0)


def test_presign_refuses_an_expiry_beyond_a_week():
    with pytest.raises(BucketError, match="between 1 and 604800"):
        presign(read_bucket(), "a", 604_801)


def test_presign_produces_a_sixteen_hex_signature():
    url = presign(read_bucket(), "a")
    signature = url.rsplit("X-Amz-Signature=", 1)[1]
    assert len(signature) == 16
    assert all(char in "0123456789abcdef" for char in signature)


def test_the_signature_changes_with_the_expiry():
    assert presign(read_bucket(), "a", 300) != presign(read_bucket(), "a", 301)


def test_the_signature_changes_with_the_key():
    assert presign(read_bucket(), "a") != presign(read_bucket(), "b")


def test_the_signature_changes_with_the_secret():
    assert presign(read_bucket(), "a", 300, "one") != presign(read_bucket(), "a", 300, "two")


def test_presign_is_deterministic():
    assert presign(read_bucket(), "a") == presign(read_bucket(), "a")


def test_presign_signs_a_key_that_does_not_exist():
    url = presign(read_bucket(), "reports/absent.txt")
    assert "reports/absent.txt" in url and "X-Amz-Signature=" in url


def test_legacy_presign_leaves_the_space_raw():
    url = legacy_presign(read_bucket(), "reports/q3 final.txt")
    assert "/reports/q3 final.txt?" in url


def test_legacy_presign_pins_a_one_hour_expiry():
    assert "X-Amz-Expires=3600" in legacy_presign(read_bucket(), "a")


def test_legacy_presign_disagrees_with_the_rebuild():
    assert presign(read_bucket(), "a") != legacy_presign(read_bucket(), "a")


# --------------------------------------------------------------------------- #
# Measurement and the JSON report
# --------------------------------------------------------------------------- #
def test_measure_counts_nine_objects_and_308_bytes():
    measured = measure()
    assert measured["objects"] == 9
    assert measured["bytes"] == 308


def test_measure_pins_the_delimiter_query():
    info = measure()["query"]
    assert info["prefixes"] == ("logs/api/", "logs/web/")
    assert info["legacy"] == (
        "logs/",
        "logs/api/2024-01.log",
        "logs/api/2024-02.log",
    )


def test_measure_pins_the_full_listing():
    full = measure()["full"]
    assert len(full.keys) == 9 and full.pages == 3 and full.truncated is False


def test_measure_pins_the_etag_counts():
    measured = measure()
    assert len(measured["etags"]["verified"]) == 8
    assert measured["etags"]["corrupt"] == ()
    assert len(measured["legacy_etags"]["failed"]) == 4


def test_measure_pins_the_urls():
    measured = measure()
    assert "q3%20final.txt" in measured["url"]
    assert "q3 final.txt" in measured["legacy_url"]


def test_report_is_json_safe():
    body = json.loads(json.dumps(report(measure())))
    assert body["bucket"] == "demo-bucket"
    assert body["count"] == 9


def test_report_holds_no_body_bytes():
    body = report(measure())
    assert all("body" not in record for record in body["objects"])
    assert body["objects"][0]["etag_kind"] == "md5"


def test_report_keeps_the_three_urls():
    assert set(report(measure())["urls"]) == {"presigned", "legacy", "missing"}


def test_report_keeps_the_query_as_lists():
    info = report(measure())["query"]
    assert info["prefixes"] == ["logs/api/", "logs/web/"]
    assert isinstance(info["contents"], list)


def test_measure_is_deterministic():
    first = measure()
    second = measure()
    assert first["full"] == second["full"]
    assert first["url"] == second["url"]


def test_measure_accepts_a_custom_prefix():
    measured = measure(None, "data/", "/", 3)
    assert measured["query"]["contents"] == ("data/archive.zip", "data/notes.csv")


def test_measure_accepts_a_page_size():
    assert measure(None, "logs/", "/", 1)["query"]["pages"] == 3


# --------------------------------------------------------------------------- #
# Audit and its negative controls
# --------------------------------------------------------------------------- #
def test_audit_reports_sixteen_checks_and_all_pass():
    results = audit(measure())
    assert len(results) == 16
    assert [name for name, okay in results if not okay] == []


def test_every_audit_check_has_a_name():
    assert all(isinstance(name, str) and name for name, _ in audit(measure()))


def test_a_smaller_manifest_flips_the_pinned_checks():
    small = manifest(single("a"), single("b"))
    results = dict(audit(measure(), read=lambda: small))
    assert results["the_bucket_reads_and_validates"] is False
    assert results["a_full_listing_follows_every_page"] is False


def test_a_corrupt_etag_flips_the_verification_checks():
    record = replace(single("a", "abc"), declared_etag="0" * 32)
    results = dict(audit(measure(), read=lambda: manifest(record)))
    assert results["the_rebuild_separates_corrupt_from_opaque"] is False


def test_a_different_verifier_flips_the_rebuild_check():
    def empty(_: Manifest) -> dict:
        return {"verified": (), "corrupt": (), "opaque": ()}

    results = dict(audit(measure(), verify=empty))
    assert results["the_rebuild_separates_corrupt_from_opaque"] is False


def test_an_empty_lister_flips_the_delimiter_check():
    def nothing(*args, **kwargs) -> Listing:
        return Listing((), (), 1, False)

    results = dict(audit(measure(), list_fn=nothing))
    assert results["a_delimiter_turns_the_prefix_into_folders"] is False
    assert results["the_folder_marker_is_an_object_not_a_child"] is False


def test_a_raising_reader_fails_checks_instead_of_raising():
    def explode() -> Manifest:
        raise RuntimeError("disk gone")

    results = dict(audit(measure(), read=explode))
    assert results["the_bucket_reads_and_validates"] is False
    assert any(value is False for value in results.values())


def test_a_tampered_etag_summary_flips_the_rebuild_check():
    measured = measure()
    measured["etags"]["verified"] = ()
    results = dict(audit(measured))
    assert results["the_rebuild_separates_corrupt_from_opaque"] is False


def test_a_tampered_legacy_failure_count_flips_the_legacy_check():
    measured = measure()
    measured["legacy_etags"]["failed"] = ()
    results = dict(audit(measured))
    assert results["the_legacy_check_calls_every_multipart_object_corrupt"] is False


def test_a_tampered_listing_flips_the_determinism_check():
    measured = measure()
    measured["full"] = Listing((), (), 1, False)
    results = dict(audit(measured))
    assert results["the_rebuild_is_deterministic"] is False


# --------------------------------------------------------------------------- #
# Rendering and the demo
# --------------------------------------------------------------------------- #
def test_render_listing_shows_prefixes_and_children():
    text = render_listing(list_objects(read_bucket(), "data/", "/", 100), "data/")
    assert "OBJ  data/archive.zip" in text
    assert "OBJ  data/notes.csv" in text


def test_render_listing_shows_the_bucket_in_its_header():
    text = render_listing(list_objects(read_bucket(), "logs/", "/", 100), "logs/")
    assert text.splitlines()[0] == "Listing s3://demo-bucket/logs/ with delimiter '/'"


def test_run_demo_returns_zero_and_ends_with_the_two_contract_lines(capsys):
    assert run_demo() == 0
    lines = capsys.readouterr().out.rstrip("\n").splitlines()
    assert lines[-1] == "Demo completed successfully."
    assert lines[-2].startswith("Cross-checks OK: ")


def test_run_demo_is_byte_identical_across_runs(capsys):
    assert run_demo() == 0
    first = capsys.readouterr().out
    assert run_demo() == 0
    second = capsys.readouterr().out
    assert first == second


def test_run_demo_prints_the_three_legacy_shortcuts(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert LEGACY_LIST in out
    assert LEGACY_ETAG in out
    assert LEGACY_URL in out


def test_run_demo_prints_the_pinned_counts(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "legacy: 5 verified, 4 called corrupt of 9" in out
    assert "rebuild: 8 verified, 0 corrupt, 1 opaque" in out
    assert "16/16 checks pass" in out


def test_run_demo_prints_the_percent_encoded_key(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "reports/q3%20final.txt" in out
    assert "reports/q3 final.txt" in out


# --------------------------------------------------------------------------- #
# Command line
# --------------------------------------------------------------------------- #
def test_cli_demo_returns_zero():
    assert main(["--demo"]) == 0


def test_cli_demo_quiet_prints_nothing(capsys):
    assert main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_cli_audit_returns_zero_and_prints_pass_lines(capsys):
    assert main(["--audit"]) == 0
    assert "PASS  a_delimiter_turns_the_prefix_into_folders" in capsys.readouterr().out


def test_cli_writes_a_json_report(tmp_path):
    target = tmp_path / "nested" / "report.json"
    assert main(["--json", str(target)]) == 0
    body = json.loads(target.read_text(encoding="utf-8"))
    assert body["count"] == 9


def test_cli_prints_the_listing_and_the_etag_table(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "Listing s3://demo-bucket/logs/" in out
    assert "data/notes.csv" in out
    assert "multipart" in out


def test_cli_honours_a_custom_prefix(capsys):
    assert main(["--prefix", "data/"]) == 0
    out = capsys.readouterr().out
    assert "data/archive.zip" in out
    assert "data/notes.csv" in out


def test_cli_honours_an_empty_delimiter(capsys):
    assert main(["--prefix", "logs/", "--delimiter", ""]) == 0
    out = capsys.readouterr().out
    assert "logs/web/2024-01.log" in out


def test_cli_refuses_a_missing_bucket_with_exit_two(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "absent.json")]) == 2
    assert "error: bucket not found" in capsys.readouterr().err


def test_cli_refuses_an_invalid_bucket_with_exit_two(tmp_path, capsys):
    target = write_bucket(
        tmp_path,
        {"bucket": "Bad_Bucket", "objects": [{"key": "a", "body": "x", "etag": "0" * 32}]},
    )
    assert main(["--file", str(target)]) == 2
    assert "invalid bucket" in capsys.readouterr().err


def test_cli_refuses_a_zero_page_size_with_exit_two(capsys):
    assert main(["--page-size", "0"]) == 2
    assert "page_size must be at least 1" in capsys.readouterr().err


def test_cli_quiet_without_demo_prints_nothing(capsys):
    assert main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_the_bundled_bucket_is_ascii():
    raw = BUCKET_FILE.read_bytes()
    assert all(byte < 128 for byte in raw)


def test_defaults_are_pinned():
    assert DEFAULT_PREFIX == "logs/"
    assert DEFAULT_DELIMITER == "/"
    assert DEFAULT_PAGE_SIZE == 3
    assert DEFAULT_EXPIRES == 300


def test_data_directory_matches_the_bucket_file():
    assert BUCKET_FILE.parent == DATA_DIR
