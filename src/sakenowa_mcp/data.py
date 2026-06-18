"""Data layer: fetch the Sakenowa open dataset, cache it locally, and build
an in-memory index of brands joined with brewery, area, flavor and ranking.

Sakenowa Data Project API (no auth, JSON over HTTPS):
    https://muro.sakenowa.com/sakenowa-data/api/{areas,breweries,brands,flavor-charts,rankings}
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

from . import flavor as _flavor

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


def _validate_payload(name: str, payload: Any) -> None:
    """Sanity-check a freshly fetched endpoint before it is allowed into the
    cache, so a partial/HTML/error response can't quietly corrupt it."""
    if not isinstance(payload, dict):
        raise ValueError(f"/{ENDPOINTS[name]} did not return a JSON object")
    if name == "rankings":
        if not isinstance(payload.get("overall"), list):
            raise ValueError("rankings payload missing 'overall' list")
    else:
        key = _LIST_KEY[name]
        if not isinstance(payload.get(key), list):
            raise ValueError(f"/{ENDPOINTS[name]} payload missing '{key}' list")


def _atomic_write(path: Path, text: str) -> None:
    """Write via a temp file + os.replace so readers never see a half-written
    file and a crash can't truncate an existing one."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def refresh() -> dict:
    """Fetch every endpoint, validate it, then commit the whole snapshot to the
    cache atomically. Raises before touching the cache if any fetch fails, so a
    mid-refresh network error leaves the previous snapshot intact."""
    cdir = cache_dir()
    payloads: dict[str, Any] = {}
    counts: dict[str, int] = {}
    year_month: Optional[str] = None

    # Phase 1: fetch + validate everything in memory (no cache writes yet).
    for name in ENDPOINTS:
        payload = _fetch(name)
        _validate_payload(name, payload)
        payloads[name] = payload
        if name == "rankings":
            year_month = payload.get("yearMonth")
            counts[name] = len(payload.get("overall", []))
        else:
            counts[name] = len(payload.get(_LIST_KEY[name], []))

    # Phase 2: commit. Data files first, then meta.json last as the marker that
    # a complete, consistent snapshot is on disk.
    for name, payload in payloads.items():
        _atomic_write(cdir / f"{name}.json", json.dumps(payload, ensure_ascii=False))
    meta = {
        "fetched_at": time.time(),
        "fetched_at_iso": _iso(time.time()),
        "year_month": year_month,
        "counts": counts,
        "attribution": ATTRIBUTION,
    }
    _atomic_write(cdir / "meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
    return meta


def _cache_complete() -> bool:
    """True only if every endpoint file plus meta.json exists and parses."""
    cdir = cache_dir()
    for name in list(ENDPOINTS) + ["meta"]:
        path = cdir / f"{name}.json"
        if not path.exists():
            return False
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return False
    return True


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
    medians: dict = field(default_factory=lambda: {"aroma": 0.0, "body": 0.0})

    def brand(self, brand_id: int) -> Optional[Brand]:
        try:
            return self.brands.get(int(brand_id))
        except (TypeError, ValueError):
            return None

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

    areas = {a["id"]: a["name"] for a in areas_raw if "id" in a}
    breweries = {b["id"]: b for b in breweries_raw if "id" in b}

    # Flavor rows: coerce to float, keep only complete vectors in [0, 1].
    flavor: dict[int, dict] = {}
    for f in flavor_raw:
        bid = f.get("brandId")
        if bid is None:
            continue
        try:
            vals = {k: float(f[k]) for k in FLAVOR_KEYS}
        except (KeyError, TypeError, ValueError):
            continue
        if all(0.0 <= v <= 1.0 for v in vals.values()):
            flavor[bid] = vals

    overall_rank: dict[int, int] = {}
    for row in rankings_raw.get("overall", []):
        if "brandId" in row and "rank" in row:
            overall_rank[row["brandId"]] = row["rank"]
    area_rank: dict[int, int] = {}
    for group in rankings_raw.get("areas", []):
        for row in group.get("ranking", []):
            if "brandId" in row and "rank" in row:
                area_rank.setdefault(row["brandId"], row["rank"])

    brands: dict[int, Brand] = {}
    for br in brands_raw:
        bid = br.get("id")
        if bid is None:
            continue
        brewery = breweries.get(br.get("breweryId"), {})
        brands[bid] = Brand(
            id=bid,
            name=br.get("name", ""),
            brewery_id=br.get("breweryId"),
            brewery=brewery.get("name", ""),
            area=areas.get(brewery.get("areaId"), ""),
            flavor=flavor.get(bid),
            overall_rank=overall_rank.get(bid),
            area_rank=area_rank.get(bid),
        )

    # Medians for the four-type heuristic: computed once here, not per request.
    medians = _flavor.compute_medians([b.flavor for b in brands.values() if b.flavor])

    age = _cache_age()
    meta["stale"] = age is not None and age > _ttl()

    return Dataset(
        meta=meta, areas=areas, breweries=breweries, brands=brands, medians=medians
    )


# --------------------------------------------------------------------------- #
# Singleton accessor
# --------------------------------------------------------------------------- #
_DATASET: Optional[Dataset] = None
_LOCK = threading.RLock()


def get_dataset() -> Dataset:
    """Return the in-memory dataset, fetching/refreshing the cache if missing or
    older than the TTL. Thread-safe. If a refresh is due but the network is
    unavailable, an existing (stale) cache is served rather than failing; only a
    truly empty/corrupt cache raises."""
    global _DATASET
    with _LOCK:
        if _DATASET is not None:
            return _DATASET
        age = _cache_age()
        if age is None or age > _ttl():
            try:
                refresh()
            except Exception as exc:  # network / HTTP / validation error
                if not _cache_complete():
                    raise RuntimeError(
                        "Could not fetch Sakenowa data and no usable local cache "
                        f"exists. Check your network and retry. ({exc})"
                    ) from exc
                # Otherwise: fall through and serve the existing (stale) cache.
        _DATASET = build()
        return _DATASET


def reset_cache() -> None:
    """Drop the in-process dataset so the next get_dataset() rebuilds it."""
    global _DATASET
    with _LOCK:
        _DATASET = None
