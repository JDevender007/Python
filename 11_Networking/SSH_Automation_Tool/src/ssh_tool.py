"""SSH command execution, file transfer, and an offline demo backend.

``SSHSession`` wraps paramiko for real connections, but accepts any backend
exposing the same ``run`` / ``put`` / ``get`` / ``close`` surface — including
the in-memory ``LocalShell`` used by the demo and the test suite, so the
project runs with no network at all.

Only connect to machines you own or have explicit authorization to manage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import paramiko

LOG = logging.getLogger("ssh.tool")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 22


class SSHError(RuntimeError):
    """Raised for connection, authentication and transfer problems."""


@dataclass
class CommandResult:
    """Outcome of one remote command."""

    command: str
    exit_status: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_status == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "exit_status": self.exit_status,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


# --------------------------------------------------------------------------- #
# Offline backend
# --------------------------------------------------------------------------- #
class LocalShell:
    """An in-memory stand-in for a remote shell.

    Implements a small, predictable command set against a dict-backed
    filesystem so the demo and tests can exercise the exact call pattern of a
    real session without binding a port or needing credentials.
    """

    def __init__(self, user: str = "demo", cwd: str = "/home/demo") -> None:
        self.user = user
        self.cwd = cwd
        self.dirs: set[bytes] = {cwd.encode()}
        self.fs: dict[str, bytes] = {}  # file path -> content
        self.closed = False

    # --- helpers -------------------------------------------------------- #
    def _is_dir(self, path: str) -> bool:
        return path.encode() in self.dirs

    def _resolve(self, path: str) -> str:
        if not path.startswith("/"):
            path = f"{self.cwd.rstrip('/')}/{path}"
        parts: list[str] = []
        for chunk in path.split("/"):
            if chunk in ("", "."):
                continue
            if chunk == "..":
                if parts:
                    parts.pop()
                continue
            parts.append(chunk)
        return "/" + "/".join(parts)

    # --- backend surface ------------------------------------------------ #
    def run(self, command: str) -> CommandResult:
        """Execute a tiny subset of shell commands."""
        command = command.strip()
        LOG.info("local run: %s", command)

        if command.startswith("echo "):
            return CommandResult(command, 0, command[5:] + "\n", "")
        if command == "echo":
            return CommandResult(command, 0, "\n", "")
        if command == "pwd":
            return CommandResult(command, 0, self.cwd + "\n", "")
        if command == "whoami":
            return CommandResult(command, 0, self.user + "\n", "")
        if command.startswith("uname"):
            return CommandResult(command, 0, "LocalShell 1.0 offline-demo x86_64\n", "")
        if command in ("true",):
            return CommandResult(command, 0, "", "")
        if command in ("false",):
            return CommandResult(command, 1, "", "")

        if command.startswith("cat "):
            path = self._resolve(command[4:].strip())
            data = self.fs.get(path)
            if data is None:
                return CommandResult(command, 1, "", f"cat: {path}: No such file\n")
            return CommandResult(command, 0, data.decode("utf-8", errors="replace"), "")

        if command.startswith("ls"):
            arg = command[2:].strip() or self.cwd
            path = self._resolve(arg)
            if not self._is_dir(path):
                return CommandResult(command, 2, "", f"ls: {path}: No such directory\n")
            prefix = path.rstrip("/")
            names = set()
            for key in list(self.fs) + [d.decode() for d in self.dirs]:
                if key == prefix or not key.startswith(prefix + "/"):
                    continue
                names.add(key[len(prefix) + 1:].split("/", 1)[0])
            return CommandResult(command, 0, "".join(n + "\n" for n in sorted(names)), "")

        return CommandResult(command, 127, "", f"{command.split()[0]}: command not found\n")

    def put(self, local: str | Path, remote: str) -> int:
        """Copy a local file into the in-memory filesystem."""
        source = Path(local)
        if not source.is_file():
            raise SSHError(f"local file not found: {source}")
        target = self._resolve(remote)
        # register every ancestor as a directory
        parent = target.rsplit("/", 1)[0] or "/"
        chunks = [c for c in parent.split("/") if c]
        for depth in range(len(chunks) + 1):
            self.dirs.add(("/" + "/".join(chunks[:depth])).encode())
        data = source.read_bytes()
        self.fs[target] = data
        return len(data)

    def get(self, remote: str, local: str | Path) -> Path:
        """Copy a file out of the in-memory filesystem."""
        source = self._resolve(remote)
        if source not in self.fs:
            raise SSHError(f"remote file not found: {source}")
        target = Path(local)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.fs[source])
        return target

    def close(self) -> None:
        self.closed = True


# --------------------------------------------------------------------------- #
# Paramiko-backed transport
# --------------------------------------------------------------------------- #
class ParamikoBackend:
    """Thin adapter giving paramiko the LocalShell surface."""

    def __init__(self, client: paramiko.SSHClient) -> None:
        self._client = client
        self._sftp: paramiko.SFTPClient | None = None

    def _sftp_client(self) -> paramiko.SFTPClient:
        if self._sftp is None:
            self._sftp = self._client.open_sftp()
        return self._sftp

    def run(self, command: str) -> CommandResult:
        LOG.info("remote run: %s", command)
        stdin, stdout, stderr = self._client.exec_command(command, timeout=30)
        stdin.close()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        status = stdout.channel.recv_exit_status()
        return CommandResult(command, status, out, err)

    def put(self, local: str | Path, remote: str) -> int:
        source = Path(local)
        if not source.is_file():
            raise SSHError(f"local file not found: {source}")
        self._sftp_client().put(str(source), remote)
        return source.stat().st_size

    def get(self, remote: str, local: str | Path) -> Path:
        target = Path(local)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._sftp_client().get(remote, str(target))
        except (IOError, OSError, paramiko.SFTPError) as exc:
            raise SSHError(f"download failed: {exc}") from exc
        return target

    def close(self) -> None:
        if self._sftp is not None:
            try:
                self._sftp.close()
            except Exception:  # noqa: BLE001 - best-effort teardown
                pass
            self._sftp = None
        try:
            self._client.close()
        except Exception:  # noqa: BLE001 - best-effort teardown
            pass


# --------------------------------------------------------------------------- #
# Session
# --------------------------------------------------------------------------- #
class SSHSession:
    """High-level session used by the CLI and the tests."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        username: str = "demo",
        password: str | None = None,
        key_path: str | Path | None = None,
        timeout: float = 10.0,
        backend: Any | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_path = Path(key_path) if key_path else None
        self.timeout = timeout
        self._backend = backend

    @property
    def connected(self) -> bool:
        return self._backend is not None

    def connect(self) -> None:
        """Open the SSH connection (no-op when a backend is injected)."""
        if self._backend is not None:
            return
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            connect_kwargs: dict[str, Any] = {
                "hostname": self.host,
                "port": self.port,
                "username": self.username,
                "timeout": self.timeout,
                "allow_agent": False,
                "look_for_keys": False,
            }
            if self.key_path is not None:
                connect_kwargs["key_filename"] = str(self.key_path)
            elif self.password is not None:
                connect_kwargs["password"] = self.password
            client.connect(**connect_kwargs)
        except (paramiko.SSHException, OSError, EOFError) as exc:
            try:
                client.close()
            except Exception:  # noqa: BLE001 - best-effort teardown
                pass
            raise SSHError(
                f"could not connect to {self.username}@{self.host}:{self.port} - {exc}"
            ) from exc
        self._backend = ParamikoBackend(client)
        LOG.info("connected to %s@%s:%s", self.username, self.host, self.port)

    def _require(self) -> Any:
        if self._backend is None:
            raise SSHError("not connected")
        return self._backend

    def run(self, command: str) -> CommandResult:
        """Run one command and return its result."""
        return self._require().run(command)

    def run_all(self, commands: list[str]) -> list[CommandResult]:
        """Run several commands in order."""
        return [self.run(cmd) for cmd in commands]

    def upload(self, local: str | Path, remote: str) -> int:
        """Upload a file over SFTP, returning the byte count."""
        sent = self._require().put(local, remote)
        LOG.info("uploaded %s -> %s (%s bytes)", local, remote, sent)
        return sent

    def download(self, remote: str, local: str | Path) -> Path:
        """Download a file over SFTP, returning the local path."""
        path = self._require().get(remote, local)
        LOG.info("downloaded %s -> %s", remote, path)
        return path

    def close(self) -> None:
        """Close the session (idempotent)."""
        if self._backend is None:
            return
        try:
            self._backend.close()
        finally:
            self._backend = None

    def __enter__(self) -> "SSHSession":
        self.connect()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
