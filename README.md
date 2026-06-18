# sakenowa-mcp 🍶

> The first [Model Context Protocol](https://modelcontextprotocol.io) server for **Japanese sake (日本酒)** — a *flavor-space engine*, not an encyclopedia.

Give any MCP-capable LLM (Claude Desktop, Claude Code, …) a real sense of taste for sake. It wraps the open [**Sakenowa Data Project**](https://sakenowa.com/) dataset — **1,700+ breweries, 3,200+ sake, 1,300+ six-axis flavor charts, monthly popularity rankings** — and turns it into tools the model can reason with: search, profile, **flavor-similarity recommendation**, and side-by-side comparison.

As far as I can tell, there is **no other sake MCP server in existence** — existing "brewery" MCPs cover Western beer only. This one is built around what makes sake searchable: its flavor vector.

---

## Why this exists

Ask an LLM "find me something like 八海山" and it guesses from training data. With `sakenowa-mcp` it does the real thing: it pulls 八海山's six-axis flavor vector and returns the **nearest sake in flavor space** — and can steer the search *drier*, *lighter*, *richer*, or to the deliberate *opposite*.

The positioning, in one line:

> **Sakenowa MCP = a flavor-space engine for sake.** It does not store tasting notes or prices; it makes the *shape* of a sake's taste computable.

## The flavor model

Every rated sake has six normalized axes (0–1):

| axis | 日本語 | meaning |
|---|---|---|
| f1 | 華やか | floral & vibrant |
| f2 | 芳醇 | mellow & full-bodied |
| f3 | 重厚 | rich & heavy |
| f4 | 穏やか | calm & gentle |
| f5 | 軽快 | light & smooth |
| f6 | ドライ | dry |

## Tools

| tool | what it does |
|---|---|
| `sync_sakenowa_data(force=False)` | Fetch/refresh the dataset into a local cache; report scale & attribution. Auto-refreshes weekly. |
| `search_sake(query, limit=10, area="")` | Find sake by brand or brewery name → IDs. Kanji queries match directly; `area` filters by prefecture. |
| `get_sake_profile(brand_id)` | Six-axis ASCII radar, dominant tags, an *estimated* four-type class (薫/爽/醇/熟), popularity rank, and the spec fields the data **doesn't** contain. |
| `find_similar_sake(brand_id, mode, limit=5)` | **★ core ★** Nearest sake by flavor vector. `mode`: `similar` / `drier` / `sweeter` / `lighter` / `richer` / `more_aromatic` / `calmer` / `contrast`. |
| `compare_sake([id, id, …])` | Compare 2–5 sake across all six axes with per-axis spread. |

Plus a `recommend_sake` MCP **prompt** as a friendly entry point.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/). Python is provisioned automatically (3.10+).

```bash
git clone https://github.com/mame0001/sakenowa-mcp.git
cd sakenowa-mcp
uv sync          # create venv + install
uv run pytest    # run offline tests
```

### Add to Claude Code

```bash
claude mcp add sakenowa -- uv --directory /absolute/path/to/sakenowa-mcp run sakenowa-mcp
```

### Add to Claude Desktop

In `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "sakenowa": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/sakenowa-mcp", "run", "sakenowa-mcp"]
    }
  }
}
```

Then ask: *"Find me 3 sake similar to 久保田 but a bit drier,"* or *"Compare 八海山 and 獺祭."*

## Try it without an LLM

```bash
uv run python -m sakenowa_mcp.demo   # full showcase: sync → search → profile → similar → compare
# or a one-liner:
uv run python -c "from sakenowa_mcp import data, search; ds=data.get_dataset(); print([b.name for b in search.search(ds,'八海山',5)])"
```

## Configuration

| env var | default | meaning |
|---|---|---|
| `SAKENOWA_CACHE_DIR` | `~/.cache/sakenowa-mcp` | where the JSON snapshot is cached |
| `SAKENOWA_TTL_SECONDS` | `604800` (7 days) | how long before the cache auto-refreshes |

## Honest limitations

- **~41% flavor coverage** (≈1,335 of 3,250 sake). Tools tell you when a bottle has no chart.
- **No bottle specs.** The dataset has no polishing ratio (精米歩合), rice variety, SMV/日本酒度, acidity, ABV, price, or junmai/ginjo grade. The tools say so explicitly so the model doesn't invent them.
- **Estimated four-type class is a heuristic**, self-calibrated against the dataset median — not the official SSI sensory category.
- Names are Japanese; romaji/kana search is best-effort substring matching.

## Data & attribution

Sake data comes from the **[Sakenowa Data Project](https://sakenowa.com/)** (さけのわデータプロジェクト). It is free and permits commercial use **but requires attribution to "Sakenowa."** Every tool response includes that attribution — please keep it intact. This project is not affiliated with or endorsed by Sakenowa.

## License

Source code: **MIT** (see `LICENSE`). Sake data remains under the Sakenowa Data Project's terms.
