"""sakenowa-mcp — MCP server exposing the Sakenowa sake dataset as a
flavor-space engine: search sake, read a six-axis flavor profile, find
flavor-similar (or deliberately different) sake, and compare bottles.

Run over stdio:  `sakenowa-mcp`  (or `uv run sakenowa-mcp`)
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import data, flavor, search

mcp = FastMCP("sakenowa")

ATTR = data.ATTRIBUTION
# The Sakenowa API carries NO bottle spec data — be explicit so callers don't
# hallucinate it.
MISSING_FIELDS = [
    "精米歩合 (rice-polishing ratio)",
    "酒米 (rice variety)",
    "日本酒度 / SMV (sweetness-dryness meter value)",
    "酸度 (acidity)",
    "アルコール度数 (ABV)",
    "特定名称 (junmai / ginjo / daiginjo grade)",
    "価格 (price)",
    "醸造年度 (brewing year / vintage)",
]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _ds():
    return data.get_dataset()


def _clamp_int(value, lo: int, hi: int, default: int) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(v, hi))


def _brand_line(b) -> str:
    flag = "✓flavor" if b.flavor else "—"
    rank = f" · #{b.overall_rank} overall" if b.overall_rank else ""
    return f"- **{b.name}** (id `{b.id}`) — {b.brewery} / {b.area} · {flag}{rank}"


# --------------------------------------------------------------------------- #
# Tool 1 — sync
# --------------------------------------------------------------------------- #
@mcp.tool()
def sync_sakenowa_data(force: bool = False) -> str:
    """Fetch/refresh the Sakenowa open dataset into a local cache and report
    its scale. The cache auto-refreshes weekly, so you rarely need this — call
    it with force=True only to pull the latest monthly snapshot immediately.

    Returns dataset counts, the data's year-month, and the required attribution.
    """
    if force:
        data.refresh()
        data.reset_cache()
    ds = _ds()
    c = ds.meta.get("counts", {})
    flavored = len(ds.flavored)
    total_brands = len(ds.brands)
    pct = (100 * flavored / total_brands) if total_brands else 0
    stale = " ⚠️ stale (refresh failed; serving cached snapshot)" if ds.meta.get("stale") else ""
    return (
        f"# Sakenowa dataset synced\n"
        f"- Snapshot (year-month): **{ds.meta.get('year_month')}**{stale}\n"
        f"- Fetched: {ds.meta.get('fetched_at_iso')}\n"
        f"- Breweries: **{c.get('breweries', 0):,}**\n"
        f"- Brands (sake): **{total_brands:,}**\n"
        f"- With flavor chart: **{flavored:,}** ({pct:.0f}% coverage)\n"
        f"- Ranked this month: **{c.get('rankings', 0):,}**\n"
        f"- Areas (prefectures): **{len(ds.areas)}**\n\n"
        f"_{ATTR}_"
    )


# --------------------------------------------------------------------------- #
# Tool 2 — search
# --------------------------------------------------------------------------- #
@mcp.tool()
def search_sake(query: str, limit: int = 10, area: str = "") -> str:
    """Find sake by brand name or brewery name and return their IDs.

    Names are Japanese; kanji queries (e.g. 八海山, 獺祭) match directly, and
    so do Chinese kanji that share the glyphs. Use `area` to filter by
    prefecture name (e.g. '新潟'). Use the returned `id` with
    get_sake_profile / find_similar_sake / compare_sake.
    """
    ds = _ds()
    limit = _clamp_int(limit, 1, 20, 10)
    hits = search.search(ds, query, limit=limit, area=area)
    if not hits:
        tip = f" in area '{area}'" if area else ""
        return f"No sake matched '{query}'{tip}. Try fewer characters or a kanji name."
    head = f"# {len(hits)} match(es) for '{query}'" + (f" · area={area}" if area else "")
    body = "\n".join(_brand_line(b) for b in hits)
    return f"{head}\n{body}\n\n_{ATTR}_"


# --------------------------------------------------------------------------- #
# Tool 3 — profile
# --------------------------------------------------------------------------- #
@mcp.tool()
def get_sake_profile(brand_id: int) -> str:
    """Return the six-axis flavor profile of one sake: an ASCII radar, the
    dominant flavor tags, an *estimated* four-type class (薫/爽/醇/熟,
    heuristic), and its overall/area popularity rank.

    Also lists the bottle-spec fields the Sakenowa dataset does NOT provide
    (polishing ratio, SMV, ABV, price, …) so they are never invented.
    """
    ds = _ds()
    b = ds.brand(brand_id)
    if b is None:
        return f"No sake with id {brand_id}. Use search_sake to find the right id."

    lines = [f"# {b.name}", f"- Brewery: {b.brewery} · Area: {b.area} · id `{b.id}`"]
    if b.overall_rank:
        lines.append(f"- Popularity: #{b.overall_rank} overall"
                     + (f", #{b.area_rank} in {b.area}" if b.area_rank else ""))

    if not b.flavor:
        lines.append("\n_No flavor chart available for this sake "
                     "(only ~41% of brands are rated)._")
        lines.append(f"\n_{ATTR}_")
        return "\n".join(lines)

    kanji, romaji, gloss = flavor.estimate_type(b.flavor, ds.medians)
    lines += [
        "",
        "## Flavor chart (0–1)",
        "```",
        flavor.radar(b.flavor),
        "```",
        f"**Dominant:** {', '.join(flavor.top_tags(b.flavor))}",
        f"**Estimated type:** {kanji} ({romaji}) — {gloss}  "
        f"_(experimental heuristic, not an official SSI category)_",
        "",
        "## Not in this dataset",
        ", ".join(MISSING_FIELDS),
        "",
        f"_{ATTR}_",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Tool 4 — similarity (the core feature)
# --------------------------------------------------------------------------- #
@mcp.tool()
def find_similar_sake(brand_id: int, mode: str = "similar", limit: int = 5) -> str:
    """★ Core feature ★ Given one sake, find others by flavor-vector proximity.

    `mode` steers the direction in flavor space:
      - similar       : nearest overall (a true taste-alike)
      - drier         : like this, but drier
      - sweeter       : like this, but less dry / rounder
      - lighter       : like this, but lighter & crisper
      - richer        : like this, but fuller & heavier
      - more_aromatic : like this, but more floral/fragrant
      - calmer        : like this, but quieter on the nose
      - contrast      : the opposite palate (for deliberate exploration)

    Only sake that have a flavor chart can be matched.
    """
    ds = _ds()
    b = ds.brand(brand_id)
    if b is None:
        return f"No sake with id {brand_id}. Use search_sake first."
    if not b.flavor:
        return (f"'{b.name}' (id {brand_id}) has no flavor chart, so it can't be "
                f"matched. Pick a sake whose profile shows ✓flavor.")
    if mode not in flavor.MODES:
        return f"Unknown mode '{mode}'. Choose one of: {', '.join(flavor.MODES)}."
    limit = _clamp_int(limit, 1, 10, 5)

    base = flavor.vec(b.flavor)
    target = flavor.contrast_vec(base) if mode == "contrast" else flavor.shift(base, mode)

    ranked = sorted(
        (
            (flavor.distance(target, flavor.vec(o.flavor)), o)
            for o in ds.flavored
            if o.id != b.id
        ),
        key=lambda t: t[0],
    )[:limit]

    if mode == "contrast":
        verb, metric, note = (
            "Most contrasting", "opposite-fit",
            "_Ranked by closeness to the mirrored (opposite) flavor target._",
        )
    elif mode == "similar":
        verb, metric, note = "Closest (similar)", "match", ""
    else:
        verb, metric, note = (
            f"Closest ({mode})", "fit",
            f"_Ranked by closeness to a '{mode}'-shifted target; the direction is "
            f"approximate and may be weak where the data is sparse._",
        )

    lines = [
        f"# {verb} to **{b.name}** ({b.brewery} / {b.area})",
        f"_base: {', '.join(flavor.top_tags(b.flavor))}_",
    ]
    if note:
        lines.append(note)
    lines.append("")
    for dist, o in ranked:
        sim = max(0.0, 1 - dist / (6 ** 0.5))  # rough 0..1 closeness to target
        lines.append(
            f"- **{o.name}** (id `{o.id}`) — {o.brewery} / {o.area} · "
            f"{metric} {sim:.0%} · {', '.join(flavor.top_tags(o.flavor))}"
        )
    lines.append(f"\n_{ATTR}_")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Tool 5 — compare
# --------------------------------------------------------------------------- #
@mcp.tool()
def compare_sake(brand_ids: list[int]) -> str:
    """Compare 2–5 sake side by side across all six flavor axes, with the
    spread (max−min) per axis to highlight where they differ most.
    """
    ds = _ds()
    try:
        ids = [int(x) for x in brand_ids]
    except (TypeError, ValueError):
        return "brand_ids must be a list of integer ids (use search_sake to find them)."
    if not 2 <= len(ids) <= 5:
        return "Give 2–5 brand ids to compare (use search_sake to find them)."

    chosen = []
    for i in ids:
        b = ds.brand(i)
        if b is None:
            return f"No sake with id {i}."
        if not b.flavor:
            return f"'{b.name}' (id {i}) has no flavor chart, so it can't be compared."
        chosen.append(b)

    header = "| axis | " + " | ".join(f"{b.name}" for b in chosen) + " | spread |"
    sep = "|" + "---|" * (len(chosen) + 2)
    rows = [header, sep]
    for k, jp, en in flavor.AXES:
        vals = [b.flavor[k] for b in chosen]
        spread = max(vals) - min(vals)
        cells = " | ".join(f"{v:.2f}" for v in vals)
        rows.append(f"| {jp} {en} | {cells} | {spread:.2f} |")

    note = "\n".join(
        f"- **{b.name}**: {', '.join(flavor.top_tags(b.flavor))}" for b in chosen
    )
    return f"# Comparing {len(chosen)} sake\n" + "\n".join(rows) + "\n\n" + note + f"\n\n_{ATTR}_"


# --------------------------------------------------------------------------- #
# Prompt — a friendly entry point for clients that support MCP prompts
# --------------------------------------------------------------------------- #
@mcp.prompt()
def recommend_sake(taste: str = "") -> str:
    """Recommend Japanese sake matching a described taste or mood."""
    return (
        "You are a sake sommelier with the `sakenowa` tools. "
        f"The drinker wants: {taste or '(ask them what they like)'}.\n"
        "1. Use search_sake to anchor on a specific sake the drinker names. If "
        "they describe only a taste/mood with no bottle, ask them to name one "
        "sake they've enjoyed — there is no style-only search.\n"
        "2. Use find_similar_sake with an appropriate mode to expand options.\n"
        "3. Present 3 picks with their flavor tags and why they fit. "
        "Never invent polishing ratio, SMV, ABV or price — they aren't in the data."
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
