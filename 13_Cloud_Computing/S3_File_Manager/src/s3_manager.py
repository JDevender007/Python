"""S3 file management with boto3 — wrapped for clean errors and offline tests.

The manager accepts any boto3 S3 client, so tests and the demo drive it with
botocore's ``Stubber``: every API interaction (create bucket, put, get, list,
head, delete) is scripted in-process with **no network, no AWS account, and
no credentials**. Point it at a real client for actual S3/MinIO/R2 usage.

Only operate on buckets you own or are authorized to manage.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

LOG = logging.getLogger("s3.manager")

DEFAULT_REGION = "us-east-1"
BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]{1,61}[a-z0-9]$")

# Fake credentials for the offline stubbed client: never used on the wire.
DEMO_CREDS = {"aws_access_key_id": "DEMO", "aws_secret_access_key": "DEMO"}


class S3Error(RuntimeError):
    """Raised for validation problems and wrapped AWS errors."""


@dataclass
class S3Object:
    """One object summary from a listing."""

    key: str
    size: int
    last_modified: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "size": self.size, "last_modified": self.last_modified}


# --------------------------------------------------------------------------- #
# Client factories
# --------------------------------------------------------------------------- #
def offline_client(region: str = DEFAULT_REGION) -> BaseClient:
    """Build an S3 client that needs no credential chain (for Stubber use)."""
    return boto3.client(
        "s3",
        region_name=region,
        config=Config(signature_version="s3v4"),
        endpoint_url=None,
        **DEMO_CREDS,
    )


def live_client(region: str = DEFAULT_REGION, endpoint_url: str | None = None) -> BaseClient:
    """Build an S3 client using the normal AWS credential chain."""
    return boto3.client("s3", region_name=region, endpoint_url=endpoint_url)


# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #
def validate_bucket(name: str) -> str:
    """Validate S3 bucket naming rules (simplified) and return the name."""
    if not isinstance(name, str) or not BUCKET_RE.match(name):
        raise S3Error(
            f"invalid bucket name: {name!r} "
            "(3-63 chars, lowercase letters/digits/dots/dashes, must start and end alphanumeric)"
        )
    return name


def validate_key(key: str) -> str:
    """Validate an object key."""
    if not isinstance(key, str) or not key or key.startswith("/"):
        raise S3Error(f"invalid object key: {key!r} (non-empty, no leading '/')")
    return key


def _friendly_error(action: str, exc: Exception) -> S3Error:
    """Turn a botocore exception into a readable S3Error."""
    if isinstance(exc, ClientError):
        error = exc.response.get("Error", {})
        code = error.get("Code", "?")
        message = error.get("Message", str(exc))
        if code in ("404", "NoSuchKey", "NotFound"):
            return S3Error(f"{action}: object or bucket not found")
        if code in ("NoSuchBucket",):
            return S3Error(f"{action}: bucket not found")
        if code in ("AccessDenied", "403"):
            return S3Error(f"{action}: access denied (check credentials/policy)")
        return S3Error(f"{action}: {code} - {message}")
    if isinstance(exc, BotoCoreError):
        return S3Error(f"{action}: {exc}")
    return S3Error(f"{action}: {exc}")


# --------------------------------------------------------------------------- #
# Manager
# --------------------------------------------------------------------------- #
class S3Manager:
    """Small, explicit wrapper around a boto3 S3 client."""

    def __init__(
        self,
        bucket: str,
        client: BaseClient | None = None,
        region: str = DEFAULT_REGION,
        endpoint_url: str | None = None,
    ) -> None:
        self.bucket = validate_bucket(bucket)
        self.region = region
        self.client = client if client is not None else live_client(region, endpoint_url)

    # --- bucket --------------------------------------------------------- #
    def create_bucket(self) -> str:
        """Create the managed bucket and return its name."""
        params: dict[str, Any] = {"Bucket": self.bucket}
        if self.region != "us-east-1":
            params["CreateBucketConfiguration"] = {"LocationConstraint": self.region}
        try:
            response = self.client.create_bucket(**params)
        except (ClientError, BotoCoreError) as exc:
            raise _friendly_error(f"create_bucket {self.bucket}", exc) from exc
        LOG.info("created bucket %s", self.bucket)
        return response.get("Location", f"/{self.bucket}")

    # --- objects -------------------------------------------------------- #
    def put_bytes(
        self, key: str, data: bytes, content_type: str | None = None
    ) -> str:
        """Upload bytes and return the ETag (without quotes)."""
        key = validate_key(key)
        if not isinstance(data, (bytes, bytearray)):
            raise S3Error("data must be bytes")
        params: dict[str, Any] = {"Bucket": self.bucket, "Key": key, "Body": bytes(data)}
        if content_type:
            params["ContentType"] = content_type
        try:
            response = self.client.put_object(**params)
        except (ClientError, BotoCoreError) as exc:
            raise _friendly_error(f"put {key}", exc) from exc
        etag = response.get("ETag", "").strip('"')
        LOG.info("put %s (%s bytes, etag=%s)", key, len(data), etag)
        return etag

    def get_bytes(self, key: str) -> bytes:
        """Download an object and return its bytes."""
        key = validate_key(key)
        body = None
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            body = response["Body"]
            data = body.read()
        except (ClientError, BotoCoreError) as exc:
            raise _friendly_error(f"get {key}", exc) from exc
        finally:
            if body is not None:
                try:
                    body.close()
                except Exception:  # noqa: BLE001 - best-effort stream close
                    pass
        LOG.info("got %s (%s bytes)", key, len(data))
        return data

    def exists(self, key: str) -> bool:
        """True when the object exists; False on 404, S3Error otherwise."""
        key = validate_key(key)
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                return False
            raise _friendly_error(f"head {key}", exc) from exc
        except BotoCoreError as exc:
            raise _friendly_error(f"head {key}", exc) from exc

    def delete(self, key: str) -> None:
        """Delete an object (S3 delete is idempotent)."""
        key = validate_key(key)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except (ClientError, BotoCoreError) as exc:
            raise _friendly_error(f"delete {key}", exc) from exc
        LOG.info("deleted %s", key)

    def list_objects(self, prefix: str = "") -> list[S3Object]:
        """List objects under a prefix, following pagination, sorted by key."""
        items: list[S3Object] = []
        token: str | None = None
        try:
            while True:
                params: dict[str, Any] = {"Bucket": self.bucket, "Prefix": prefix}
                if token:
                    params["ContinuationToken"] = token
                response = self.client.list_objects_v2(**params)
                for entry in response.get("Contents", []):
                    items.append(
                        S3Object(
                            key=entry["Key"],
                            size=int(entry.get("Size", 0)),
                            last_modified=str(entry.get("LastModified", "")),
                        )
                    )
                if not response.get("IsTruncated"):
                    break
                token = response.get("NextContinuationToken")
                if not token:
                    break
        except (ClientError, BotoCoreError) as exc:
            raise _friendly_error(f"list s3://{self.bucket}/{prefix}", exc) from exc
        return sorted(items, key=lambda obj: obj.key)

    # --- files ---------------------------------------------------------- #
    def upload_file(self, path: str | Path, key: str, content_type: str | None = None) -> str:
        """Upload a local file; returns the ETag."""
        source = Path(path)
        if not source.is_file():
            raise S3Error(f"local file not found: {source}")
        return self.put_bytes(key, source.read_bytes(), content_type=content_type)

    def download_file(self, key: str, path: str | Path) -> Path:
        """Download an object to a local file; returns the local path."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.get_bytes(key))
        return target

    # --- urls ----------------------------------------------------------- #
    def presigned_url(self, key: str, expires: int = 3600) -> str:
        """Generate a presigned GET URL (local signing, no network call)."""
        key = validate_key(key)
        if not 1 <= expires <= 604_800:
            raise S3Error("expires must be between 1 and 604800 seconds")
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires,
            )
        except (ClientError, BotoCoreError) as exc:
            raise _friendly_error(f"presign {key}", exc) from exc


