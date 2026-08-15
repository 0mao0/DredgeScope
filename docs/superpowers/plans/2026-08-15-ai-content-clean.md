# AI 正文清洗（content_clean）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对每篇新闻抓取文本调用 LLM 清洗，把干净正文存入 `articles.content_clean`，并让分析、API 与前端原文展示都基于清洗结果。

**Architecture:** 数据库新增 `content_clean` 列（向后兼容迁移）；`info_analysis.py` 新增 LLM 清洗函数并在分析流程中先清洗再分析；API 三处查询返回新字段；前端详情弹窗新增“原文”区；另提供手动补跑历史文章脚本。

**Tech Stack:** Python 3.12 / SQLite / FastAPI / OpenAI SDK（阿里云 Qwen）/ Vue 3 + TypeScript / pytest

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/database.py` | 修改 | 新增 `content_clean` 列迁移、`get_articles_need_clean()`、`get_articles_by_ids()`、`update_content_clean()`；`get_articles_by_time_range_strict()` 返回新列 |
| `backend/analysis/info_analysis.py` | 修改 | 新增 `CLEAN_PROMPT`、`clean_content_with_llm()`；`process_items_from_db()` 集成清洗 |
| `backend/reporting/dashboard_server.py` | 修改 | `/api/articles`、`/api/article/{id}` 查询返回 `content_clean` |
| `frontend/src/stores/index.ts` | 修改 | `NewsItem` 增加 `content_clean` |
| `frontend/src/views/Dashboard.vue` | 修改 | 详情弹窗新增“原文”区 |
| `frontend/src/views/History.vue` | 修改 | 详情弹窗新增“原文”区 |
| `backend/scripts/clean_content_backfill.py` | 新增 | 手动批量补跑历史文章清洗 |
| `tests/test_database_content_clean.py` | 新增 | 数据库迁移/查询/回写测试 |
| `tests/test_clean_content.py` | 新增 | LLM 清洗函数测试 |
| `tests/test_process_items_clean.py` | 新增 | 分析流程集成清洗测试 |
| `tests/test_clean_content_backfill.py` | 新增 | 补跑脚本测试 |

所有 pytest 命令在仓库根目录 `D:\AI\DredgeScope` 执行。

---

### Task 1: 数据库迁移与 content_clean 查询/回写函数

**Files:**
- Modify: `backend/database.py`（`init_db()` 的 remark 列检查之后；新增三个函数放在 `get_articles_need_enrich()` 附近）
- Test: `tests/test_database_content_clean.py`

- [ ] **Step 1: 编写失败测试**

创建 `tests/test_database_content_clean.py`：

```python
# tests/test_database_content_clean.py
"""articles.content_clean 列迁移、查询与回写测试"""

import os
import shutil
import sqlite3
import sys
import uuid

import asyncio
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import database


@pytest.fixture
def db_env(monkeypatch):
    """创建临时数据库（模拟旧库，无 content_clean 列），再调用 init_db 补齐"""
    tmpdir = os.path.join(os.getcwd(), "dredge_test_" + uuid.uuid4().hex[:8])
    os.makedirs(tmpdir, exist_ok=True)
    db_file = os.path.join(tmpdir, "test_dredge.db")
    track_file = os.path.join(tmpdir, "test_tracks.db")
    monkeypatch.setattr(database, "DB_PATH", db_file)
    monkeypatch.setattr(database, "TRACK_DB_PATH", track_file)

    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            title TEXT,
            content TEXT,
            valid INTEGER DEFAULT 1,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()
    database.init_db()
    yield db_file
    shutil.rmtree(tmpdir, ignore_errors=True)


def _insert(db_file, url, content, valid=1, content_clean='', created_at='2026-08-01T00:00:00'):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute(
        "INSERT INTO articles (url, title, content, content_clean, valid, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (url, url, content, content_clean, valid, created_at),
    )
    conn.commit()
    row_id = c.lastrowid
    conn.close()
    return row_id


def test_init_db_adds_content_clean_column(db_env):
    """init_db 应给旧库补上 content_clean 列"""
    conn = sqlite3.connect(db_env)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(articles)").fetchall()]
    conn.close()
    assert 'content_clean' in cols


