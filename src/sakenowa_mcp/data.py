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
        if len(payload.get("overall", [])) == 0:
            raise ValueError("rankings payload 'overall' list is empty")
    else:
        key = _LIST_KEY[name]
        if not isinstance(payload.get(key), list):
            raise ValueError(f"/{ENDPOINTS[name]} payload missing '{key}' list")
        if len(payload.get(key, [])) == 0:
            raise ValueError(f"/{ENDPOINTS[name]} payload '{key}' list is empty")


def _atomic_write(path: Path, text: str) -> None:
    """Write via a temp file + os.replace so readers never see a half-written
    file and a crash can't truncate an existing one."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def refresh() -> dict:
    """Fetch every endpoint, validate it, then commit the whole snapshot to the
    cache atomically (single file). Raises before touching the cache if any fetch
    fails, so a mid-refresh network error leaves the previous snapshot intact."""
    import shutil
    import tempfile

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

    # Phase 2: write single snapshot file to unique temp directory.
    # tempfile.mkdtemp() prevents cross-process collision of .tmp dirs.
    fetched_at = time.time()
    temp_dir = Path(tempfile.mkdtemp(dir=cdir, prefix="snapshot-"))
    try:
        # Single snapshot JSON includes all endpoints + metadata.
        snapshot = {
            "fetched_at": fetched_at,
            "fetched_at_iso": _iso(fetched_at),
            "year_month": year_month,
            "counts": counts,
            "attribution": ATTRIBUTION,
            "payloads": payloads,  # All 5 endpoints in one file
        }
        snapshot_path = temp_dir / "snapshot.json"
        snapshot_path.write_text(
            json.dumps(snapshot, ensure_ascii=False), encoding="utf-8"
        )

        # Phase 3: atomic commit (single os.replace).
        # Move temp dir to finalized name, replacing any old snapshot dir.
        final_snapshot_dir = cdir / f"snapshot-{int(fetched_at)}"
        os.replace(temp_dir, final_snapshot_dir)

        # Update pointer (meta.json) atomically to reference the new snapshot.
        meta = {
            "snapshot_dir": f"snapshot-{int(fetched_at)}",
            "fetched_at": fetched_at,
            "fetched_at_iso": _iso(fetched_at),
            "year_month": year_month,
            "counts": counts,
            "attribution": ATTRIBUTION,
        }
        meta_tmp = cdir / "meta.json.tmp"
        meta_tmp.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(meta_tmp, cdir / "meta.json")
    except Exception:
        # Cleanup the staging dir if anything failed.
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    return meta


def _cache_complete() -> bool:
    """True only if meta.json points to a valid snapshot.json with all endpoints."""
    try:
        snapshot = _get_snapshot()
        # Validate snapshot schema: must have payloads with all 5 endpoints.
        payloads = snapshot.get("payloads", {})
        for name in ENDPOINTS:
            if name not in payloads:
                return False
            _validate_payload(name, payloads[name])
        return True
    except (FileNotFoundError, ValueError, json.JSONDecodeError, KeyError):
        return False


def _cache_age() -> Optional[float]:
    meta_path = cache_dir() / "meta.json"
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return time.time() - float(meta.get("fetched_at", 0))
    except (ValueError, json.JSONDecodeError):
        return None


def _get_snapshot() -> dict:
    """Load the current snapshot from the pointer in meta.json."""
    meta_path = cache_dir() / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError("meta.json not found")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    snapshot_dir_name = meta.get("snapshot_dir")
    if not snapshot_dir_name:
        raise ValueError("meta.json missing snapshot_dir pointer")
    snapshot_path = cache_dir() / snapshot_dir_name / "snapshot.json"
    if not snapshot_path.exists():
        raise FileNotFoundError(f"snapshot at {snapshot_path} not found")
    return json.loads(snapshot_path.read_text(encoding="utf-8"))


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
    """Build in-memory dataset from a single consistent snapshot (not multiple files)."""
    try:
        snapshot = _get_snapshot()
        payloads = snapshot.get("payloads", {})
        areas_raw = payloads["areas"]["areas"]
        breweries_raw = payloads["breweries"]["breweries"]
        brands_raw = payloads["brands"]["brands"]
        flavor_raw = payloads["flavor_charts"]["flavorCharts"]
        rankings_raw = payloads["rankings"]
        # Meta from snapshot (includes all counts, attribution, fetch timestamp).
        meta = {k: v for k, v in snapshot.items() if k != "payloads"}
    except (KeyError, FileNotFoundError, json.JSONDecodeError, TypeError, AttributeError) as e:
        raise ValueError(f"Corrupted cached data cannot be parsed: {e}") from e

    areas = {a["id"]: a["name"] for a in areas_raw if isinstance(a, dict) and "id" in a and "name" in a}
    breweries = {b["id"]: b for b in breweries_raw if isinstance(b, dict) and "id" in b}

    # Flavor rows: coerce to float, keep only complete vectors in [0, 1].
    flavor: dict[int, dict] = {}
    for f in flavor_raw:
        if not isinstance(f, dict):
            continue
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
        if isinstance(row, dict) and "brandId" in row and "rank" in row:
            overall_rank[row["brandId"]] = row["rank"]
    area_rank: dict[int, int] = {}
    for group in rankings_raw.get("areas", []):
        if not isinstance(group, dict):
            continue
        for row in group.get("ranking", []):
            if isinstance(row, dict) and "brandId" in row and "rank" in row:
                area_rank.setdefault(row["brandId"], row["rank"])

    brands: dict[int, Brand] = {}
    for br in brands_raw:
        if not isinstance(br, dict):
            continue
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
_LAST_REFRESH_ATTEMPT: Optional[float] = None
_REFRESH_BACKOFF_SECONDS = 300  # Don't retry network for 5 min after failure


def get_dataset() -> Dataset:
    """Return the in-memory dataset, fetching/refreshing the cache if missing or
    older than the TTL. Thread-safe. If a refresh is due but the network is
    unavailable, an existing (stale) cache is served rather than failing; only a
    truly empty/corrupt cache raises. Backoff prevents hammering the network
    when it is unavailable."""
    global _DATASET, _LAST_REFRESH_ATTEMPT
    with _LOCK:
        age = _cache_age()
        now = time.time()

        # If cache is stale or missing, clear the in-memory dataset to force refresh.
        if age is None or age > _ttl():
            _DATASET = None

        # If we have a recent valid dataset in memory, return it without network.
        if _DATASET is not None:
            return _DATASET

        # Decide whether to attempt a network refresh.
        # Only retry network if:
        #   1. Cache is missing or stale, AND
        #   2. We haven't tried recently (backoff to avoid hammering network)
        should_attempt_refresh = (
            (age is None or age > _ttl()) and
            (_LAST_REFRESH_ATTEMPT is None or
             now - _LAST_REFRESH_ATTEMPT > _REFRESH_BACKOFF_SECONDS)
        )

        if should_attempt_refresh:
            _LAST_REFRESH_ATTEMPT = now
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
    """Drop the in-process dataset so the next get_dataset() rebuilds it.
    Also reset the refresh attempt timer to allow immediate retry."""
    global _DATASET, _LAST_REFRESH_ATTEMPT
    with _LOCK:
        _DATASET = None
        _LAST_REFRESH_ATTEMPT = None
