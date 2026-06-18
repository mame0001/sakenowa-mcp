"""Data layer: fetch the Sakenowa open dataset, cache it locally, and build
an in-memory index of brands joined with brewery, area, flavor and ranking.

Sakenowa Data Project API (no auth, JSON over HTTPS):
    https://muro.sakenowa.com/sakenowa-data/api/{areas,breweries,brands,flavor-charts,rankings}
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

API_BASE = "https://muro.sakenowa.com/sakenowa-data/api"
ATTRIBUTION = "出典／Data: Sakenowa Data Project (https://sakenowa.com) — © Sakenowa"

# logical name -> URL path segment
ENDPOINTS = {
    "areas": "areas",
    "breweries": "breweries",
    "brands": "brands",
    "flavor_charts": "flavor-charts",
    "rankings": "rankings",
}
# logical name -> top-level JSON key holding the list ("rankings" handled specially)
_LIST_KEY = {
    "areas": "areas",
    "breweries": "breweries",
    "brands": "brands",
    "flavor_charts": "flavorCharts",
}

DEFAULT_TTL_SECONDS = 7 * 24 * 3600  # data updates ~monthly; refresh weekly
FLAVOR_KEYS = ("f1", "f2", "f3", "f4", "f5", "f6")


# --------------------------------------------------------------------------- #
# Cache location / config
# --------------------------------------------------------------------------- #
def cache_dir() -> Path:
    override = os.environ.get("SAKENOWA_CACHE_DIR")
    path = Path(override) if override else Path.home() / ".cache" / "sakenowa-mcp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ttl() -> int:
    try:
        return int(os.environ.get("SAKENOWA_TTL_SECONDS", DEFAULT_TTL_SECONDS))
    except ValueError:
        return DEFAULT_TTL_SECONDS


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Fetch + cache
# --------------------------------------------------------------------------- #
def _fetch(name: str) -> Any:
    url = f"{API_BASE}/{ENDPOINTS[name]}"
    with httpx.Client(timeout=30.0, headers={"User-Agent": "sakenowa-mcp/0.1"}) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json()


def refresh() -> dict:
    """Fetch every endpoint and write it to the cache. Returns fresh metadata."""
    cdir = cache_dir()
    counts: dict[str, int] = {}
    year_month: Optional[str] = None
    for name in ENDPOINTS:
        payload = _fetch(name)
        (cdir / f"{name}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        if name == "rankings":
            year_month = payload.get("yearMonth")
            counts[name] = len(payload.get("overall", []))
        else:
            counts[name] = len(payload.get(_LIST_KEY[name], []))
    meta = {
        "fetched_at": time.time(),
        "fetched_at_iso": _iso(time.time()),
        "year_month": year_month,
        "counts": counts,
        "attribution": ATTRIBUTION,
    }
    (cdir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta


def _cache_age() -> Optional[float]:
    meta_path = cache_dir() / "meta.json"
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return time.time() - float(meta.get("fetched_at", 0))
    except (ValueError, json.JSONDecodeError):
        return None


def _read(name: str) -> Any:
    return json.loads((cache_dir() / f"{name}.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# In-memory model
# --------------------------------------------------------------------------- #
@dataclass
class Brand:
    id: int
    name: str
    brewery_id: int
    brewery: str
    area: str
    flavor: Optional[dict]  # {"f1":..,"f6":..} or None
    overall_rank: Optional[int]
    area_rank: Optional[int]


@dataclass
class Dataset:
    meta: dict
    areas: dict           # area_id -> name
    breweries: dict       # brewery_id -> raw dict
    brands: dict          # brand_id  -> Brand

    def brand(self, brand_id: int) -> Optional[Brand]:
        return self.brands.get(int(brand_id))

    @property
    def flavored(self):
        return [b for b in self.brands.values() if b.flavor]


def build() -> Dataset:
    areas_raw = _read("areas")["areas"]
    breweries_raw = _read("breweries")["breweries"]
    brands_raw = _read("brands")["brands"]
    flavor_raw = _read("flavor_charts")["flavorCharts"]
    rankings_raw = _read("rankings")
    meta = json.loads((cache_dir() / "meta.json").read_text(encoding="utf-8"))

    areas = {a["id"]: a["name"] for a in areas_raw}
    breweries = {b["id"]: b for b in breweries_raw}
    flavor = {
        f["brandId"]: {k: f[k] for k in FLAVOR_KEYS} for f in flavor_raw
    }

    overall_rank: dict[int, int] = {
        row["brandId"]: row["rank"] for row in rankings_raw.get("overall", [])
    }
    area_rank: dict[int, int] = {}
    for group in rankings_raw.get("areas", []):
        for row in group.get("ranking", []):
            area_rank.setdefault(row["brandId"], row["rank"])

    brands: dict[int, Brand] = {}
    for br in brands_raw:
        bid = br["id"]
        brewery = breweries.get(br["breweryId"], {})
        brands[bid] = Brand(
            id=bid,
            name=br["name"],
            brewery_id=br["breweryId"],
            brewery=brewery.get("name", ""),
            area=areas.get(brewery.get("areaId"), ""),
            flavor=flavor.get(bid),
            overall_rank=overall_rank.get(bid),
            area_rank=area_rank.get(bid),
        )

    return Dataset(meta=meta, areas=areas, breweries=breweries, brands=brands)


# --------------------------------------------------------------------------- #
# Singleton accessor
# --------------------------------------------------------------------------- #
_DATASET: Optional[Dataset] = None


def get_dataset() -> Dataset:
    """Return the in-memory dataset, fetching/refreshing the cache if missing
    or older than the TTL. Cheap on subsequent calls (cached in-process)."""
    global _DATASET
    if _DATASET is not None:
        return _DATASET
    age = _cache_age()
    if age is None or age > _ttl():
        refresh()
    _DATASET = build()
    return _DATASET


def reset_cache() -> None:
    """Drop the in-process dataset so the next get_dataset() rebuilds it."""
    global _DATASET
    _DATASET = None
