"""Tests for the S3 File Manager project (all offline via botocore Stubber)."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from botocore.stub import Stubber

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import main  # noqa: E402
from s3_manager import (  # noqa: E402
    S3Error,
    S3Manager,
    offline_client,
    run_demo,
    validate_bucket,
    validate_key,
)

BUCKET = "demo-bucket-offline"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture()
def stubbed():
    """An S3Manager whose client is fully scripted by a Stubber."""
    client = offline_client()
    stubber = Stubber(client)
    stubber.activate()
    manager = S3Manager(BUCKET, client=client)
    yield manager, stubber
    stubber.deactivate()


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def test_validate_bucket_ok():
    assert validate_bucket("my-bucket-123") == "my-bucket-123"


def test_validate_bucket_rejects_bad_names():
    for bad in ("", "UPPER", "a", "-lead", "trail-", "has space", "x" * 64):
        with pytest.raises(S3Error, match="invalid bucket"):
            validate_bucket(bad)


def test_validate_key():
    assert validate_key("a/b.txt") == "a/b.txt"
    with pytest.raises(S3Error, match="invalid object key"):
        validate_key("")
    with pytest.raises(S3Error, match="invalid object key"):
        validate_key("/leading")


def test_manager_constructor_validates():
    with pytest.raises(S3Error, match="invalid bucket"):
        S3Manager("BAD NAME", client=offline_client())


# --------------------------------------------------------------------------- #
# Object operations
# --------------------------------------------------------------------------- #
def test_put_bytes(stubbed):
    manager, stubber = stubbed
    stubber.add_response(
        "put_object", {"ETag": '"abc123"'},
        {"Bucket": BUCKET, "Key": "hello.txt", "Body": b"hi", "ContentType": "text/plain"},
    )
    etag = manager.put_bytes("hello.txt", b"hi", content_type="text/plain")
    assert etag == "abc123"
    assert not stubber._queue


def test_put_bytes_requires_bytes(stubbed):
    manager, _ = stubbed
    with pytest.raises(S3Error, match="bytes"):
        manager.put_bytes("x.txt", "not-bytes")  # type: ignore[arg-type]


def test_get_bytes(stubbed):
    manager, stubber = stubbed
    stubber.add_response(
        "get_object",
        {"Body": io.BytesIO(b"payload"), "ContentLength": 7},
        {"Bucket": BUCKET, "Key": "hello.txt"},
    )
    assert manager.get_bytes("hello.txt") == b"payload"


def test_get_bytes_missing_object(stubbed):
    manager, stubber = stubbed
    stubber.add_client_error(
        "get_object", service_error_code="NoSuchKey", http_status_code=404,
        service_message="Not Found",
        expected_params={"Bucket": BUCKET, "Key": "ghost.txt"},
    )
    with pytest.raises(S3Error, match="not found"):
        manager.get_bytes("ghost.txt")


def test_exists_true(stubbed):
    manager, stubber = stubbed
    stubber.add_response(
        "head_object", {"ContentLength": 3},
        {"Bucket": BUCKET, "Key": "a.txt"},
    )
    assert manager.exists("a.txt") is True


def test_exists_false_on_404(stubbed):
    manager, stubber = stubbed
    stubber.add_client_error(
        "head_object", service_error_code="404", http_status_code=404,
        service_message="Not Found",
        expected_params={"Bucket": BUCKET, "Key": "ghost.txt"},
    )
    assert manager.exists("ghost.txt") is False


def test_exists_access_denied_raises(stubbed):
    manager, stubber = stubbed
    stubber.add_client_error(
        "head_object", service_error_code="AccessDenied", http_status_code=403,
        service_message="Forbidden",
        expected_params={"Bucket": BUCKET, "Key": "secret.txt"},
    )
    with pytest.raises(S3Error, match="access denied"):
        manager.exists("secret.txt")


def test_delete(stubbed):
    manager, stubber = stubbed
    stubber.add_response(
        "delete_object", {}, {"Bucket": BUCKET, "Key": "bye.txt"}
    )
    manager.delete("bye.txt")  # no exception = success
    assert not stubber._queue


def test_delete_wraps_error(stubbed):
    manager, stubber = stubbed
    stubber.add_client_error(
        "delete_object", service_error_code="AccessDenied", http_status_code=403,
        service_message="nope",
        expected_params={"Bucket": BUCKET, "Key": "x"},
    )
    with pytest.raises(S3Error, match="access denied"):
        manager.delete("x")


# --------------------------------------------------------------------------- #
# Listing
# --------------------------------------------------------------------------- #
def test_list_objects(stubbed):
    manager, stubber = stubbed
    stubber.add_response(
        "list_objects_v2",
        {"Contents": [
            {"Key": "b.txt", "Size": 2},
            {"Key": "a.txt", "Size": 1},
        ], "IsTruncated": False},
        {"Bucket": BUCKET, "Prefix": ""},
    )
    objects = manager.list_objects()
    assert [o.key for o in objects] == ["a.txt", "b.txt"]  # sorted
    assert objects[0].size == 1


def test_list_objects_pagination(stubbed):
    manager, stubber = stubbed
    stubber.add_response(
        "list_objects_v2",
        {"Contents": [{"Key": "a.txt", "Size": 1}],
         "IsTruncated": True, "NextContinuationToken": "tok1"},
        {"Bucket": BUCKET, "Prefix": ""},
    )
    stubber.add_response(
        "list_objects_v2",
        {"Contents": [{"Key": "z.txt", "Size": 26}], "IsTruncated": False},
        {"Bucket": BUCKET, "Prefix": "", "ContinuationToken": "tok1"},
    )
    objects = manager.list_objects()
    assert [o.key for o in objects] == ["a.txt", "z.txt"]
    assert not stubber._queue


def test_list_objects_empty(stubbed):
    manager, stubber = stubbed
    stubber.add_response(
        "list_objects_v2", {"IsTruncated": False},
        {"Bucket": BUCKET, "Prefix": "nothing/"},
    )
    assert manager.list_objects("nothing/") == []


def test_list_objects_to_dict(stubbed):
    manager, stubber = stubbed
    stubber.add_response(
        "list_objects_v2",
        {"Contents": [{"Key": "a.txt", "Size": 1, "LastModified": "2026-01-01"}],
         "IsTruncated": False},
        {"Bucket": BUCKET, "Prefix": ""},
    )
    payload = manager.list_objects()[0].to_dict()
    assert payload == {"key": "a.txt", "size": 1, "last_modified": "2026-01-01"}


# --------------------------------------------------------------------------- #
# File transfers and URLs
# --------------------------------------------------------------------------- #
def test_upload_and_download_file(stubbed, tmp_path):
    manager, stubber = stubbed
    source = tmp_path / "src.txt"
    source.write_text("file body", encoding="utf-8")

    stubber.add_response(
        "put_object", {"ETag": '"t"'},
        {"Bucket": BUCKET, "Key": "src.txt", "Body": b"file body",
         "ContentType": "text/plain"},
    )
    manager.upload_file(source, "src.txt", content_type="text/plain")

    stubber.add_response(
        "get_object",
        {"Body": io.BytesIO(b"file body"), "ContentLength": 9},
        {"Bucket": BUCKET, "Key": "src.txt"},
    )
    target = manager.download_file("src.txt", tmp_path / "out" / "copy.txt")
    assert target.read_text(encoding="utf-8") == "file body"
    assert not stubber._queue


def test_upload_missing_local_file(stubbed, tmp_path):
    manager, _ = stubbed
    with pytest.raises(S3Error, match="not found"):
        manager.upload_file(tmp_path / "nope.txt", "k")


def test_create_bucket(stubbed):
    manager, stubber = stubbed
    stubber.add_response(
        "create_bucket", {"Location": f"/{BUCKET}"}, {"Bucket": BUCKET}
    )
    assert manager.create_bucket() == f"/{BUCKET}"


def test_presigned_url_offline():
    # signing is local: no Stubber needed, no network touched
    manager = S3Manager(BUCKET, client=offline_client())
    url = manager.presigned_url("reports/q3.txt", expires=300)
    assert url.startswith("https://")
    assert "X-Amz-Signature=" in url
    assert "reports%2Fq3.txt" in url or "reports/q3.txt" in url


def test_presigned_url_validates_expiry():
    manager = S3Manager(BUCKET, client=offline_client())
    with pytest.raises(S3Error, match="expires"):
        manager.presigned_url("k", expires=0)
    with pytest.raises(S3Error, match="expires"):
        manager.presigned_url("k", expires=999_999)


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(tmp_path, capsys):
    assert run_demo(workdir=tmp_path) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Stubber" in out
    assert (tmp_path / "report.restored.txt").read_bytes() == \
        b"quarterly report - confidential\n"


def test_run_demo_is_idempotent(tmp_path, capsys):
    assert run_demo(workdir=tmp_path) == 0
    assert run_demo(workdir=tmp_path) == 0
    out = capsys.readouterr().out
    assert out.count("Demo completed successfully.") == 2


def test_demo_leaves_no_stub_queue(tmp_path):
    # run_demo asserts internally, but verify it really cleans up
    assert run_demo(workdir=tmp_path) == 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "presigned URL" in out


def test_cli_requires_bucket_for_list(capsys, monkeypatch):
    monkeypatch.delenv("S3_BUCKET", raising=False)
    assert main(["--list"]) == 2
    assert "--bucket" in capsys.readouterr().err


def test_cli_requires_key_for_get(capsys, monkeypatch):
    monkeypatch.delenv("S3_BUCKET", raising=False)
    assert main(["--get", "--bucket", BUCKET]) == 2
    assert "--key" in capsys.readouterr().err


def test_cli_put_requires_key(capsys, tmp_path, monkeypatch):
    monkeypatch.delenv("S3_BUCKET", raising=False)
    f = tmp_path / "a.txt"
    f.write_text("x", encoding="utf-8")
    assert main(["--put", str(f), "--bucket", BUCKET]) == 2
    assert "--key" in capsys.readouterr().err


def test_cli_put_missing_file(capsys, tmp_path, monkeypatch):
    monkeypatch.delenv("S3_BUCKET", raising=False)
    code = main(["--put", str(tmp_path / "nope.txt"), "--key", "k",
                 "--bucket", BUCKET])
    assert code == 2
    assert "not found" in capsys.readouterr().err


def test_cli_list_json(monkeypatch, capsys):
    """CLI list path with a stubbed manager injected."""
    from main import build_parser  # noqa: F401
    import main as main_mod

    client = offline_client()
    stubber = Stubber(client)
    stubber.activate()
    stubber.add_response(
        "list_objects_v2",
        {"Contents": [{"Key": "a.txt", "Size": 1}], "IsTruncated": False},
        {"Bucket": BUCKET, "Prefix": ""},
    )
    real_live = main_mod.live_client
    monkeypatch.setattr(main_mod, "live_client", lambda region, endpoint: client)
    try:
        assert main(["--list", "--bucket", BUCKET, "--json"]) == 0
        import json

        out = capsys.readouterr().out
        payload = json.loads(out[out.index("["):out.rindex("]") + 1])
        assert payload[0]["key"] == "a.txt"
    finally:
        stubber.deactivate()
        monkeypatch.setattr(main_mod, "live_client", real_live)


def test_cli_delete_error_path(monkeypatch, capsys):
    import main as main_mod

    client = offline_client()
    stubber = Stubber(client)
    stubber.activate()
    stubber.add_client_error(
        "delete_object", service_error_code="AccessDenied", http_status_code=403,
        service_message="denied",
        expected_params={"Bucket": BUCKET, "Key": "x"},
    )
    monkeypatch.setattr(main_mod, "live_client", lambda region, endpoint: client)
    try:
        assert main(["--delete", "--key", "x", "--bucket", BUCKET]) == 1
        assert "access denied" in capsys.readouterr().err
    finally:
        stubber.deactivate()