def test_get_articles_need_clean_filters_correctly(db_env):
    """只返回 content_clean 为空、content 非空、valid=1 的文章"""
    need_id = _insert(db_env, 'https://a.com/1', '正文内容')
    _insert(db_env, 'https://a.com/2', '旧正文', content_clean='干净正文')
    _insert(db_env, 'https://a.com/3', '无效正文', valid=0)
    _insert(db_env, 'https://a.com/4', '')

    rows = database.get_articles_need_clean(limit=10)
    assert [r['id'] for r in rows] == [need_id]
    assert rows[0]['content'] == '正文内容'


def test_get_articles_need_clean_limit(db_env):
    """limit 应生效，None 表示不限"""
    _insert(db_env, 'https://a.com/1', '正文一')
    _insert(db_env, 'https://a.com/2', '正文二')
    assert len(database.get_articles_need_clean(limit=1)) == 1
    assert len(database.get_articles_need_clean(limit=None)) == 2


def test_get_articles_by_ids(db_env):
    """按 ID 批量查询应返回对应文章"""
    id1 = _insert(db_env, 'https://a.com/1', '正文一')
    id2 = _insert(db_env, 'https://a.com/2', '正文二')
    rows = database.get_articles_by_ids([id2, id1])
    assert sorted(r['id'] for r in rows) == sorted([id1, id2])
    assert database.get_articles_by_ids([]) == []


def test_update_content_clean(db_env):
    """update_content_clean 应回写干净正文"""
    row_id = _insert(db_env, 'https://a.com/1', '原正文')
    database.update_content_clean(row_id, '清洗后的正文')
    conn = sqlite3.connect(db_env)
    value = conn.execute("SELECT content_clean FROM articles WHERE id = ?", (row_id,)).fetchone()[0]
    conn.close()
    assert value == '清洗后的正文'


def test_time_range_returns_content_clean(db_env):
    """get_articles_by_time_range_strict 应返回 content_clean 字段"""
    row_id = _insert(db_env, 'https://a.com/1', '原正文', content_clean='干净正文')
    rows = database.get_articles_by_time_range_strict('2026-08-01T00:00:00', '2026-08-02T00:00:00')
    assert any(r['id'] == row_id and r['content_clean'] == '干净正文' for r in rows)
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_database_content_clean.py -v`

Expected: FAIL —— `AttributeError: module 'database' has no attribute 'get_articles_need_clean'`

- [ ] **Step 3: 实现数据库改动**

在 `backend/database.py` 的 `init_db()` 中，`remark` 列检查块之后（`c.execute("DROP TABLE IF EXISTS events")` 之前）插入：

```python
    # 检查并添加缺失的 content_clean 列 (针对已有数据库)
    try:
        c.execute("SELECT content_clean FROM articles LIMIT 1")
    except sqlite3.OperationalError:
        print("[DB] 检测到 articles 表缺失 content_clean 列，正在添加...")
        try:
            c.execute("ALTER TABLE articles ADD COLUMN content_clean TEXT")
            print("[DB] 已成功添加 content_clean 列")
        except Exception as e:
            print(f"[DB] 添加 content_clean 列失败: {e}")
```

在 `backend/database.py` 中 `get_items_for_enrichment()` 函数之后新增：

```python
def get_articles_need_clean(limit=None):
    """获取需要 AI 正文清洗的文章（content_clean 为空且 content 非空且 valid=1）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    query = '''
        SELECT id, url, title, content, content_clean
        FROM articles
        WHERE (content_clean IS NULL OR content_clean = '')
          AND content IS NOT NULL AND content != ''
          AND valid = 1
        ORDER BY id DESC
    '''
    params = []
    if limit:
        query += " LIMIT ?"
        params.append(limit)
    c.execute(query, tuple(params))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_articles_by_ids(ids):
    """按 ID 列表批量查询文章（用于手动补跑指定文章）"""
    if not ids:
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    placeholders = ",".join("?" * len(ids))
    c.execute(f"SELECT * FROM articles WHERE id IN ({placeholders})", tuple(ids))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_content_clean(article_id, text):
    """回写 AI 清洗后的正文"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE articles SET content_clean = ? WHERE id = ?", (text, article_id))
    conn.commit()
    conn.close()
