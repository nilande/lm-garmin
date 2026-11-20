"""S0: unpack a Topografi 50 delivery (one zip per theme) into the local GeoPackage cache.

GeoPackages are never read from inside the zips (deflate makes random access slow). Each
theme is unpacked once; a manifest records what was unpacked from where, so re-running is a
no-op unless a zip changed.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import time
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .stage_cache import StageCache

MANIFEST = "manifest.json"


@dataclass
class Entry:
    zip_name: str
    zip_size: int
    zip_mtime: float
    gpkg: str
    gpkg_size: int
    seconds: float
    zip_sha256: str | None = None


@dataclass
class Manifest:
    delivery: str = ""
    uttag_sha256: str | None = None
    entries: dict[str, Entry] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> Manifest:
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        entries = {k: Entry(**v) for k, v in raw.get("entries", {}).items()}
        return cls(raw.get("delivery", ""), raw.get("uttag_sha256"), entries)

    def save(self, path: Path) -> None:
        data = {
            "delivery": self.delivery,
            "uttag_sha256": self.uttag_sha256,
            "entries": {k: asdict(v) for k, v in self.entries.items()},
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)


@dataclass
class Result:
    zip_name: str
    gpkg: Path
    skipped: bool
    seconds: float = 0.0
    mb_per_s: float = 0.0


def is_junk(p: Path) -> bool:
    """macOS metadata files that must never be treated as data."""
    return p.name.startswith("._") or p.name == ".DS_Store"


def delivery_zips(delivery: Path) -> list[Path]:
    zips = sorted(p for p in delivery.glob("*.zip") if not is_junk(p))
    if not zips:
        raise FileNotFoundError(f"no theme zips found in {delivery}")
    return zips


def gpkg_member(z: zipfile.ZipFile) -> zipfile.ZipInfo:
    members = [
        i for i in z.infolist() if i.filename.endswith(".gpkg") and not is_junk(Path(i.filename))
    ]
    if len(members) != 1:
        raise ValueError(f"{z.filename}: expected exactly one .gpkg, found {len(members)}")
    return members[0]


def check_gpkg(path: Path) -> None:
    """Open read-only and make sure every feature table has its R-tree index."""
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as c:
        tables = c.execute("SELECT table_name, column_name FROM gpkg_geometry_columns").fetchall()
        names = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not tables:
        raise ValueError(f"{path}: no feature tables")
    missing = [f"rtree_{t}_{g}" for t, g in tables if f"rtree_{t}_{g}" not in names]
    if missing:
        raise ValueError(f"{path}: missing spatial index {', '.join(missing)}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unpack(delivery: Path, dest: Path, *, log=print) -> list[Result]:
    """Unpack every theme zip in `delivery` to `dest` (one .gpkg per theme)."""
    fingerprints = StageCache(dest.parent)
    with fingerprints.lease(exclusive=True):
        return _unpack(delivery, dest, fingerprints, log)


def _unpack(delivery: Path, dest: Path, fingerprints: StageCache, log) -> list[Result]:
    dest.mkdir(parents=True, exist_ok=True)
    mpath = dest / MANIFEST
    manifest = Manifest.load(mpath)
    manifest.delivery = str(delivery)
    uttag = delivery / "uttag.json"
    manifest.uttag_sha256 = sha256(uttag) if uttag.exists() else None

    results = []
    for zp in delivery_zips(delivery):
        st = zp.stat()
        digest = fingerprints.fingerprint(zp)
        prev = manifest.entries.get(zp.name)
        if (
            prev
            and prev.zip_sha256 == digest
            and (dest / prev.gpkg).exists()
            and (dest / prev.gpkg).stat().st_size == prev.gpkg_size
        ):
            results.append(Result(zp.name, dest / prev.gpkg, skipped=True))
            continue

        t0 = time.monotonic()
        with zipfile.ZipFile(zp) as z:
            member = gpkg_member(z)
            out = dest / Path(member.filename).name
            tmp = out.with_suffix(".gpkg.part")
            with z.open(member) as src, tmp.open("wb") as dst:
                shutil.copyfileobj(src, dst, length=8 << 20)
        check_gpkg(tmp)
        tmp.replace(out)
        dt = time.monotonic() - t0
        rate = st.st_size / 1e6 / dt if dt > 0 else 0.0
        manifest.entries[zp.name] = Entry(
            zp.name, st.st_size, st.st_mtime, out.name, out.stat().st_size, round(dt, 2), digest
        )
        manifest.save(mpath)
        results.append(Result(zp.name, out, skipped=False, seconds=dt, mb_per_s=rate))
        log(f"{zp.name}: {out.stat().st_size / 1e6:.0f} MB in {dt:.1f}s ({rate:.0f} MB/s read)")

    manifest.save(mpath)
    return results
