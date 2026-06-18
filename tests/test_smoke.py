"""Offline unit tests for the pure flavor / search logic (no network)."""

import pytest

from sakenowa_mcp import flavor, search


def test_distance_identity():
    v = [0.5] * 6
    assert flavor.distance(v, v) == 0.0


def test_distance_symmetry():
    a, b = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6], [0.6, 0.5, 0.4, 0.3, 0.2, 0.1]
    assert flavor.distance(a, b) == flavor.distance(b, a)


def test_shift_stays_in_unit_range():
    v = flavor.shift([0.95] * 6, "drier")
    assert all(0.0 <= x <= 1.0 for x in v)


def test_drier_increases_dryness():
    base = [0.5] * 6
    shifted = flavor.shift(base, "drier")
    assert shifted[flavor.KEYS.index("f6")] > base[flavor.KEYS.index("f6")]


def test_contrast_mirrors():
    assert flavor.contrast_vec([0.0, 1.0, 0.5, 0.2, 0.8, 0.3]) == pytest.approx(
        [1.0, 0.0, 0.5, 0.8, 0.2, 0.7]
    )


def test_normalize_fullwidth_and_case():
    assert search.normalize("  Ｈａｋｋａｉｓａｎ ") == "hakkaisan"


def test_estimate_type_returns_known_class():
    kanji, romaji, _ = flavor.estimate_type({f"f{i}": 0.5 for i in range(1, 7)})
    assert kanji in {"薫酒", "爽酒", "醇酒", "熟酒"}


def test_top_tags_count():
    f = {"f1": 0.9, "f2": 0.1, "f3": 0.8, "f4": 0.2, "f5": 0.7, "f6": 0.3}
    assert len(flavor.top_tags(f, 3)) == 3
    assert flavor.top_tags(f, 1)[0].startswith("華やか")


def test_compute_medians_empty_does_not_crash():
    assert flavor.compute_medians([]) == {"aroma": 0.0, "body": 0.0}


def test_single_char_query_skips_fuzzy():
    # 'z' is absent from 'ab' and is only 1 char -> fuzzy disabled -> no match
    assert search._score("z", "ab", "") == 0


def test_two_char_query_allows_fuzzy():
    assert search._score("abx", "abc", "") > 0
