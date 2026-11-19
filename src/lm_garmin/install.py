"""Copy built maps to a Garmin device (mounted as a USB drive) safely.

Each map is copied to `<name>.part`, verified with SHA-256 and only then renamed, so the
device never sees a half-written map. macOS AppleDouble files (`._<name>`), which the
device could mistake for maps, are removed for the installed files.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

DEFAULT_DEVICE = Path("/Volumes/GARMIN")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def garmin_dir(device: Path) -> Path:
    d = device / "Garmin"
    if not d.is_dir():
        raise FileNotFoundError(f"{d} not found – is the device connected and mounted?")
    return d


def install(files: list[Path], device: Path = DEFAULT_DEVICE, *, log=print) -> list[Path]:
    target = garmin_dir(device)
    need = sum(f.stat().st_size for f in files)
    free = shutil.disk_usage(target).free
    if need > free:
        raise OSError(
            f"not enough space on {device}: need {need / 1e9:.2f} GB, {free / 1e9:.2f} GB free"
        )
    done = []
    for src in files:
        if src.suffix.lower() != ".img":
            raise ValueError(f"{src} is not an .img file")
        dest = target / src.name
        part = target / (src.name + ".part")
        shutil.copyfile(src, part)
        if sha256(part) != sha256(src):
            part.unlink()
            raise OSError(f"checksum mismatch after copying {src.name}; nothing replaced")
        os.replace(part, dest)
        junk = target / ("._" + src.name)
        if junk.exists():
            junk.unlink()
        done.append(dest)
        log(f"{src.name} → {dest} ({src.stat().st_size / 1e6:.1f} MB, verified)")
    os.sync()
    return done
