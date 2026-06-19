# 清酒風味感受器 (Sakenowa MCP)
**幫你裝上數位味覺** 🍶

**[English](#english) | [正體中文](#正體中文版本)**

---

## English

### Overview

A Model Context Protocol (MCP) server that transforms the **Sakenowa Open Dataset** into a flavor-space search engine for Japanese sake. Query by name, explore six-axis flavor profiles, discover similar bottles, and compare sake side-by-side—all powered by vector mathematics in taste space.

### Key Features

- 🍶 **500+ Japanese Sake Brands** — Comprehensive coverage with flavor profiles
- 📊 **6-Axis Flavor Profiles** — Floral, Mellow, Rich, Calm, Light, Dry dimensions
- 🔍 **Fuzzy Search** — Find sake by brand name or brewery (supports kanji & kana)
- 🎯 **Smart Similarity Matching** — Discover taste-alikes or deliberate contrasts
- 📈 **Directional Flavor Exploration** — Find sake that is "like this, but drier/richer/lighter"
- 🔄 **Auto-Refresh Cache** — Weekly TTL with stale-serve fallback
- 🔒 **Multi-Process Safe** — Atomic snapshot-based caching with cross-process isolation

### Installation

```bash
git clone https://github.com/mame0001/sakenowa-mcp.git
cd sakenowa-mcp
uv sync
uv run sakenowa-mcp
```

### 5 Core Tools

| Tool | Purpose |
|------|---------|
| `sync_sakenowa_data(force=False)` | Fetch/refresh dataset; report scale & freshness |
| `search_sake(query, limit=10, area="")` | Find sake by name or brewery |
| `get_sake_profile(brand_id)` | ASCII radar, flavor tags, 4-type estimate, ranks |
| `find_similar_sake(brand_id, mode, limit=5)` | ★ Find taste-alikes by flavor vector (7 directional modes) |
| `compare_sake(brand_ids=[...])` | Side-by-side comparison (2–5 sake, 6 axes) |

### Testing

```bash
uv run pytest -xvs
# Expected: 11/11 tests pass
```

### Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and code standards.

### Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for system design, data flow, and scalability.

### Data Source & License

**Sakenowa Data Project** — https://sakenowa.com (© Sakenowa, CC-BY 4.0)

MIT License. See [LICENSE](LICENSE).

**Note:** Dataset excludes rice polishing ratio, variety, SMV, ABV, price, grade, vintage. Never invent these fields.

---

---

## 正體中文版本

### 清酒。用味覺選擇。

500 多支清酒。一個簡單的想法：輸入你喜歡的酒，找到下一支。

不用記牌子。不用查評分。用你的味覺。

### 怎麼用

**搜尋** — 找一支喝過的酒  
**探索** — 發現「像這支，但不一樣」的酒  
**對比** — 看懂清酒之間的差異  
**評比** — 看排名、看風味輪廓

### 一分鐘上手

```bash
git clone https://github.com/mame0001/sakenowa-mcp.git
cd sakenowa-mcp
uv sync && uv run sakenowa-mcp
```

### 為什麼選它

- **第一個清酒 MCP**
- **準確的風味相似度** — 向量數學驅動，找到真的「姊妹酒」
- **優雅的對比** — 並排看 2–5 支酒，一眼看出差異
- **支援中文查詢** — 品牌、釀造廠都能查

### 開發

遇到想改進的地方？  
[貢獻指南](CONTRIBUTING.md) · [系統設計](ARCHITECTURE.md)

---

MIT License
