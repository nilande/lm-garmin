"""Content-addressed build outputs with atomic publication."""

from __future__ import annotations

import fcntl
import hashlib
import json
import shutil
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from .tools import sha256_file

STAGES = ("convert", "extract", "split", "compile")


def key(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _stamp(path: Path) -> list[int]:
    status = path.stat()
    return [
        status.st_dev,
        status.st_ino,
        status.st_size,
        status.st_mtime_ns,
        status.st_ctime_ns,
    ]


@dataclass(frozen=True)
class Artifact:
    path: Path
    key: str
    record: dict
    cached: bool


class StageCache:
    def __init__(self, cache: Path):
        self.root = cache / "stages"

    @contextmanager
    def lease(self, *, exclusive: bool = False) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            yield

    def fingerprint(self, path: Path) -> str:
        """Reuse a content digest while the file's identity and metadata match."""
        path = path.resolve()
        stamp = _stamp(path)
        folder = self.root / "fingerprints"
        folder.mkdir(parents=True, exist_ok=True)
        record_file = folder / f"{key(str(path))}.json"
        try:
            data = json.loads(record_file.read_text())
            if data["stamp"] == stamp:
                return data["sha256"]
        except (OSError, ValueError, KeyError, TypeError):
            pass
        digest = sha256_file(path)
        if _stamp(path) != stamp:
            raise OSError(f"{path} changed while calculating its checksum")
        with NamedTemporaryFile(mode="w", dir=folder, delete=False) as tmp:
            temp = Path(tmp.name)
            try:
                json.dump({"stamp": stamp, "sha256": digest}, tmp)
                tmp.close()
                temp.replace(record_file)
            finally:
                temp.unlink(missing_ok=True)
        return digest

    def run(self, stage: str, inputs, produce: Callable[[Path], dict]) -> Artifact:
        cache_key = key([1, stage, inputs])
        parent = self.root / stage
        parent.mkdir(parents=True, exist_ok=True)
        target = parent / cache_key
        with (parent / f".{cache_key}.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            manifest = target / "cache.json"
            try:
                data = json.loads(manifest.read_text())
                if all((target / p).stat().st_size == size for p, size in data["files"].items()):
                    return Artifact(target, cache_key, data["record"], True)
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                pass
            with TemporaryDirectory(prefix=".build-", dir=parent) as tmp:
                staging = Path(tmp) / "output"
                staging.mkdir()
                record = produce(staging)
                files = {
                    p.relative_to(staging).as_posix(): p.stat().st_size
                    for p in staging.rglob("*")
                    if p.is_file()
                }
                (staging / "cache.json").write_text(json.dumps({"record": record, "files": files}))
                if target.exists():
                    shutil.rmtree(target)
                staging.rename(target)
                return Artifact(target, cache_key, record, False)

    def info(self) -> dict[str, dict[str, int]]:
        return {
            name: {
                "entries": sum(p.is_dir() and not p.name.startswith(".") for p in folder.iterdir()),
                "bytes": sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()),
            }
            for name in STAGES
            if (folder := self.root / name).is_dir()
        }

    def clean(self) -> None:
        with self.lease(exclusive=True):
            for name in (*STAGES, "fingerprints"):
                folder = self.root / name
                if folder.is_dir():
                    shutil.rmtree(folder)


def publish(source: Path, target: Path) -> None:
    """Copy a complete artifact into place without exposing a partial map."""
    with NamedTemporaryFile(dir=target.parent, delete=False) as tmp:
        name = Path(tmp.name)
        try:
            with source.open("rb") as stream:
                shutil.copyfileobj(stream, tmp)
            tmp.close()
            name.replace(target)
        finally:
            name.unlink(missing_ok=True)
