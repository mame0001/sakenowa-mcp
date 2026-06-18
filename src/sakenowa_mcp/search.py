"""Fuzzy lookup of sake by name. Sakenowa brand names are Japanese (kanji /
kana); many kanji overlap with Chinese, so substring matching already covers a
lot of CJK queries. We add prefix/exact ranking and a difflib fallback, and
also match the brewery name (蔵元) so 'search by maker' works too.
"""

from __future__ import annotations

import unicodedata
from difflib import SequenceMatcher


def normalize(s: str) -> str:
    """NFKC fold (full-width -> half-width, etc.), trim, lowercase."""
    return unicodedata.normalize("NFKC", s or "").strip().lower()


def _score(query: str, name: str, brewery: str) -> int:
    if not query:
        return 0
    if name == query:
        return 100
    if name.startswith(query):
        return 85
    if query in name:
        return 70
    if brewery and brewery == query:
        return 60
    if brewery and query in brewery:
        return 45
    ratio = SequenceMatcher(None, query, name).ratio()
    if ratio >= 0.6:
        return int(ratio * 40)
    return 0


def search(dataset, query: str, limit: int = 10, area: str = "") -> list:
    """Return up to `limit` Brand objects best matching `query`.

    Ties break toward sake that (a) have flavor data and (b) rank higher.
    `area` optionally filters by area name substring (e.g. '新潟').
    """
    q = normalize(query)
    area_q = normalize(area)
    scored = []
    for b in dataset.brands.values():
        if area_q and area_q not in normalize(b.area):
            continue
        s = _score(q, normalize(b.name), normalize(b.brewery))
        if s > 0:
            scored.append((s, b))
    scored.sort(
        key=lambda t: (
            -t[0],
            0 if t[1].flavor else 1,
            t[1].overall_rank if t[1].overall_rank is not None else 1_000_000,
        )
    )
    return [b for _, b in scored[:limit]]
