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

### 清酒風味搜尋引擎（第一個清酒 MCP）

用 AI 搜清酒的風味。輸入一支喝過的酒，找「像這支，但更乾爽」或「完全相反」的酒款。不用記牌子，用味覺找。

### 5 大功能

- 🍶 **500+ 清酒品牌** — 涵蓋完整風味檔案
- 🔍 **模糊搜尋** — 品牌名、釀造廠都能查（支援漢字、假名）
- 🎯 **風味相似度** — 找「這支的姊妹酒」或「完全相反的選擇」
- 📈 **風味探索** — 「像這支，但更乾／更濃／更輕」一句話找酒
- 📊 **並排對比** — 2~5 支酒側邊欄比較，一眼看出差異

### 快速開始

```bash
git clone https://github.com/mame0001/sakenowa-mcp.git
cd sakenowa-mcp
uv sync
uv run sakenowa-mcp
```

### 5 個工具

| 工具 | 用途 |
|------|------|
| `sync_sakenowa_data()` | 更新清酒資料庫 |
| `search_sake()` | 查品牌名、釀造廠 |
| `get_sake_profile()` | 看風味輪廓、排名 |
| `find_similar_sake()` | ★ 根據風味找相似酒 |
| `compare_sake()` | 並排對比多支酒 |

### 驗證安裝

```bash
uv run pytest -xvs
# 預期：11/11 測試通過
```

### 開發 & 架構

- [CONTRIBUTING.md](CONTRIBUTING.md) — 本地開發、提交 PR
- [ARCHITECTURE.md](ARCHITECTURE.md) — 系統設計、風味向量數學

### 開源授權

MIT License（資料源於 Sakenowa 開放資料集，CC-BY 4.0）
