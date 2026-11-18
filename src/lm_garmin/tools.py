"""Pinned external tools (mkgmap, splitter): download, verify and locate them."""

from __future__ import annotations

import hashlib
import os
import shutil
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Tool:
    name: str
    version: str
    url: str
    sha256: str

    @property
    def dirname(self) -> str:
        return f"{self.name}-{self.version}"

    @property
    def jar(self) -> str:
        return f"{self.dirname}/{self.name}.jar"


TOOLS: dict[str, Tool] = {
    "mkgmap": Tool(
        "mkgmap",
        "r4924",
        "https://www.mkgmap.org.uk/download/mkgmap-r4924.zip",
        "b2170799b61a95d4fc258e8e4fb4e21396809e0390789178f94c77109f8e0d84",
    ),
    "splitter": Tool(
        "splitter",
        "r654",
        "https://www.mkgmap.org.uk/download/splitter-r654.zip",
        "87b0ca0e827bef556341f66ec8dd7f48eea2a479d1ff3659caa5d6f0e9a9b68c",
    ),
}


def cache_dir() -> Path:
    base = os.environ.get("LM_GARMIN_CACHE") or Path.home() / ".cache" / "lm-garmin"
    return Path(base)


def tools_dir() -> Path:
    return cache_dir() / "tools"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(tool: Tool, dest: Path | None = None) -> Path:
    """Download, verify and unpack a tool. Returns the path to its jar."""
    dest = dest or tools_dir()
    jar = dest / tool.jar
    if jar.exists():
        return jar
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / f"{tool.dirname}.zip"
    if not archive.exists() or sha256_file(archive) != tool.sha256:
        tmp = archive.with_suffix(".part")
        with urllib.request.urlopen(tool.url) as r, tmp.open("wb") as f:
            shutil.copyfileobj(r, f)
        tmp.replace(archive)
    actual = sha256_file(archive)
    if actual != tool.sha256:
        archive.unlink()
        raise RuntimeError(f"{tool.name}: checksum mismatch ({actual} != {tool.sha256})")
    with zipfile.ZipFile(archive) as z:
        z.extractall(dest)
    if not jar.exists():
        raise RuntimeError(f"{tool.name}: {jar} not found after unpacking")
    return jar


def find_java() -> str | None:
    """Locate a java executable: $LM_GARMIN_JAVA, $JAVA_HOME, Homebrew openjdk, PATH."""
    candidates = [
        os.environ.get("LM_GARMIN_JAVA"),
        os.environ.get("JAVA_HOME") and str(Path(os.environ["JAVA_HOME"]) / "bin" / "java"),
        "/opt/homebrew/opt/openjdk/bin/java",
    ]
    for c in candidates:
        if c and Path(c).is_file():
            return c
    return shutil.which("java")
