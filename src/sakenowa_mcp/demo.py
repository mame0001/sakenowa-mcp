"""A no-LLM showcase: sync the data, then run search / profile / similarity /
compare on a few famous sake. Run with:  `uv run python -m sakenowa_mcp.demo`
"""

from __future__ import annotations

from . import server


def _print(title: str, text: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)
    print(text)


def main() -> None:
    _print("sync_sakenowa_data()", server.sync_sakenowa_data())

    # Anchor on a famously crisp Niigata sake.
    _print("search_sake('八海山')", server.search_sake("八海山", limit=3))

    ds = server._ds()
    hits = server.search.search(ds, "八海山", limit=1)
    if not hits:
        print("\n(八海山 not found — dataset may have changed)")
        return
    target = hits[0]

    _print(f"get_sake_profile({target.id})", server.get_sake_profile(target.id))
    _print(
        f"find_similar_sake({target.id}, 'similar')",
        server.find_similar_sake(target.id, "similar", 5),
    )
    _print(
        f"find_similar_sake({target.id}, 'richer')",
        server.find_similar_sake(target.id, "richer", 5),
    )

    # Compare against another well-known bottle if we can find one.
    others = server.search.search(ds, "久保田", limit=1)
    if others and others[0].flavor and target.flavor:
        _print(
            f"compare_sake([{target.id}, {others[0].id}])",
            server.compare_sake([target.id, others[0].id]),
        )


if __name__ == "__main__":
    main()
