"""Map products built by lm-garmin, with fixed Garmin ids (issue #3).

Every map file on a device needs its own family id and its own tile (map) numbers – a
device silently skips a map whose tile numbers are already loaded (docs/device-testing.md).
Family ids 5730–5736 were used by the planning test kits and are not reused.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

STYLES_DIR = Path(__file__).resolve().parents[2] / "styles"


@dataclass(frozen=True)
class Product:
    key: str
    style: str
    family_id: int
    mapid_base: int  # first 8-digit tile number; splitter counts up from here
    name: str
    levels: str
    transparent: bool = False
    draw_priority: int = 25
    output: str = ""

    @property
    def style_dir(self) -> Path:
        return STYLES_DIR / self.style

    @property
    def typ(self) -> Path:
        return self.style_dir / "typ" / f"{self.style}.txt"

    @property
    def filename(self) -> str:
        return self.output or f"lm-{self.key}.img"


PRODUCTS: dict[str, Product] = {
    "topo50": Product(
        key="topo50",
        style="topo50",
        family_id=5750,
        mapid_base=57500001,
        name="LM Topo50",
        levels="0:24, 1:23, 2:22, 3:21, 4:20, 5:18, 6:16",
    ),
    "skoter": Product(
        key="skoter",
        style="skoter",
        family_id=5751,
        mapid_base=57510001,
        name="LM Skoterleder",
        levels="0:24, 1:22, 2:20, 3:18, 4:16",
        transparent=True,
        draw_priority=30,
    ),
}
