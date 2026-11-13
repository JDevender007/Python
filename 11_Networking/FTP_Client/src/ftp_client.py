"""FTP client wrapper built on the standard library ``ftplib``.

The client ships with an offline demo server (a tiny in-process FTP-ish
transfer harness) so the project can be exercised without any network.
For real transfers, point it at an FTP server you control.
"""

from __future__ import annotations

import ftplib
import logging
from dataclasses import dataclass
from pathlib import Path

LOG = logging.getLogger("ftp.client")

DEFAULT_HOST = "127.0.0.1"


@dataclass
class RemoteEntry:
    """One parsed directory entry."""

    name: str
    size: int
    is_dir: bool

    def __str__(self) -> str:
        kind = "d" if self.is_dir else "-"
        return f"{kind} {self.size:>10}  {self.name}"


class FTPError(RuntimeError):
    """Raised for connection and transfer problems."""


class FTPClient:
    """Small, explicit wrapper around ftplib.FTP."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = 21,
                 timeout: float = 10.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._ftp: ftplib.FTP | None = None

    # ------------------------------------------------------------------ #
    @property
    def connected(self) -> bool:
        return self._ftp is not None

    def connect(self, user: str = "anonymous", password: str = "anonymous@") -> str:
        """Log in and return the server welcome banner."""
        ftp = ftplib.FTP()
        try:
            banner = ftp.connect(self.host, self.port, timeout=self.timeout)
            ftp.login(user, password)
        except (OSError, EOFError, ftplib.Error, ValueError) as exc:
            raise FTPError(f"could not connect to {self.host}:{self.port} - {exc}") from exc
        self._ftp = ftp
        LOG.info("connected to %s:%s", self.host, self.port)
        return banner

    def close(self) -> None:
        """Quit cleanly if connected."""
        if self._ftp is None:
            return
        try:
            self._ftp.quit()
        except (OSError, EOFError, ftplib.Error):
            try:
                self._ftp.close()
            except Exception:  # noqa: BLE001 - best-effort teardown
                pass
        self._ftp = None

    def _require(self) -> ftplib.FTP:
        if self._ftp is None:
            raise FTPError("not connected")
        return self._ftp

    # ------------------------------------------------------------------ #
    def list(self, path: str = "") -> list[RemoteEntry]:
        """List a remote directory as parsed entries."""
        ftp = self._require()
        entries: list[RemoteEntry] = []
        try:
            lines: list[str] = []
            ftp.retrlines(f"NLST {path}" if path else "NLST", lines.append)
        except ftplib.error_perm as exc:
            raise FTPError(f"list failed: {exc}") from exc

        for name in lines:
            clean = name.rstrip("/")
            size = 0
            is_dir = name.endswith("/")
            if not is_dir:
                try:
                    size = ftp.size(clean) or 0
                except (OSError, ftplib.Error):
                    size = 0
            entries.append(RemoteEntry(name=clean, size=size, is_dir=is_dir))
        return sorted(entries, key=lambda e: (not e.is_dir, e.name.lower()))

    def upload(self, local: str | Path, remote: str | None = None) -> int:
        """Upload a file and return the number of bytes sent."""
        ftp = self._require()
        source = Path(local)
        if not source.is_file():
            raise FTPError(f"local file not found: {source}")
        target = remote or source.name
        sent = 0
        try:
            with source.open("rb") as fh:
                sent = ftp.storbinary(f"STOR {target}", fh)
        except (OSError, EOFError, ftplib.Error) as exc:
            raise FTPError(f"upload failed: {exc}") from exc
        LOG.info("uploaded %s -> %s (%s bytes)", source, target, sent)
        return sent

    def download(self, remote: str, local: str | Path | None = None) -> Path:
        """Download a file and return the local path written."""
        ftp = self._require()
        target = Path(local) if local else Path(remote).name
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("wb") as fh:
                ftp.retrbinary(f"RETR {remote}", fh.write)
        except (OSError, EOFError, ftplib.Error) as exc:
            raise FTPError(f"download failed: {exc}") from exc
        LOG.info("downloaded %s -> %s", remote, target)
        return target

    def delete(self, remote: str) -> None:
        """Remove a remote file."""
        ftp = self._require()
        try:
            ftp.delete(remote)
        except (OSError, EOFError, ftplib.Error) as exc:
            raise FTPError(f"delete failed: {exc}") from exc

    def make_directory(self, path: str) -> None:
        """Create a remote directory."""
        ftp = self._require()
        try:
            ftp.mkd(path)
        except (OSError, EOFError, ftplib.Error) as exc:
            raise FTPError(f"mkdir failed: {exc}") from exc

    def rename(self, old: str, new: str) -> None:
        """Rename a remote file or directory."""
        ftp = self._require()
        try:
            ftp.rename(old, new)
        except (OSError, EOFError, ftplib.Error) as exc:
            raise FTPError(f"rename failed: {exc}") from exc

    def quit(self) -> None:
        """Alias for close(), kept for CLI symmetry."""
        self.close()


# --------------------------------------------------------------------------- #
# Offline demo backend
# --------------------------------------------------------------------------- #
class LocalFTP:
    """An in-memory stand-in that mimics the subset of FTP we use.

    It lets the demo and the tests exercise the exact same call pattern as a
    real server without binding a port or needing credentials.
    """

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.directories: set[str] = {""}
        self.banner = "220 LocalFTP ready (offline demo)"

    # --- ftplib-compatible surface -------------------------------------- #
    def connect(self, host: str, port: int, timeout: float = 10.0) -> str:
        return self.banner

    def login(self, user: str, password: str) -> str:
        return "230 logged in"

    def nlst(self, path: str = "") -> list[str]:
        prefix = path.strip("/")
        results: list[str] = []
        for name in self.files:
            if prefix and not name.startswith(prefix):
                continue
            results.append(name)
        for name in self.directories:
            if not name or name == prefix:
                continue
            if prefix and not name.startswith(prefix):
                continue
            results.append(name + "/")
        return sorted(results)

    def retrlines(self, cmd: str, callback) -> None:
        """Mimic ftplib's line-oriented retrieval for NLST-style commands."""
        parts = cmd.split(None, 1)
        path = parts[1] if len(parts) > 1 else ""
        for name in self.nlst(path):
            callback(name)

    def size(self, name: str) -> int | None:
        data = self.files.get(name)
        return len(data) if data is not None else None

    def storbinary(self, cmd: str, fh) -> int:
        _, _, name = cmd.partition(" ")
        data = fh.read()
        self.files[name] = data
        return len(data)

    def retrbinary(self, cmd: str, callback) -> None:
        _, _, name = cmd.partition(" ")
        if name not in self.files:
            raise ftplib.error_perm("550 no such file")
        callback(self.files[name])

    def delete(self, name: str) -> None:
        if name not in self.files:
            raise ftplib.error_perm("550 no such file")
        del self.files[name]

    def mkd(self, path: str) -> None:
        self.directories.add(path.strip("/"))

    def rename(self, old: str, new: str) -> None:
        if old not in self.files:
            raise ftplib.error_perm("550 no such file")
        self.files[new] = self.files.pop(old)

    def quit(self) -> str:
        return "221 bye"

    def close(self) -> None:
        pass