# --------------------------------------------------------------------------- #
# Offline demo (botocore Stubber - no network)
# --------------------------------------------------------------------------- #
def run_demo(workdir: Path | None = None) -> int:
    """Script a complete bucket lifecycle against a stubbed S3 client."""
    from botocore.stub import Stubber

    print("=" * 60)
    print(" S3 FILE MANAGER - offline demo (botocore Stubber)")
    print(" No network, no AWS account, no credentials required.")
    print("=" * 60)

    directory = workdir or Path(__file__).resolve().parent.parent / "data"
    directory.mkdir(parents=True, exist_ok=True)

    bucket = "demo-bucket-offline"
    client = offline_client()
    stubber = Stubber(client)
    stubber.activate()

    report = b"quarterly report - confidential\n"
    notes = b"id,name\n1,alice\n2,bob\n"

    # Script the whole lifecycle in call order.
    stubber.add_response(
        "create_bucket", {"Location": f"/{bucket}"}, {"Bucket": bucket}
    )
    stubber.add_response(
        "put_object",
        {"ETag": '"11111111111111111111111111111111"'},
        {"Bucket": bucket, "Key": "reports/q3.txt", "Body": report,
         "ContentType": "text/plain"},
    )
    stubber.add_response(
        "put_object",
        {"ETag": '"22222222222222222222222222222222"'},
        {"Bucket": bucket, "Key": "data/notes.csv", "Body": notes,
         "ContentType": "text/csv"},
    )
    stubber.add_response(
        "list_objects_v2",
        {
            "Contents": [
                {"Key": "reports/q3.txt", "Size": len(report)},
                {"Key": "data/notes.csv", "Size": len(notes)},
            ],
            "IsTruncated": False,
        },
        {"Bucket": bucket, "Prefix": ""},
    )
    stubber.add_response(
        "head_object", {"ContentLength": len(report)},
        {"Bucket": bucket, "Key": "reports/q3.txt"},
    )
    stubber.add_client_error(
        "head_object", service_error_code="404", http_status_code=404,
        service_message="Not Found",
        expected_params={"Bucket": bucket, "Key": "ghost.txt"},
    )
    stubber.add_response(
        "get_object",
        {"Body": io.BytesIO(report), "ContentLength": len(report)},
        {"Bucket": bucket, "Key": "reports/q3.txt"},
    )
    stubber.add_response(
        "get_object",
        {"Body": io.BytesIO(report), "ContentLength": len(report)},
        {"Bucket": bucket, "Key": "reports/q3.txt"},
    )
    stubber.add_response(
        "list_objects_v2",
        {"Contents": [{"Key": "data/notes.csv", "Size": len(notes)}],
         "IsTruncated": False},
        {"Bucket": bucket, "Prefix": "data/"},
    )
    stubber.add_response("delete_object", {}, {"Bucket": bucket, "Key": "reports/q3.txt"})
    stubber.add_response(
        "list_objects_v2",
        {"Contents": [{"Key": "data/notes.csv", "Size": len(notes)}],
         "IsTruncated": False},
        {"Bucket": bucket, "Prefix": ""},
    )

    manager = S3Manager(bucket, client=client)

    print(f"\n[1] create_bucket  -> {manager.create_bucket()}")
    etag1 = manager.put_bytes("reports/q3.txt", report, content_type="text/plain")
    etag2 = manager.put_bytes("data/notes.csv", notes, content_type="text/csv")
    print(f"[2] put 2 objects  -> etags {etag1[:8]}..., {etag2[:8]}...")

    listing = manager.list_objects()
    total = sum(obj.size for obj in listing)
    print(f"[3] list           -> {len(listing)} objects, {total} bytes")
    for obj in listing:
        print(f"       {obj.key}  ({obj.size} bytes)")

    print(f"[4] exists report  -> {manager.exists('reports/q3.txt')}")
    print(f"[5] exists ghost   -> {manager.exists('ghost.txt')} (404 handled)")

    fetched = manager.get_bytes("reports/q3.txt")
    print(f"[6] get_bytes      -> {len(fetched)} bytes, match={fetched == report}")

    restored = manager.download_file("reports/q3.txt", directory / "report.restored.txt")
    print(f"[7] download_file  -> {restored.name} "
          f"(identical={restored.read_bytes() == report})")

    print(f"[8] list prefix 'data/' -> {[o.key for o in manager.list_objects('data/')]}")

    url = manager.presigned_url("reports/q3.txt", expires=300)
    short = url.split("?")[0]
    print(f"[9] presigned URL  -> {short}?X-Amz-Signature=... "
          f"(signed locally, {len(url)} chars)")

    manager.delete("reports/q3.txt")
    remaining = [o.key for o in manager.list_objects()]
    print(f"[10] delete + list  -> remaining {remaining}")

    # verify the stub queue was fully consumed (every call was scripted)
    assert not stubber._queue, f"unused stub responses: {stubber._queue}"
    stubber.deactivate()

    print("\nDemo completed successfully.")
    return 0