```

修改 `backend/database.py` 中 `get_articles_by_time_range_strict()` 的 SELECT，加入 `a.content_clean`：

```python
        SELECT 
            a.id, a.title, a.title_cn, a.url, a.pub_date, a.summary_cn, a.full_text_cn, a.content, 
            a.screenshot_path, a.vl_desc, a.created_at, a.source_type, a.source_name, a.valid,
            a.category, a.is_retained, a.is_significant, a.content_clean
        FROM articles a
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_database_content_clean.py -v`

Expected: PASS（6 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/database.py tests/test_database_content_clean.py
git commit -m "feat(db): articles表新增content_clean列及查询/回写函数"
```

---

### Task 2: LLM 正文清洗函数

**Files:**
- Modify: `backend/analysis/info_analysis.py`（在 `clean_article_text()` 之后新增）
- Test: `tests/test_clean_content.py`

- [ ] **Step 1: 编写失败测试**

创建 `tests/test_clean_content.py`：

```python
# tests/test_clean_content.py
"""AI 正文清洗函数测试"""

import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import config
import info_analysis


def _fake_client(return_content):
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=return_content))]
        )
    )
    return client


def test_clean_content_returns_model_output(monkeypatch):
    """清洗函数应把模型输出原样返回"""
    monkeypatch.setattr(config, "TEXT_MODEL", "test-model")
    client = _fake_client("干净正文")
    item = {"url": "https://a.com/1", "content": "第一段正文。\nSubscribe\n第二段正文。"}
    result = asyncio.run(info_analysis.clean_content_with_llm(client, item))
    assert result == "干净正文"


def test_clean_content_prefilters_noise(monkeypatch):
    """传给模型的文本应已剔除规则可识别的短冗余行"""
    monkeypatch.setattr(config, "TEXT_MODEL", "test-model")
    captured = {}

    async def fake_create(**kwargs):
        captured["prompt"] = kwargs["messages"][0]["content"]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="正文"))])

    client = AsyncMock()
    client.chat.completions.create = fake_create
    item = {"url": "https://a.com/1", "content": "真实正文第一段。\nSubscribe\n真实正文第二段。"}
    asyncio.run(info_analysis.clean_content_with_llm(client, item))
    assert "Subscribe" not in captured["prompt"]
    assert "真实正文第一段" in captured["prompt"]


def test_clean_content_short_input_skips(monkeypatch):
    """过短内容不应调用模型，返回 None"""
    monkeypatch.setattr(config, "TEXT_MODEL", "test-model")
    client = _fake_client("正文")
    result = asyncio.run(
        info_analysis.clean_content_with_llm(client, {"url": "https://a.com/1", "content": "太短"})
    )
    assert result is None
    client.chat.completions.create.assert_not_called()


def test_clean_content_exception_returns_none(monkeypatch):
    """模型调用异常应返回 None（降级）"""
    monkeypatch.setattr(config, "TEXT_MODEL", "test-model")
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))
    item = {"url": "https://a.com/1", "content": "足够长的正文内容，用来触发模型调用。"}
    result = asyncio.run(info_analysis.clean_content_with_llm(client, item))
    assert result is None
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_clean_content.py -v`

Expected: FAIL —— `AttributeError: module 'info_analysis' has no attribute 'clean_content_with_llm'`

- [ ] **Step 3: 实现清洗函数**

在 `backend/analysis/info_analysis.py` 的 `clean_article_text()` 函数之后新增：

