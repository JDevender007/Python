# S3 File Manager

An S3 listing is a page, an ETag is not an MD5, and a presigned URL is local. The legacy manager is
three calls that look exactly like the documentation:

```python
listing = client.list_objects_v2(Bucket=bucket, Prefix="logs/")
assert etag == hashlib.md5(body).hexdigest()
url = f"s3://{bucket}/{key}?X-Amz-Expires=3600"
```

**1. A prefix query without a delimiter is a string match, not a folder.** Every key that starts
with `logs/` matches, including `logs/api/2024-01.log` and the zero-byte folder marker `logs/`
itself. The console shows two folders because it passes `Delimiter="/"` and reads
`CommonPrefixes`; the legacy call matches **4 keys**, returns no prefixes, and because it stops at
the first page of 3 it shows only **3**. A prefix is a filter; the delimiter is what turns it into
a directory.

**2. An ETag is not an MD5.** A single PUT has a plain 32-hex MD5 ETag. A multipart upload has
`md5(concat(part md5s))-<partcount>`, and an SSE-KMS object has an ETag that is not a digest of the
body at all. The check `etag == md5(body)` therefore calls all **3** multipart objects and the
**1** KMS object corrupt: **4 of 9 failed**, and not one of them is damaged. The rebuild
reassembles the parts, recomputes the multipart digest, and separates **verified**, **corrupt** and
**opaque**: **8 verified, 0 corrupt, 1 opaque**.

**3. A listing is paginated, and `IsTruncated` is the only signal.** Nine objects at three per page
take **3 pages**. A loop that never reads `IsTruncated`, or that continues while a token exists,
either stops early or never stops; the token is opaque, and its absence on the last page is the only
reliable end.

**4. A presigned URL is signed locally and proves nothing about existence.** The key is
percent-encoded into the canonical request, so `q3 final.txt` becomes `q3%20final.txt` and the
signature covers the encoded path. Interpolating the raw key produces a URL with a space in it, and
pinning `X-Amz-Expires=3600` ignores the caller's `expires=300`. Signing never checks the bucket: a
URL for a key that does not exist is generated happily and fails only when it is used.

The bucket is a bundled JSON manifest -- no boto3, no credentials, no network, no stubbing library.
Each object carries the ETag the bucket reports, so the digest check has something real to disagree
with.

## What this project teaches

- Why `Prefix` filters while `Delimiter` groups, and why the console shows folders
- Why the zero-byte folder marker is an object with the prefix itself as its key
- Why a first page is not a listing: `IsTruncated` and the continuation token
- Why a multipart ETag is a digest of digests plus a part count
- Why an SSE-KMS ETag cannot be verified from the body, and why "opaque" is not "corrupt"
- Why comparing every ETag to the body MD5 produces four false alarms in nine objects
- Why a presigned URL percent-encodes the key inside the signed canonical request
- Why the expiry is part of the signature, not a decoration on the query string
- Why signing is a local operation that never proves the object exists
- Why a manifest with declared ETags is a better lab fixture than a stubbed client
- How to page a combined stream of objects and common prefixes
- How to audit a listing and a digest check by rebuilding both from the manifest

## How to run

```
python src/main.py --demo
python src/main.py --demo --quiet
python src/main.py --file data/bucket.json --json out.json
python src/main.py --prefix logs/ --delimiter / --page-size 3
python src/main.py --expires 60 --audit
python -m pytest tests -q
```

`--file` names a bucket manifest: a bucket name and a list of `{key, body, upload, part_count,
etag}` objects. `--prefix` and `--delimiter` select the folder view; an empty `--delimiter` means
no grouping. `--audit` exits `1` if any check fails. Exit code `2` means the input was refused -- a
missing file, non-ASCII bytes, invalid JSON, a root that is not a mapping, a bad bucket name, a
duplicate or leading-slash key, an unknown upload mode, a part count outside its range, or an ETag
that is not 32 hex characters with an optional `-partcount` suffix.

## Project structure

```
S3_File_Manager/
├── README.md
├── requirements.txt        # pytest==9.1.1
├── .gitignore
├── data/
│   └── bucket.json         # 9 objects: 5 single, 3 multipart, 1 KMS
├── src/
│   ├── s3_manager.py       # listing, ETags, presigning, audit, demo
│   └── main.py             # argparse only
└── tests/
    └── test_s3_manager.py  # 149 tests
```

## What the demo shows

| view | value |
| --- | --- |
| objects / bytes | 9 / 308 |
| keys matching `logs/` | 4 (the marker plus three nested keys) |
| legacy first page under `logs/` | 3, no delimiter |
| delimiter view | 2 prefixes (`logs/api/`, `logs/web/`) |
| folder marker | `logs/` is an object, not a child |
| legacy ETag check | 5 verified, **4 called corrupt** |
| rebuild ETag check | **8 verified, 0 corrupt, 1 opaque** |
| full listing | 9 objects over **3 pages**, `IsTruncated=false` |

- `data/notes.csv` → `e56cf7fc…-2`, `logs/api/2024-02.log` → `bccf4c49…-3`,
  `reports/q4.txt` → `4fef5040…-2`: each multipart ETag differs from the body MD5
- `secrets/keys.json` carries an opaque ETag: neither verified nor corrupt, on purpose
- Presigned: `reports/q3%20final.txt` with `X-Amz-Expires=300`; legacy:
  `reports/q3 final.txt` with `X-Amz-Expires=3600`
- A presigned URL for `reports/absent.txt` is signed too -- signing does not check existence
- **16/16 audit checks pass**, including one that rebuilds the listing from the manifest

## Requirements

Python 3.10+, standard library only (`json`, `hashlib`, `dataclasses`, `argparse`,
`urllib.parse`). Tests need pytest==9.1.1. No boto3, no botocore, no credentials, no network; the
bucket is a bundled JSON manifest.

---
**Devender J** -- https://github.com/JDevender007
