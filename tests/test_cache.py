"""Offline tests for the cache layer: pruning and self-healing (no network).

These exercise data.py's filesystem/state logic by pointing SAKENOWA_CACHE_DIR
at a tmp dir and stubbing refresh(), so nothing here touches the Sakenowa API.
"""

import json
import time

from sakenowa_mcp import data


def _write_snapshot(cdir, dir_name, *, fetched_at=None):
    """Write a minimal but schema-valid snapshot dir + matching meta.json."""
    fetched_at = fetched_at if fetched_at is not None else time.time()
    snapshot = {
        "fetched_at": fetched_at,
        "fetched_at_iso": data._iso(fetched_at),
        "year_month": "202605",
        "counts": {},
        "attribution": data.ATTRIBUTION,
        "payloads": {
            "areas": {"areas": [{"id": 1, "name": "Niigata"}]},
            "breweries": {"breweries": [{"id": 1, "name": "B", "areaId": 1}]},
            "brands": {"brands": [{"id": 1, "name": "S", "breweryId": 1}]},
            "flavor_charts": {
                "flavorCharts": [
                    {"brandId": 1, "f1": 0.5, "f2": 0.5, "f3": 0.5,
                     "f4": 0.5, "f5": 0.5, "f6": 0.5}
                ]
            },
            "rankings": {
                "overall": [{"brandId": 1, "rank": 1}],
                "areas": [],
                "yearMonth": "202605",
            },
        },
    }
    snap_dir = cdir / dir_name
    snap_dir.mkdir(parents=True, exist_ok=True)
    (snap_dir / "snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")
    meta = {k: v for k, v in snapshot.items() if k != "payloads"}
    meta["snapshot_dir"] = dir_name
    (cdir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return meta


def test_prune_keeps_only_current_snapshot(tmp_path):
    keep = "snapshot-200"
    _write_snapshot(tmp_path, keep)
    # Cruft that prune must remove:
    (tmp_path / "snapshot-100").mkdir()           # superseded snapshot
    (tmp_path / ".staging-abc").mkdir()           # killed-refresh leftover
    for legacy in data._LEGACY_FILES:             # pre-snapshot multi-file format
        (tmp_path / legacy).write_text("{}")

    data._prune_cache(tmp_path, keep=keep)

    remaining = {p.name for p in tmp_path.iterdir()}
    assert remaining == {keep, "meta.json"}


def test_prune_is_best_effort_on_missing_keep(tmp_path):
    # keep that doesn't exist must not raise and must not nuke meta.json.
    _write_snapshot(tmp_path, "snapshot-1")
    data._prune_cache(tmp_path, keep="snapshot-does-not-exist")
    # snapshot-1 is now "superseded" (!= keep) so it's gone, but no crash.
    assert (tmp_path / "meta.json").exists()


def test_get_dataset_self_heals_unreadable_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("SAKENOWA_CACHE_DIR", str(tmp_path))
    # Old-format meta.json: a *fresh* timestamp (so the TTL check would normally
    # skip refresh) but NO snapshot_dir pointer — the exact state that used to
    # crash with "meta.json missing snapshot_dir pointer".
    (tmp_path / "meta.json").write_text(
        json.dumps({"fetched_at": time.time()}), encoding="utf-8"
    )
    data.reset_cache()

    calls = {"n": 0}

    def fake_refresh():
        calls["n"] += 1
        return _write_snapshot(tmp_path, "snapshot-999")

    monkeypatch.setattr(data, "refresh", fake_refresh)

    ds = data.get_dataset()

    assert calls["n"] == 1            # self-heal triggered exactly one refetch
    assert len(ds.brands) == 1        # rebuilt successfully from fresh snapshot
    data.reset_cache()                # don't leak state into other tests