```python
CLEAN_PROMPT = """你是新闻网页正文清洗助手。下面是从新闻网页抓取到的完整文本，可能包含导航、页眉、标签、相关新闻、订阅提示、页脚等冗余内容。

请只输出【这篇新闻的主体正文】：
1. 从报道正文第一段开始，到最后一个正文段落为止；
2. 保留作者/日期行之外的正文内容，图片说明（如“（照片由…提供）”）可以保留在对应段落位置；
3. 必须去掉标题重复、面包屑导航（如“主页”“回到总览”）、“查看帖子标签”、“分享这篇文章”、“相关新闻”、“订阅通讯”、“关注我们”及其之后的所有内容；
4. 不要翻译、不要总结、不要改写，也不要加任何解释，原样输出清洗后的正文段落。

【文本开始】
%s
【文本结束】
"""


async def clean_content_with_llm(client, item):
    """
    使用 LLM 从抓取文本中提取主体正文（去除标签/相关新闻/订阅等冗余）

    Args:
        client: AsyncOpenAI 客户端
        item: 文章字典，需包含 content

    Returns:
        清洗后的正文；内容过短或调用失败时返回 None
    """
    raw = (item.get('content') or '').strip()
    if len(raw) < 50:
        return None

    pre = clean_article_text(raw)
    if len(pre) > 12000:
        pre = pre[:12000]
    prompt = CLEAN_PROMPT % pre
    try:
        resp = await client.chat.completions.create(
            model=config.TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
        )
        content = resp.choices[0].message.content
        return content.strip() if content and content.strip() else None
    except Exception as e:
        print(f"[Text] 正文清洗失败 {item.get('url', '')}: {e}")
        return None
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_clean_content.py -v`

Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/analysis/info_analysis.py tests/test_clean_content.py
git commit -m "feat(analysis): AI正文清洗函数"
```

---

### Task 3: 分析流程集成 AI 正文清洗

**Files:**
- Modify: `backend/analysis/info_analysis.py`（`process_items_from_db()`）
- Test: `tests/test_process_items_clean.py`

- [ ] **Step 1: 编写失败测试**

创建 `tests/test_process_items_clean.py`：

```python
# tests/test_process_items_clean.py
"""分析流程集成 AI 正文清洗测试"""

import os
import sys
from unittest.mock import AsyncMock, Mock

import asyncio
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import config
import info_analysis


@pytest.fixture(autouse=True)
def _patch_config(monkeypatch):
    monkeypatch.setattr(config, "TEXT_LLM_API_KEY", "test-key")


def test_process_items_cleans_before_analysis(monkeypatch):
    """未清洗文章应先清洗、回写，再交给分析函数"""
    monkeypatch.setattr(info_analysis, "clean_content_with_llm", AsyncMock(return_value="干净正文"))
    monkeypatch.setattr(info_analysis, "analyze_item_from_db", AsyncMock(return_value={"id": 1}))
    update_mock = Mock()
    monkeypatch.setattr(info_analysis.database, "update_content_clean", update_mock)

    item = {"id": 1, "url": "https://a.com/1", "title": "标题", "content": "原始正文", "content_clean": ""}
    asyncio.run(info_analysis.process_items_from_db([item]))

    info_analysis.clean_content_with_llm.assert_awaited_once()
    update_mock.assert_called_once_with(1, "干净正文")
    called_item = info_analysis.analyze_item_from_db.await_args.args[1]
    assert called_item["content"] == "干净正文"
    assert called_item["content_clean"] == "干净正文"


def test_process_items_keeps_original_when_clean_fails(monkeypatch):
    """清洗失败应降级使用原 content，不写库"""
    monkeypatch.setattr(info_analysis, "clean_content_with_llm", AsyncMock(return_value=None))
    monkeypatch.setattr(info_analysis, "analyze_item_from_db", AsyncMock(return_value={"id": 1}))
    update_mock = Mock()
    monkeypatch.setattr(info_analysis.database, "update_content_clean", update_mock)

    item = {"id": 2, "url": "https://a.com/2", "title": "标题", "content": "原始正文", "content_clean": ""}
    asyncio.run(info_analysis.process_items_from_db([item]))

    update_mock.assert_not_called()
    called_item = info_analysis.analyze_item_from_db.await_args.args[1]
    assert called_item["content"] == "原始正文"


