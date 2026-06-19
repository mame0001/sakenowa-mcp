# Contributing to Sakenowa MCP

**English** | [正體中文](#正體中文版本)

Thank you for your interest in contributing! This document guides developers through setting up the project, understanding its structure, and submitting changes.

## Quick Links
- [Development Setup](#development-setup)
- [Code Structure](#code-structure)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Submitting a PR](#submitting-a-pr)
- [Coding Standards](#coding-standards)

---

## Development Setup

### Clone & Install

```bash
git clone https://github.com/mame0001/sakenowa-mcp.git
cd sakenowa-mcp
uv sync
```

### Verify Installation

```bash
uv run pytest -xvs
# Expected: 11/11 tests pass (~50ms)
```

### Run the Demo

```bash
uv run python -m sakenowa_mcp.demo
# First run: ~2-5 MB download; subsequent runs use cache
```

---

## Code Structure

```
sakenowa-mcp/
├── src/sakenowa_mcp/
│   ├── __init__.py           # Package metadata
│   ├── server.py             # MCP tools (5 tools + 1 prompt)
│   ├── data.py               # Data layer: fetch, cache, build
│   ├── search.py             # Fuzzy search: normalize, score
│   ├── flavor.py             # Vector math: 6D space, similarity
│   └── demo.py               # CLI demo
├── tests/
│   └── test_smoke.py         # 11 smoke tests
├── pyproject.toml            # Config, deps, entry point
└── README.md                 # User documentation
```

### Module Responsibilities

| Module | Purpose | Key Functions |
|--------|---------|---------------|
| `server.py` | MCP interface | `sync_sakenowa_data()`, `search_sake()`, etc. |
| `data.py` | Data persistence | `refresh()`, `build()`, `get_dataset()` |
| `search.py` | Text matching | `search()`, `normalize()`, `_score()` |
| `flavor.py` | Vector math | `vec()`, `distance()`, `shift()`, `radar()` |

---

## Making Changes

### Before You Start

1. **Check existing issues & PRs** — Avoid duplicate work
2. **Open a discussion** — For major features, discuss first
3. **Branch from `main`** — Always use latest main

### Workflow

```bash
git checkout -b fix/cache-issue
# ... make changes ...
uv run pytest -xvs
git add src/sakenowa_mcp/data.py
git commit -m "Fix: prevent cache corruption in concurrent refresh()"
git push origin fix/cache-issue
```

### Welcome Contributions

**High Priority:**
- [ ] Unit tests for backoff mechanism
- [ ] Old snapshot garbage collection
- [ ] Snapshot size monitoring

**Medium Priority:**
- [ ] Alternative similarity metrics (cosine vs Euclidean)
- [ ] Batch compare (5+ sake at once)
- [ ] Cache statistics (hit ratio, etc.)

---

## Testing

### Run Tests

```bash
uv run pytest -xvs
uv run pytest tests/test_smoke.py::test_distance_identity -v
uv run pytest --cov=src/sakenowa_mcp tests/
```

### Write Tests

```python
def test_snapshot_atomicity():
    """Verify snapshot is atomic even on crash."""
    old_snapshot = create_test_snapshot()
    refresh_with_simulated_crash()
    assert _cache_complete()  # Still valid
    assert get_dataset() == old_snapshot
```

**Guidelines:**
- Tests run offline (no real API)
- Use `SAKENOWA_CACHE_DIR` env var for isolation
- Aim for high coverage
- Keep tests fast (<100ms each)

---

## Submitting a PR

### Pre-Submission Checklist

```bash
# Tests must pass
uv run pytest -xvs

# Docstrings updated
def refresh() -> dict:
    """Fetch and atomically replace snapshot."""

# README updated if user-facing change
```

### PR Template

```markdown
## Description
What problem does this solve?

## Changes
- Bullet list of changes
- Include file & function names

## Testing
How did you test this?

## Checklist
- [ ] Tests pass (`uv run pytest -xvs`)
- [ ] Code follows PEP 8
- [ ] Docstrings updated
- [ ] README updated (if needed)
```

---

## Coding Standards

### Type Hints

```python
def build() -> Dataset:
    """Return in-memory dataset from snapshot."""
```

### Docstrings (Concise)

```python
def shift(v: list, mode: str) -> list:
    """Nudge flavor vector toward a mode (e.g. 'drier').
    
    Clamped to [0, 1] to stay in valid flavor space.
    """
```

### Comments (Only When WHY is Non-Obvious)

```python
# Good: Explain the intent, not the syntax
# Clear in-memory cache to respect TTL expiration
_DATASET = None

# Bad: Just describes what the code does
_DATASET = None  # Set to None
```

### Naming

- `_private_var` for module internals
- `CONSTANT_NAME` for immutable values
- `function_name()` for functions
- Avoid single-letter vars except loops/math

### Error Handling

```python
try:
    refresh()
except Exception as exc:
    if not _cache_complete():
        raise RuntimeError("No usable cache") from exc
    # Serve stale cache otherwise
```

---

## Running the Server

```bash
export SAKENOWA_CACHE_DIR=/custom/path
export SAKENOWA_TTL_SECONDS=604800
uv run sakenowa-mcp
```

---

## Troubleshooting

### Clean Cache Between Tests

```bash
rm -rf ~/.cache/sakenowa-mcp/
# or
export SAKENOWA_CACHE_DIR=/tmp/test-$$
uv run pytest -xvs
```

### Module Not Found

```bash
uv sync
pip install -e .
```

---

## Questions?

- **GitHub Issues** — Bug reports & feature requests
- **GitHub Discussions** — Questions & ideas

Thanks for contributing! 🍶

---

---

# 正體中文版本

## 開發貢獻指南

感謝你對本專案的興趣！本文件指導開發者完成開發環境設定、理解專案結構，以及提交程式碼貢獻。

## 快速導航
- [開發環境設定](#開發環境設定-1)
- [程式碼結構](#程式碼結構-1)
- [修改程式碼](#修改程式碼-1)
- [測試](#測試-1)
- [提交 PR](#提交-pr-1)
- [程式碼規範](#程式碼規範-1)

---

## 開發環境設定

### 複製並安裝

```bash
git clone https://github.com/mame0001/sakenowa-mcp.git
cd sakenowa-mcp
uv sync
```

### 驗證安裝

```bash
uv run pytest -xvs
# 預期：11/11 測試通過（~50ms）
```

### 執行演示

```bash
uv run python -m sakenowa_mcp.demo
# 首次：~2-5 MB 下載；後續使用快取
```

---

## 程式碼結構

```
sakenowa-mcp/
├── src/sakenowa_mcp/
│   ├── __init__.py           # 套件中繼資料
│   ├── server.py             # MCP 工具（5 工具 + 1 提示）
│   ├── data.py               # 資料層：取得、快取、構建
│   ├── search.py             # 模糊搜尋：歸一化、評分
│   ├── flavor.py             # 向量數學：6D、相似度
│   └── demo.py               # CLI 演示
├── tests/
│   └── test_smoke.py         # 11 個煙測
├── pyproject.toml            # 設定、依賴、進入點
└── README.md                 # 使用者文檔
```

### 模組責任

| 模組 | 用途 | 主要函式 |
|------|------|---------|
| `server.py` | MCP 介面 | `sync_sakenowa_data()`、`search_sake()` 等 |
| `data.py` | 資料持久化 | `refresh()`、`build()`、`get_dataset()` |
| `search.py` | 文字匹配 | `search()`、`normalize()`、`_score()` |
| `flavor.py` | 向量運算 | `vec()`、`distance()`、`shift()`、`radar()` |

---

## 修改程式碼

### 開始前

1. **檢查現有議題與 PR** — 避免重複工作
2. **開啟討論** — 大型功能先討論
3. **從 `main` 創建** — 始終使用最新 main

### 工作流程

```bash
git checkout -b fix/cache-issue
# ... 修改程式碼 ...
uv run pytest -xvs
git add src/sakenowa_mcp/data.py
git commit -m "修復：防止並發 refresh() 導致快取污損"
git push origin fix/cache-issue
```

### 歡迎貢獻的領域

**高優先度：**
- [ ] 退避機制的單元測試
- [ ] 舊快照垃圾回收
- [ ] 快照大小監控

**中等優先度：**
- [ ] 替代相似度度量（餘弦 vs 歐幾里得）
- [ ] 批量對比（5+ 支清酒）
- [ ] 快取統計（命中率等）

---

## 測試

### 執行測試

```bash
uv run pytest -xvs
uv run pytest tests/test_smoke.py::test_distance_identity -v
uv run pytest --cov=src/sakenowa_mcp tests/
```

### 撰寫測試

```python
def test_snapshot_atomicity():
    """驗證快照即使當機也是原子的。"""
    old_snapshot = create_test_snapshot()
    refresh_with_simulated_crash()
    assert _cache_complete()  # 仍有效
    assert get_dataset() == old_snapshot
```

**指南：**
- 測試離線執行（無真實 API）
- 使用 `SAKENOWA_CACHE_DIR` 環變隔離
- 力求高涵蓋率
- 保持測試快速（<100ms）

---

## 提交 PR

### 提交前檢查清單

```bash
# 測試必須通過
uv run pytest -xvs

# Docstring 已更新
def refresh() -> dict:
    """取得並原子地替換快照。"""

# README 已更新（若需）
```

### PR 模板

```markdown
## 描述
此改動解決了什麼問題？

## 改動
- 改動清單
- 包含檔案與函式名

## 測試
如何測試此改動？

## 檢查清單
- [ ] 測試通過 (`uv run pytest -xvs`)
- [ ] 程式碼遵循 PEP 8
- [ ] Docstring 已更新
- [ ] README 已更新（若需）
```

---

## 程式碼規範

### 型別提示

```python
def build() -> Dataset:
    """從快照返回記憶體內資料集。"""
```

### Docstring（簡潔）

```python
def shift(v: list, mode: str) -> list:
    """調整風味向量朝向某模式（如 'drier'）。
    
    夾鉗至 [0, 1] 以保持有效風味空間。
    """
```

### 註解（僅非明顯意圖時）

```python
# 好：說明意圖，不是語法
# 清除記憶體快取以遵守 TTL 過期
_DATASET = None

# 不好：只描述程式碼做什麼
_DATASET = None  # 設為 None
```

### 命名

- `_private_var` 用於模組內部
- `CONSTANT_NAME` 用於不可變值
- `function_name()` 用於函式
- 避免單字母變數（迴圈/數學除外）

### 錯誤處理

```python
try:
    refresh()
except Exception as exc:
    if not _cache_complete():
        raise RuntimeError("無可用快取") from exc
    # 否則提供過期快取
```

---

## 執行伺服器

```bash
export SAKENOWA_CACHE_DIR=/custom/path
export SAKENOWA_TTL_SECONDS=604800
uv run sakenowa-mcp
```

---

## 問題排除

### 測試間清理快取

```bash
rm -rf ~/.cache/sakenowa-mcp/
# 或
export SAKENOWA_CACHE_DIR=/tmp/test-$$
uv run pytest -xvs
```

### 模組未找到

```bash
uv sync
pip install -e .
```

---

## 有問題嗎？

- **GitHub Issues** — 報告 bug 與功能請求
- **GitHub Discussions** — 提問與想法

感謝貢獻！🍶