def run_demo(workdir: Path | None = None) -> int:
    """Exercise command execution and file transfer against LocalShell."""
    directory = workdir or Path(__file__).resolve().parent.parent / "data"
    directory.mkdir(parents=True, exist_ok=True)

    print("Opening offline SSH session (in-memory LocalShell)...")
    session = SSHSession(host="offline", username="demo", backend=LocalShell())
    session.connect()
    print(f"  connected={session.connected}")

    print("\n== Commands ==")
    for command in ("whoami", "pwd", "uname -a", 'echo "hello from the ssh demo"'):
        result = session.run(command)
        print(f"  $ {command}")
        print(f"    -> exit={result.exit_status} out={result.stdout.strip()!r}")

    local = directory / "hello.txt"
    local.write_text("payload for the ssh demo\n", encoding="utf-8")
    sent = session.upload(local, "/home/demo/hello.txt")
    print(f"\nUploaded hello.txt ({sent} bytes)")

    listing = session.run("ls /home/demo")
    print("Remote listing:", listing.stdout.split())

    remote_view = session.run("cat /home/demo/hello.txt")
    print("Remote content:", remote_view.stdout.strip())

    restored = session.download("/home/demo/hello.txt", directory / "restored.txt")
    identical = restored.read_text(encoding="utf-8") == local.read_text(encoding="utf-8")
    print(f"Downloaded -> {restored.name}; identical={identical}")
    assert identical

    failing = session.run("definitely_not_a_command")
    print(f"Unknown command handled: exit={failing.exit_status}, "
          f"stderr={failing.stderr.strip()!r}")

    session.close()
    print(f"\nSession closed; connected={session.connected}")
    print("Demo completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_demo())