def test_process_items_skips_already_cleaned(monkeypatch):
    """已清洗文章不应再次调用清洗"""
    monkeypatch.setattr(info_analysis, "clean_content_with_llm", AsyncMock(return_value="干净正文"))
    monkeypatch.setattr(info_analysis, "analyze_item_from_db", AsyncMock(return_value={"id": 1}))

    item = {"id": 3, "url": "https://a.com/3", "title": "标题", "content": "原始正文", "content_clean": "已有干净正文"}
    asyncio.run(info_analysis.process_items_from_db([item]))

    info_analysis.clean_content_with_llm.assert_not_awaited()
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_process_items_clean.py -v`

Expected: FAIL —— 断言失败（当前流程不会调用清洗/回写）

- [ ] **Step 3: 实现集成**

修改 `backend/analysis/info_analysis.py` 的 `process_items_from_db()` 中 `runner`：

```python
    async def runner(item):
        async with sem:
            # AI 正文清洗：先清理冗余，再用于后续分析
            if not (item.get('content_clean') or '').strip() and (item.get('content') or '').strip():
                cleaned = await clean_content_with_llm(client, item)
                if cleaned:
                    item['content_clean'] = cleaned
                    item['content'] = cleaned
                    article_id = item.get('id')
                    if article_id:
                        try:
                            database.update_content_clean(article_id, cleaned)
                        except Exception as e:
                            print(f"[Text] 清洗结果回写失败 id={article_id}: {e}")
            res = await analyze_item_from_db(client, item)
            if res:
                # 分析完成后立即保存回数据库
                database.save_article(res)
                results.append(res)
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_process_items_clean.py -v`

Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/analysis/info_analysis.py tests/test_process_items_clean.py
git commit -m "feat(analysis): 分析流程集成AI正文清洗"
```

---

### Task 4: API 返回 content_clean

**Files:**
- Modify: `backend/reporting/dashboard_server.py`（`/api/articles` 与 `/api/article/{id}` 两处 SELECT）

- [ ] **Step 1: 修改 `/api/articles` 查询**

在 `backend/reporting/dashboard_server.py` 的 `data_query` 中，把：

```python
        SELECT 
            a.id, a.title, a.title_cn, a.pub_date, a.source_type, a.source_name,
            a.summary_cn, a.full_text_cn, a.content, a.screenshot_path, a.url, a.created_at,
            a.valid, a.category
```

改为：

```python
        SELECT 
            a.id, a.title, a.title_cn, a.pub_date, a.source_type, a.source_name,
            a.summary_cn, a.full_text_cn, a.content, a.content_clean, a.screenshot_path, a.url, a.created_at,
            a.valid, a.category
```

- [ ] **Step 2: 修改 `/api/article/{id}` 查询**

把：

```python
        SELECT id, title, title_cn, url, pub_date, summary_cn, full_text_cn, content, source_type, source_name, screenshot_path, vl_desc, created_at, valid, category
```

改为：

```python
        SELECT id, title, title_cn, url, pub_date, summary_cn, full_text_cn, content, content_clean, source_type, source_name, screenshot_path, vl_desc, created_at, valid, category
```

- [ ] **Step 3: 运行数据库层测试确认 `content_clean` 已随事件接口返回**

Run: `python -m pytest tests/test_database_content_clean.py::test_time_range_returns_content_clean -v`

Expected: PASS

- [ ] **Step 4: 冒烟验证两个 API 端点**

Run（在仓库根目录，PowerShell）：

```powershell
$env:PYTHONIOENCODING='utf-8'
python -c "import sys; sys.path.insert(0, 'backend'); import reporting.dashboard_server"
```

Expected: 无异常输出，`dashboard_server` 可导入。

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'
@'
import sys
sys.path.insert(0, r"backend")
import database
rows = database.get_articles_by_time_range_strict("2026-08-01T00:00:00", "2026-08-15T23:59:59")
print("content_clean in fields:", all("content_clean" in r for r in rows[:5]))
'@ | python -
```

Expected: `content_clean in fields: True`

- [ ] **Step 5: 提交**

```bash
git add backend/reporting/dashboard_server.py
git commit -m "feat(api): 接口返回content_clean字段"
```

---

### Task 5: 前端展示 AI 清洗后的原文

**Files:**
- Modify: `frontend/src/stores/index.ts`
- Modify: `frontend/src/views/Dashboard.vue`
- Modify: `frontend/src/views/History.vue`

- [ ] **Step 1: store 类型增加字段**

在 `frontend/src/stores/index.ts` 的 `NewsItem` 接口中，`content?: string` 之后新增：

```ts
  content_clean?: string
