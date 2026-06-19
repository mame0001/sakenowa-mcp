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

### 概述

一個 Model Context Protocol (MCP) 伺服器，將 **Sakenowa 開放資料集**轉化為日本清酒的風味空間搜尋引擎。按名稱查詢、探索六軸風味輪廓、發現相似酒款，並排對比清酒——全部由風味空間中的向量數學驅動。

### 核心特性

- 🍶 **500+ 日本清酒品牌** — 涵蓋完整的風味檔案資料
- 📊 **6 軸風味輪廓** — 華やか（華麗香氣）、芳醇（醇厚）、重厚（飽滿）、穏やか（溫和）、軽快（輕爽）、ドライ（乾爽）
- 🔍 **模糊搜尋** — 按品牌名或釀造廠查詢（支援漢字與假名）
- 🎯 **精準相似度搜尋** — 發現類似酒款或尋找對比選擇
- 📈 **方向性風味探索** — 找「像這支，但更乾爽／更飽滿／更輕爽」的酒
- 🔄 **自動更新快取** — 每週刷新 TTL，快取過期時自動降級服務
- 🔒 **多進程安全** — 基於原子快照的快取，具備跨進程隔離

### 安裝

```bash
git clone https://github.com/mame0001/sakenowa-mcp.git
cd sakenowa-mcp
uv sync
uv run sakenowa-mcp
```

### 5 個核心工具

| 工具 | 用途 |
|------|------|
| `sync_sakenowa_data(force=False)` | 獲取/更新資料集；報告規模與新鮮度 |
| `search_sake(query, limit=10, area="")` | 按名稱或釀造廠尋找清酒 |
| `get_sake_profile(brand_id)` | ASCII 雷達圖、風味標籤、4 分類估計、排名 |
| `find_similar_sake(brand_id, mode, limit=5)` | ★ 按風味向量尋找類似酒（7 種方向模式） |
| `compare_sake(brand_ids=[...])` | 並排對比（2–5 支清酒，6 軸） |

### 測試

```bash
uv run pytest -xvs
# 預期結果：11/11 測試通過
```

### 貢獻

參見 [CONTRIBUTING.md](CONTRIBUTING.md) 以了解開發環境設定和程式碼規範。

### 架構

參見 [ARCHITECTURE.md](ARCHITECTURE.md) 以瞭解系統設計、資料流以及擴展性考量。

### 資料來源與授權

**Sakenowa 資料專案** — https://sakenowa.com (© Sakenowa, CC-BY 4.0)

MIT 授權。詳見 [LICENSE](LICENSE)。

**備註：** 資料集不包含米拋光比、米品種、日本酒度、酒精度、價格、等級、年份。永遠不要編造這些欄位。
