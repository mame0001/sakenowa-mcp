"""Flavor-space math: the six-axis Sakenowa flavor vector, distance,
directional "nudges", an ASCII radar, and an estimated four-type class.

The six axes (each normalized 0..1), per the Sakenowa flavor chart:
    f1 華やか   floral & vibrant
    f2 芳醇     mellow & full-bodied aroma
    f3 重厚     rich & heavy
    f4 穏やか   calm & gentle
    f5 軽快     light & smooth
    f6 ドライ   dry
"""

from __future__ import annotations

import unicodedata
from statistics import median
from typing import Iterable, Optional

AXES = [
    ("f1", "華やか", "floral & vibrant"),
    ("f2", "芳醇", "mellow & full"),
    ("f3", "重厚", "rich & heavy"),
    ("f4", "穏やか", "calm & gentle"),
    ("f5", "軽快", "light & smooth"),
    ("f6", "ドライ", "dry"),
]
KEYS = [a[0] for a in AXES]
JP = {k: jp for k, jp, _ in AXES}
EN = {k: en for k, _, en in AXES}


def vec(flavor: dict) -> list:
    return [flavor[k] for k in KEYS]


def distance(a: Iterable[float], b: Iterable[float]) -> float:
    """Euclidean distance in 6-D flavor space."""
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


# Directional taste nudges. Each mode shifts the target vector before the
# nearest-neighbour search, so "drier" finds sake that is *like this one but
# drier*, not merely the driest sake overall.
MODE_SHIFTS = {
    "similar": {},
    "drier": {"f6": +0.20, "f2": -0.10},
    "sweeter": {"f6": -0.20, "f2": +0.10},
    "lighter": {"f5": +0.20, "f3": -0.15, "f2": -0.10},
    "richer": {"f3": +0.20, "f2": +0.15, "f5": -0.15},
    "more_aromatic": {"f1": +0.25, "f4": -0.15},
    "calmer": {"f4": +0.20, "f1": -0.15},
}
MODES = list(MODE_SHIFTS.keys()) + ["contrast"]


def _clamp(x: float) -> float:
    return min(1.0, max(0.0, x))


def shift(v: list, mode: str) -> list:
    deltas = MODE_SHIFTS.get(mode, {})
    return [_clamp(x + deltas.get(k, 0.0)) for k, x in zip(KEYS, v)]


def contrast_vec(v: list) -> list:
    """Mirror the vector around the 0.5 midpoint — the 'opposite' palate."""
    return [_clamp(1.0 - x) for x in v]


# --------------------------------------------------------------------------- #
# Estimated four-type classification (薫 / 爽 / 醇 / 熟)
# --------------------------------------------------------------------------- #
# Heuristic, self-calibrated against the median of all rated sake:
#   aroma axis  = 華やか − 穏やか  (f1 − f4)
#   body axis   = (芳醇 + 重厚)/2 − 軽快  ((f2+f3)/2 − f5)
# This is an experimental estimate, NOT the official SSI sensory category.
def axis_scores(flavor: dict) -> tuple:
    aroma = flavor["f1"] - flavor["f4"]
    body = (flavor["f2"] + flavor["f3"]) / 2 - flavor["f5"]
    return aroma, body


def compute_medians(flavors: Iterable[dict]) -> dict:
    aromas, bodies = [], []
    for f in flavors:
        a, b = axis_scores(f)
        aromas.append(a)
        bodies.append(b)
    return {"aroma": median(aromas), "body": median(bodies)}


def estimate_type(flavor: dict, medians: Optional[dict] = None) -> tuple:
    """Return (kanji, romaji, gloss). Experimental heuristic — see module note."""
    aroma, body = axis_scores(flavor)
    am = medians["aroma"] if medians else 0.0
    bm = medians["body"] if medians else 0.0
    hi_aroma, hi_body = aroma >= am, body >= bm
    if hi_aroma and not hi_body:
        return ("薫酒", "Kunshu", "aromatic & light — fragrant, delicate")
    if not hi_aroma and not hi_body:
        return ("爽酒", "Soshu", "light & smooth — crisp, refreshing")
    if not hi_aroma and hi_body:
        return ("醇酒", "Junshu", "rich & full — savory, full-bodied")
    return ("熟酒", "Jukushu", "aged & complex — deep, layered")


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def _display_width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _pad(s: str, width: int) -> str:
    return s + " " * max(0, width - _display_width(s))


def radar(flavor: dict, bar_width: int = 18) -> str:
    """A compact ASCII bar chart of the six axes."""
    lines = []
    for k, jp, en in AXES:
        val = float(flavor[k])
        filled = round(val * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        lines.append(f"  {_pad(jp, 8)} {bar} {val:.2f}  {en}")
    return "\n".join(lines)


def top_tags(flavor: dict, n: int = 3) -> list:
    """The n most pronounced axes, as 'JP (en)' tags."""
    ordered = sorted(AXES, key=lambda a: flavor[a[0]], reverse=True)
    return [f"{jp}({en})" for k, jp, en in ordered[:n]]