```

- [ ] **Step 2: Dashboard 详情弹窗新增“原文”区**

在 `frontend/src/views/Dashboard.vue` 中，`<!-- Image -->` 区块之前插入：

```html
        <!-- 清洗后原文 -->
        <div
          v-if="currentArticle?.content_clean"
          class="mt-6 bg-slate-900/50 rounded-lg p-4 border border-slate-700/50"
        >
          <h4 class="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">原文</h4>
          <div class="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
            {{ currentArticle.content_clean }}
          </div>
        </div>
```

- [ ] **Step 3: History 详情弹窗新增“原文”区**

在 `frontend/src/views/History.vue` 中，`<!-- Image -->` 区块之前插入同样的区块：

```html
        <!-- 清洗后原文 -->
        <div
          v-if="currentArticle?.content_clean"
          class="mt-6 bg-slate-900/50 rounded-lg p-4 border border-slate-700/50"
        >
          <h4 class="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">原文</h4>
          <div class="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
            {{ currentArticle.content_clean }}
          </div>
        </div>
```

- [ ] **Step 4: 类型检查**

Run（frontend 目录）:

```powershell
node .\node_modules\vue-tsc\bin\vue-tsc.js --noEmit -p tsconfig.json
```

Expected: 无输出，exit code 0

- [ ] **Step 5: 提交**

```bash
git add frontend/src/stores/index.ts frontend/src/views/Dashboard.vue frontend/src/views/History.vue
git commit -m "feat(frontend): 详情弹窗展示AI清洗后的原文"
```

---

### Task 6: 历史文章清洗补跑脚本

**Files:**
- Create: `backend/scripts/clean_content_backfill.py`
- Test: `tests/test_clean_content_backfill.py`

- [ ] **Step 1: 编写失败测试**

创建 `tests/test_clean_content_backfill.py`：

```python
# tests/test_clean_content_backfill.py
"""历史文章 AI 正文清洗补跑脚本测试"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, Mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'scripts'))

import config
import database
import clean_content_backfill


@pytest.fixture(autouse=True)
def _patch_config(monkeypatch):
    monkeypatch.setattr(config, "TEXT_LLM_API_KEY", "test-key")


def test_run_backfill_success(monkeypatch):
    """成功清洗的文章应回写并计入 cleaned"""
    items = [{"id": 1, "url": "https://a.com/1", "content": "正文"}]
    monkeypatch.setattr(database, "get_articles_need_clean", Mock(return_value=items))
    monkeypatch.setattr(
        clean_content_backfill.info_analysis,
        "clean_content_with_llm",
        AsyncMock(return_value="干净正文"),
    )
    update_mock = Mock()
    monkeypatch.setattr(database, "update_content_clean", update_mock)

    stats = asyncio.run(clean_content_backfill.run_backfill(limit=100))
    assert stats == {"total": 1, "cleaned": 1, "failed": 0}
    update_mock.assert_called_once_with(1, "干净正文")


def test_run_backfill_failure(monkeypatch):
    """清洗失败的文章应计入 failed 且不写库"""
    items = [{"id": 1, "url": "https://a.com/1", "content": "正文"}]
    monkeypatch.setattr(database, "get_articles_need_clean", Mock(return_value=items))
    monkeypatch.setattr(
        clean_content_backfill.info_analysis,
        "clean_content_with_llm",
        AsyncMock(return_value=None),
    )
    update_mock = Mock()
    monkeypatch.setattr(database, "update_content_clean", update_mock)

    stats = asyncio.run(clean_content_backfill.run_backfill(limit=100))
    assert stats == {"total": 1, "cleaned": 0, "failed": 1}
    update_mock.assert_not_called()


def test_run_backfill_uses_ids(monkeypatch):
    """指定 ids 时应走 get_articles_by_ids"""
    items = [{"id": 7, "url": "https://a.com/7", "content": "正文"}]
    by_ids = Mock(return_value=items)
    monkeypatch.setattr(database, "get_articles_by_ids", by_ids)
    monkeypatch.setattr(
        clean_content_backfill.info_analysis,
        "clean_content_with_llm",
        AsyncMock(return_value="干净正文"),
    )
    monkeypatch.setattr(database, "update_content_clean", Mock())

    stats = asyncio.run(clean_content_backfill.run_backfill(ids=[7]))
    by_ids.assert_called_once_with([7])
    assert stats["total"] == 1
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_clean_content_backfill.py -v`

Expected: FAIL —— `ModuleNotFoundError: No module named 'clean_content_backfill'`

- [ ] **Step 3: 实现脚本**

创建 `backend/scripts/clean_content_backfill.py`：

```python
"""历史文章 AI 正文清洗补跑脚本（手动执行，不纳入调度）"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import database
from analysis import info_analysis
from openai import AsyncOpenAI