def run_demo(workdir: Path | None = None) -> int:
    """Exercise upload/download/list/delete against the in-memory backend."""
    directory = workdir or Path(__file__).resolve().parent.parent / "data"
    directory.mkdir(parents=True, exist_ok=True)

    print("Connecting to in-memory LocalFTP (offline demo)...")
    backend = LocalFTP()
    client = FTPClient.__new__(FTPClient)  # skip real socket connect
    client.host, client.port, client.timeout = "local", 0, 5.0
    client._ftp = backend  # type: ignore[assignment]
    print("  banner:", backend.connect("local", 0))
    print("  login :", backend.login("demo", "demo"))

    payload = directory / "upload_sample.txt"
    payload.write_text("hello from the FTP demo\n", encoding="utf-8")

    sent = client.upload(payload, "upload_sample.txt")
    print(f"\nUploaded {payload.name} ({sent} bytes)")

    entries = client.list()
    print("Remote listing:")
    for entry in entries:
        print("   ", entry)

    target = directory / "downloaded.txt"
    client.download("upload_sample.txt", target)
    print(f"\nDownloaded -> {target.name} ({target.stat().st_size} bytes)")
    assert target.read_text(encoding="utf-8") == payload.read_text(encoding="utf-8")
    print("Content verified identical.")

    client.make_directory("archive")
    client.rename("upload_sample.txt", "renamed.txt")
    print("Created dir 'archive', renamed file -> renamed.txt")

    client.delete("renamed.txt")
    print("Deleted renamed.txt")
    print("Remaining:", [e.name for e in client.list()])

    client.close()
    print("\nDemo completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_demo())
