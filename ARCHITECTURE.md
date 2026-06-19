# Architecture Guide: Sakenowa MCP

**English** | [正體中文](#正體中文版本)

Comprehensive system design, data flow, key trade-offs, and scalability considerations.

## Table of Contents
1. [System Overview](#system-overview)
2. [Data Model](#data-model)
3. [Cache Strategy](#cache-strategy)
4. [Flavor-Space Mathematics](#flavor-space-mathematics)
5. [MCP Tool Layer](#mcp-tool-layer)
6. [Concurrency & Isolation](#concurrency--isolation)
7. [Performance & Scalability](#performance--scalability)

---

## System Overview

### Data Flow

```
Sakenowa API → [fetch] → snapshot-{ts}.json → [build] → Dataset (in-memory)
                                    ↓
                             [deserialize] → Brand, areas, medians
                                    ↓
                          Flavor-Space Search Engine
                                    ↓
                            MCP Tools (5) + Prompt (1)
                                    ↓
                              MCP Client (Claude, etc.)
```

### Components

| Component | Lines | Status |
|-----------|-------|--------|
| `data.py` | ~380 | Mature (7 bugs fixed v0.2) |
| `flavor.py` | ~135 | Stable |
| `search.py` | ~63 | Stable |
| `server.py` | ~290 | Stable (7 bugs fixed v0.2) |
| `tests/` | ~150 | 11/11 passing |

---

## Data Model

### Sakenowa Dataset (5 Endpoints)

```json
{
  "areas": [{"id": 1, "name": "新潟"}, ...],
  "breweries": [{"id": 1, "name": "...", "areaId": 1}, ...],
  "brands": [{"id": 1, "name": "八海山", "breweryId": 1}, ...],
  "flavorCharts": [{"brandId": 1, "f1": 0.42, ..., "f6": 0.71}, ...],
  "rankings": {
    "yearMonth": "2026-06",
    "overall": [{"brandId": 1, "rank": 1}, ...],
    "areas": [{"areaId": 1, "ranking": [...]}]
  }
}
```

### In-Memory Dataset

```python
@dataclass
class Brand:
    id: int
    name: str
    brewery: str        # Joined from breweries
    area: str           # Joined from areas
    flavor: Optional[dict]  # {"f1": 0.42, ..., "f6": 0.71}
    overall_rank: Optional[int]
    area_rank: Optional[int]

@dataclass
class Dataset:
    meta: dict
    areas: dict         # area_id → name
    breweries: dict     # brewery_id → record
    brands: dict        # brand_id → Brand (denormalized)
    medians: dict       # {"aroma": 0.5, "body": 0.4}
```

### Why Denormalize?

- Single `Brand` object has all relevant fields
- No joins needed during search (fast)
- Smaller memory footprint (all in one dict)

Trade-off: Requires careful validation on load (see `build()` guards).

---

## Cache Strategy

### Problem (v0.1)

```
refresh() wrote 5 separate files:
  os.replace(areas.json)       ✓
  os.replace(brands.json)      ✓
  [CRASH]
  os.replace(flavor_charts.json)  ✗
→ Cache has new areas + brands, old flavor = type mismatch
```

### Solution (v0.2)

```
Single atomic operation:
  os.replace(snapshot-{timestamp}.json)  ✓
→ Either all new or all old; never mixed
```

### Lifecycle

```
Day 1, 08:00  → write snapshot-1718838300/, update meta.json pointer
Day 1, 09:00  → query: return from _DATASET (in-memory, ~1ms)
Day 8, 08:00  → TTL expired: try refresh()
               → [success] write new snapshot, reload _DATASET
               → [failure] _cache_complete() = true: serve stale + backoff 5min
Day 8, 08:06  → query: serve stale (skip network for 5min)
```

### TTL & Backoff

| Setting | Default | Purpose |
|---------|---------|---------|
| TTL | 7 days | Sakenowa updates ~monthly |
| BACKOFF | 5 min | Avoid hammering API during outages |

---

## Flavor-Space Mathematics

### 6-Axis Space

```
f1 (華やか) = Floral & vibrant      [0.0 — 1.0]
f2 (芳醇)   = Mellow & full         [0.0 — 1.0]
f3 (重厚)   = Rich & heavy          [0.0 — 1.0]
f4 (穏やか) = Calm & gentle         [0.0 — 1.0]
f5 (軽快)   = Light & smooth        [0.0 — 1.0]
f6 (ドライ) = Dry                   [0.0 — 1.0]
```

Example: 八海山 = `[0.42, 0.39, 0.28, 0.61, 0.65, 0.71]`

### Core Operations

#### Distance (Euclidean)
```python
distance(a, b) = sqrt(sum((x - y)² for x, y in zip(a, b)))
```

Used for: Finding nearest neighbors in taste space.

#### Directional Shifts
```
drier:         boost f6 (+0.20), reduce f2 (-0.10)
lighter:       boost f5 (+0.20), reduce f3 (-0.15)
more_aromatic: boost f1 (+0.25), reduce f4 (-0.15)
contrast:      flip all around 0.5 (opposite palate)
```

#### Four-Type Classification (Heuristic)
```
aroma = f1 (華やか) - f4 (穏やか)
body  = (f2 + f3) / 2 - f5 (軽快)

Quadrants:
  High aroma, low body  → 薫酒 (Kunshu)
  Low aroma, low body   → 爽酒 (Soshu)
  Low aroma, high body  → 醇酒 (Junshu)
  High aroma, high body → 熟酒 (Jukushu)
```

**Note:** Experimental; not official SSI classification.

---

## MCP Tool Layer

### Tool 1: sync_sakenowa_data(force=False)

Fetch/refresh dataset; report scale & freshness.

```
Input: force (bool)
Output: Markdown with counts, coverage%, attribution
```

### Tool 2: search_sake(query, limit=10, area="")

Find sake by name.

```
Algorithm:
  1. Normalize: NFKC, lowercase, strip
  2. Score: exact (100), prefix (85), substring (70), fuzzy (24-40)
  3. Sort: (score, has_flavor, overall_rank)
  4. Return top limit
```

### Tool 3: get_sake_profile(brand_id)

Show full flavor profile.

```
Output: ASCII radar, tags, 4-type estimate, ranks,
        list of missing fields (no hallucination)
```

### Tool 4: find_similar_sake(brand_id, mode, limit=5)

**★ Core feature ★** Find taste-alikes by flavor vector.

```
Modes: similar | drier | sweeter | lighter | richer |
       more_aromatic | calmer | contrast

Algorithm:
  1. Get v_base = flavor vector
  2. Compute v_target (shift or contrast)
  3. For each other sake: score = 1.0 - distance / sqrt(6)
  4. Return top limit
```

### Tool 5: compare_sake(brand_ids)

Side-by-side comparison (2–5 sake).

```
Output: Markdown table (6 rows × N cols)
        + spread (max - min) per axis
        + flavor tags per sake
```

---

## Concurrency & Isolation

### Multi-Process Isolation

**Problem (v0.1):** Fixed `.tmp` directory collides when two workers refresh simultaneously.

**Solution (v0.2):** `tempfile.mkdtemp()` per refresh

```python
# Each process gets unique dir:
temp_dir = Path(tempfile.mkdtemp(dir=cdir, prefix="snapshot-"))
# → snapshot-abc123/, snapshot-def456/
```

### In-Process Locking

```python
_LOCK = threading.RLock()

def get_dataset() -> Dataset:
    global _DATASET
    with _LOCK:
        # Serialize concurrent get_dataset() calls
        ...
```

### Read-Write Consistency

Single snapshot file ensures readers see either old or new, never mixed.

---

## Performance & Scalability

### Memory Footprint

```
Typical dataset (May 2026):
  - Areas:     ~5 KB
  - Breweries: ~150 KB
  - Brands:    ~2 MB (denormalized)
  - Flavor:    ~300 KB
  Total:       ~2.5 MB (compressed: ~400 KB)
```

### Request Latency

```
Cold start:   ~150s (network-bound)
Warm cache:   ~10 ms (CPU-bound)
Stale cache:  ~10 ms (return in-memory)
```

### Scalability

Current design handles ~10,000 brands easily.
For 100K+ brands:
- Memory: ~20 MB (manageable)
- Build time: ~500 ms
- Search: O(n) = ~50 ms

Future optimizations: lazy load, bloom filter, ANN.

---

## Recent Improvements (v0.2)

✅ Atomic snapshot replacement (prevents multi-process corruption)  
✅ Backoff mechanism (prevents network hammering)  
✅ Schema validation (catches malformed cache)  
✅ Type-safe row handling (8 isinstance() guards)  
✅ Markdown table escaping (handles special chars)

---

---

# 正體中文版本

## 架構指南：清酒風味感受器

完整的系統設計、資料流、主要權衡以及可擴展性考量。

## 目錄
1. [系統概述](#系統概述)
2. [資料模型](#資料模型)
3. [快取策略](#快取策略)
4. [風味空間數學](#風味空間數學)
5. [MCP 工具層](#mcp-工具層)
6. [並發與隔離](#並發與隔離)
7. [效能與擴展性](#效能與擴展性)

---

## 系統概述

### 資料流

```
Sakenowa API → [取得] → snapshot-{ts}.json → [構建] → Dataset（記憶體內）
                                ↓
                         [反序列化] → Brand、區域、中位數
                                ↓
                      風味空間搜尋引擎
                                ↓
                        MCP 工具（5）+ 提示（1）
                                ↓
                          MCP 客戶端（Claude 等）
```

### 組件

| 組件 | 行數 | 狀態 |
|------|------|------|
| `data.py` | ~380 | 成熟（v0.2 修固 7 bug） |
| `flavor.py` | ~135 | 穩定 |
| `search.py` | ~63 | 穩定 |
| `server.py` | ~290 | 穩定（v0.2 修固 7 bug） |
| `tests/` | ~150 | 11/11 通過 |

---

## 資料模型

### Sakenowa 資料集（5 個端點）

```json
{
  "areas": [{"id": 1, "name": "新潟"}, ...],
  "breweries": [{"id": 1, "name": "...", "areaId": 1}, ...],
  "brands": [{"id": 1, "name": "八海山", "breweryId": 1}, ...],
  "flavorCharts": [{"brandId": 1, "f1": 0.42, ..., "f6": 0.71}, ...],
  "rankings": {
    "yearMonth": "2026-06",
    "overall": [{"brandId": 1, "rank": 1}, ...],
    "areas": [{"areaId": 1, "ranking": [...]}]
  }
}
```

### 記憶體內資料集

```python
@dataclass
class Brand:
    id: int
    name: str
    brewery: str        # 從 breweries 聯接
    area: str           # 從 areas 聯接
    flavor: Optional[dict]  # {"f1": 0.42, ..., "f6": 0.71}
    overall_rank: Optional[int]
    area_rank: Optional[int]

@dataclass
class Dataset:
    meta: dict
    areas: dict         # area_id → name
    breweries: dict     # brewery_id → 記錄
    brands: dict        # brand_id → Brand（非正規化）
    medians: dict       # {"aroma": 0.5, "body": 0.4}
```

### 為何非正規化？

- 單一 `Brand` 物件包含所有相關欄位
- 搜尋期間無需聯接（快速）
- 記憶體佔用較小（全在一個字典內）

權衡：需精心驗證（見 `build()` 防守）。

---

## 快取策略

### 問題（v0.1）

```
refresh() 寫 5 個分散檔案：
  os.replace(areas.json)       ✓
  os.replace(brands.json)      ✓
  [當機]
  os.replace(flavor_charts.json)  ✗
→ 快取有新 areas + brands，舊 flavor = 型別混合
```

### 解決方案（v0.2）

```
單一原子操作：
  os.replace(snapshot-{timestamp}.json)  ✓
→ 要麼全新，要麼全舊；永不混合
```

### 生命週期

```
第 1 天 08:00 → 寫 snapshot-1718838300/、更新 meta.json 指標
第 1 天 09:00 → 查詢：從 _DATASET 返回（記憶體，~1ms）
第 8 天 08:00 → TTL 過期：嘗試 refresh()
              → [成功] 寫新快照、重新載入 _DATASET
              → [失敗] _cache_complete() = true：提供 stale + 退避 5分鐘
第 8 天 08:06 → 查詢：提供 stale（5 分鐘內略過網路）
```

### TTL 與退避

| 設定 | 預設 | 用途 |
|------|------|------|
| TTL | 7 天 | Sakenowa 約月更新 |
| BACKOFF | 5 分鐘 | 故障時避免轟炸 API |

---

## 風味空間數學

### 6 軸空間

```
f1 (華やか) = 華麗香氣           [0.0 — 1.0]
f2 (芳醇)   = 醇厚香氣           [0.0 — 1.0]
f3 (重厚)   = 飽滿厚重           [0.0 — 1.0]
f4 (穏やか) = 溫和寧靜           [0.0 — 1.0]
f5 (軽快)   = 輕爽順暢           [0.0 — 1.0]
f6 (ドライ) = 乾爽度             [0.0 — 1.0]
```

範例：八海山 = `[0.42, 0.39, 0.28, 0.61, 0.65, 0.71]`

### 核心運算

#### 距離（歐幾里得）
```python
distance(a, b) = sqrt(sum((x - y)² for x, y in zip(a, b)))
```

用於：在品味空間中尋找最近鄰。

#### 方向性平移
```
乾爽：      提升 f6 (+0.20)、降低 f2 (-0.10)
輕爽：      提升 f5 (+0.20)、降低 f3 (-0.15)
更香：      提升 f1 (+0.25)、降低 f4 (-0.15)
對比：      翻轉所有軸，圍繞 0.5（對面風味）
```

#### 四分類估計（啟發式）
```
香氣 = f1 (華やか) - f4 (穏やか)
飽滿 = (f2 + f3) / 2 - f5 (軽快)

象限：
  高香 + 低飽 → 薫酒 (Kunshu)
  低香 + 低飽 → 爽酒 (Soshu)
  低香 + 高飽 → 醇酒 (Junshu)
  高香 + 高飽 → 熟酒 (Jukushu)
```

**備註：** 實驗性；非官方 SSI 分類。

---

## MCP 工具層

### 工具 1：sync_sakenowa_data(force=False)

獲取/更新資料集；報告規模與新鮮度。

```
輸入：force (bool)
輸出：包含計數、覆蓋率%、標示的 Markdown
```

### 工具 2：search_sake(query, limit=10, area="")

按名稱尋找清酒。

```
演算法：
  1. 歸一化：NFKC、小寫、剪除
  2. 評分：完全 (100)、字首 (85)、子字串 (70)、模糊 (24-40)
  3. 排序：(score, has_flavor, overall_rank)
  4. 返回前 limit 個
```

### 工具 3：get_sake_profile(brand_id)

顯示完整風味檔案。

```
輸出：ASCII 雷達圖、標籤、4 分類估計、排名、
      缺失欄位清單（無幻想）
```

### 工具 4：find_similar_sake(brand_id, mode, limit=5)

**★ 核心特性 ★** 按風味向量尋找類似酒。

```
模式：similar | drier | sweeter | lighter | richer |
      more_aromatic | calmer | contrast

演算法：
  1. 取 v_base = 風味向量
  2. 計算 v_target（平移或對比）
  3. 對每支其他酒：score = 1.0 - distance / sqrt(6)
  4. 返回前 limit 個
```

### 工具 5：compare_sake(brand_ids)

並排對比（2–5 支清酒）。

```
輸出：Markdown 表格（6 列 × N 欄）
      + 每軸落差（max - min）
      + 每支酒的風味標籤
```

---

## 並發與隔離

### 多進程隔離

**問題（v0.1）：** 固定 `.tmp` 目錄在兩 worker 同時刷新時衝突。

**解決方案（v0.2）：** 每次刷新使用 `tempfile.mkdtemp()`

```python
# 每個 process 取得唯一目錄：
temp_dir = Path(tempfile.mkdtemp(dir=cdir, prefix="snapshot-"))
# → snapshot-abc123/、snapshot-def456/
```

### 進程內鎖定

```python
_LOCK = threading.RLock()

def get_dataset() -> Dataset:
    global _DATASET
    with _LOCK:
        # 序列化並發 get_dataset() 呼叫
        ...
```

### 讀寫一致性

單一快照檔案確保讀者看到要麼舊、要麼新，永不混合。

---

## 效能與擴展性

### 記憶體佔用

```
典型資料集（2026 年 5 月）：
  - 區域：   ~5 KB
  - 釀造廠：~150 KB
  - 品牌：  ~2 MB（非正規化）
  - 風味：  ~300 KB
  總計：    ~2.5 MB（壓縮：~400 KB）
```

### 請求延遲

```
冷啟動：  ~150s（網路約束）
暖快取：  ~10 ms（CPU 約束）
過期快取：~10 ms（返回記憶體）
```

### 擴展性

目前設計輕鬆處理 ~10,000 品牌。
若達 100K+ 品牌：
- 記憶體：~20 MB（可管理）
- 構建時間：~500 ms
- 搜尋：O(n) = ~50 ms

未來優化：懶載、布隆篩選器、近似最近鄰。

---

## 最新改善（v0.2）

✅ 原子快照替換（防止多進程污損）  
✅ 退避機制（防止網路轟炸）  
✅ 架構驗證（捕捉異常快取）  
✅ 型別安全行處理（8 個 isinstance() 防守）  
✅ Markdown 表格轉義（處理特殊字元）