async def run_backfill(limit=None, ids=None):
    """
    对未清洗文章执行 AI 正文清洗并回写

    Args:
        limit: 最多清洗篇数；None 表示不限
        ids: 指定文章 ID 列表；优先于 limit

    Returns:
        统计字典 {"total", "cleaned", "failed"}
    """
    if not config.TEXT_LLM_API_KEY:
        print("[Backfill] TEXT_LLM_API_KEY 未配置，退出")
        return {"total": 0, "cleaned": 0, "failed": 0}

    client = AsyncOpenAI(api_key=config.TEXT_LLM_API_KEY, base_url=config.TEXT_LLM_API_BASE)
    items = database.get_articles_by_ids(ids) if ids else database.get_articles_need_clean(limit=limit)
    total = len(items)
    cleaned = 0
    failed = 0
    sem = asyncio.Semaphore(3)

    async def worker(item):
        nonlocal cleaned, failed
        async with sem:
            text = await info_analysis.clean_content_with_llm(client, item)
            if text:
                database.update_content_clean(item["id"], text)
                cleaned += 1
            else:
                failed += 1

    await asyncio.gather(*(worker(item) for item in items))
    print(f"[Backfill] 共 {total} 篇，清洗成功 {cleaned}，失败/跳过 {failed}")
    return {"total": total, "cleaned": cleaned, "failed": failed}


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="历史文章 AI 正文清洗补跑")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--limit", type=int, default=100, help="最多清洗篇数（默认 100）")
    group.add_argument("--all", action="store_true", help="清洗全部未清洗文章")
    group.add_argument("--ids", type=str, default="", help="指定文章 ID，逗号分隔")
    args = parser.parse_args()

    ids = [int(x) for x in args.ids.split(",") if x.strip()] if args.ids else None
    if ids or args.all:
        limit = None
    else:
        limit = args.limit

    asyncio.run(run_backfill(limit=limit, ids=ids))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_clean_content_backfill.py -v`

Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/scripts/clean_content_backfill.py tests/test_clean_content_backfill.py
git commit -m "feat(scripts): 历史文章AI正文清洗补跑脚本"
```

---

### Task 7: 端到端验证

**Files:** 无（仅验证）

- [ ] **Step 1: 运行全部新增测试**

Run: `python -m pytest tests/test_database_content_clean.py tests/test_clean_content.py tests/test_process_items_clean.py tests/test_clean_content_backfill.py -v`

Expected: 全部 PASS

- [ ] **Step 2: 真实模型冒烟（仅 1 篇）**

Run（PowerShell，需在 `backend` 目录执行）：

```powershell
$env:PYTHONIOENCODING='utf-8'
python -m scripts.clean_content_backfill --limit 1
```

Expected: 输出 `[Backfill] 共 1 篇，清洗成功 1，失败/跳过 0`（或失败 1 也接受，说明降级正常）；随后查询数据库确认该行 `content_clean` 非空。

- [ ] **Step 3: 后端 lint 检查（仅本次新增/修改文件）**

Run:

```powershell
python -m ruff check backend/database.py backend/analysis/info_analysis.py backend/reporting/dashboard_server.py backend/scripts/clean_content_backfill.py
```

Expected: 仅出现仓库既有历史 lint 错误（如 E722/F401），不出现本次新增代码引入的新错误。

- [ ] **Step 4: 前端类型检查**

Run（frontend 目录）:

```powershell
node .\node_modules\vue-tsc\bin\vue-tsc.js --noEmit -p tsconfig.json
```

Expected: 无输出，exit code 0

- [ ] **Step 5: 确认工作区干净（除计划文档外）并总结**

Run: `git status --short`

Expected: 无未提交的本功能改动（所有功能改动已在各 Task 提交）。
