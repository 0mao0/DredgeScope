# 企业微信推送改版实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把每日企业微信推送从单张总结卡片改为「汇总卡片 + 3~5 条 AI 打分的重要新闻列表」，每条新闻可直达系统详情弹窗。

**Architecture:** 分析阶段在现有 LLM 提示词中新增 significance 打分并写入数据库已有的 `is_significant` 列；推送阶段构造两条消息（template_card 汇总卡片 + news 新闻列表），前端支持 `?id=` 直达打开现有详情弹窗。所有 payload 构造为纯函数，与 HTTP 发送分离，便于单测。

**Tech Stack:** Python 3 / FastAPI / SQLite / 企业微信机器人 Webhook / Vue 3 + TypeScript + Pinia + Vue Router

---

## 文件结构

| 文件 | 责任 |
|------|------|
| `backend/config.py` | 新增 `PUSH_BASE_URL`（默认回退 `BACKEND_URL`） |
| `backend/analysis/info_analysis.py` | 重要度分数归一化、文本/视觉提示词打分与解析 |
| `backend/database.py` | 时间窗口查询返回 `significance` |
| `backend/reporting/wecom_push.py` | 汇总卡片、新闻列表、降级消息构造与主流程接线 |
| `frontend/src/views/Dashboard.vue` | `?id=` 直达打开详情弹窗 |
| `README.md` | 环境变量文档补充 `PUSH_BASE_URL` |
| `tests/test_significance.py` | 打分解析与归一化测试 |
| `tests/test_wecom_payload.py` | 推送 payload 构造测试 |
| `tests/test_database_significance.py` | 数据库查询返回 significance 测试 |

设计规格：[2026-08-13-wecom-push-redesign-design.md](../specs/2026-08-13-wecom-push-redesign-design.md)

---

### Task 1: 新增 PUSH_BASE_URL 配置

**Files:**
- Modify: `backend/config.py`（`BACKEND_URL` 定义之后）
- Modify: `README.md`（环境变量说明段落，`WECOM_WEBHOOK_URL` 附近）

- [ ] **Step 1: 修改 `backend/config.py`**

在 `BACKEND_URL = os.getenv(...)` 这一行后面新增：

```python
# Webhook 推送跳转链接的公共地址（后续接 HTTPS 域名时只需改这里）
PUSH_BASE_URL = os.getenv("PUSH_BASE_URL") or BACKEND_URL
```

- [ ] **Step 2: 修改 `README.md`**

在环境变量说明中找到 `WECOM_WEBHOOK_URL=your_webhook` 相关行，追加：

```text
PUSH_BASE_URL=https://your-domain.com   # 可选：推送消息里的跳转链接地址，默认取 WISEFLOW_BACKEND_URL
```

- [ ] **Step 3: 验证配置可导入且默认回退**

Run: `python -c "import sys; sys.path.insert(0, 'backend'); import config; assert config.PUSH_BASE_URL == config.BACKEND_URL; print('OK')"`

Expected: 输出 `OK`，无异常。

- [ ] **Step 4: 提交**

```bash
git add backend/config.py README.md
git commit -m "feat: 推送跳转链接支持 PUSH_BASE_URL 配置"
```

---

### Task 2: 分析层——重要度分数归一化与文本提示词

**Files:**
- Create: `tests/test_significance.py`
- Modify: `backend/analysis/info_analysis.py`

- [ ] **Step 1: 写失败测试**

新建 `tests/test_significance.py`，内容如下：

```python
# tests/test_significance.py
"""重要度打分解析与归一化测试"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from analysis.info_analysis import _normalize_llm_result, normalize_significance


def test_normalize_significance_valid():
    """整数与数字字符串都归一化为 0-10 整数"""
    assert normalize_significance(8) == 8
    assert normalize_significance("6") == 6


def test_normalize_significance_clamps():
    """越界分数被限制在 0-10"""
    assert normalize_significance(15) == 10
    assert normalize_significance(-3) == 0


def test_normalize_significance_invalid():
    """非法输入返回 None"""
    assert normalize_significance("abc") is None
    assert normalize_significance(None) is None


def test_normalize_llm_result_keeps_significant():
    """文本分析结果中的 significance 被归一化到 significant 字段"""
    result = _normalize_llm_result(
        {"is_junk": False, "category": "Bid", "significance": 9},
        {"title": "Test", "pub_date": "2026-08-13"},
    )
    assert result["significant"] == 9


def test_normalize_llm_result_missing_significance():
    """模型漏打分时 significant 为 None，不强制给分"""
    result = _normalize_llm_result(
        {"is_junk": False, "category": "Bid"},
        {"title": "Test", "pub_date": "2026-08-13"},
    )
    assert result["significant"] is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_significance.py -v`

Expected: FAIL，`ImportError: cannot import name 'normalize_significance'`。

- [ ] **Step 3: 在 `info_analysis.py` 中新增归一化函数**

先清理一个存量未使用导入：把文件顶部的：

```python
from static.constants import (
    DEFAULT_CATEGORY,
    ALLOWED_CATEGORIES,
    normalize_category
)
```

改为：

```python
from static.constants import (
    DEFAULT_CATEGORY,
    normalize_category
)
```

在 `_clean_vl_description` 函数之后、`analyze_with_vl` 之前插入：

```python
def normalize_significance(value):
    """将 LLM 返回的重要度分数归一化为 0-10 整数，缺失或非法返回 None"""
    if value is None:
        return None
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(10, score))
```

- [ ] **Step 4: 替换 `_normalize_llm_result` 为完整新版本**

找到现有的 `_normalize_llm_result(result, item)` 函数（以 `def _normalize_llm_result` 开头、到下一个 `def` 之前结束），整体替换为：

```python
def _normalize_llm_result(result, item):
    """归一化 LLM 分析结果，保证必填字段与重要度分数类型一致"""
    if isinstance(result, list):
        if len(result) == 1 and isinstance(result[0], dict):
            result = result[0]
        else:
            return {
                "is_junk": False,
                "category": "Market",
                "title_cn": item.get("title"),
                "summary_cn": "",
                "full_text_cn": "",
                "publish_time": str(item.get("pub_date") or ""),
                "image_desc": "",
                "significant": None,
            }

    if isinstance(result, dict):
        return {
            "is_junk": result.get("is_junk", False),
            "category": result.get("category", "Market"),
            "title_cn": result.get("title_cn", item.get("title", "")),
            "summary_cn": result.get("summary_cn", ""),
            "full_text_cn": result.get("full_text_cn", ""),
            "publish_time": result.get("publish_time", str(item.get("pub_date") or "")),
            "image_desc": result.get("image_desc", ""),
            "significant": normalize_significance(result.get("significance")),
        }

    return {
        "is_junk": False,
        "category": "Market",
        "title_cn": item.get("title"),
        "summary_cn": "",
        "full_text_cn": "",
        "publish_time": str(item.get("pub_date") or ""),
        "image_desc": "",
        "significant": None,
    }
```

- [ ] **Step 5: 修改 `analyze_with_text` 提示词**

在 `analyze_with_text` 的 `filter_prompt` 中做两处修改：

1. 在 JSON 示例里 `"publish_time": "YYYY-MM-DD"` 行后新增一行：

```python
  "significance": 8
```

2. 在 JSON 示例块结束（`"""` 所在行）之前插入打分规则：

```python
5. 【重要度打分】(significance) - 基于以下标准输出 0-10 的整数，数字越大越重要：
   - 与疏浚、港口、航道、海洋工程的直接相关度（相关度越高分越高）；
   - 商业价值：中标、合同、金额、大型企业动态（金额越大、企业越知名分越高）；
   - 影响范围：国家级/区域级项目、法规政策变化、重大事故或里程碑；
   - 时效性：新发布、正在进行的重大事件优先。
   只输出整数，不要输出小数或理由。
```

- [ ] **Step 6: 修改 `_build_final_result` 携带 significant**

做三处修改：

1. 明显垃圾标题的提前返回字典（`if is_obvious_junk(item.get('title')):` 内的 `return {...}`）中，在 `"id": item.get("id")` 前新增：

```python
            "significant": 0,
```

2. "全部失败或判定为 Junk" 分支的返回字典中，在 `"id": item.get("id")` 前新增：

```python
            "significant": 0,
```

3. 函数末尾最终返回字典中，在 `"id": item.get("id")` 前新增：

```python
        "significant": final_result.get("significant"),
```

- [ ] **Step 7: 运行测试确认通过**

Run: `python -m pytest tests/test_significance.py -v`

Expected: PASS，5 个测试全部通过。

- [ ] **Step 8: Ruff 检查**

Run: `ruff check backend/analysis/info_analysis.py --ignore E402,F541`

Expected: 无错误输出，退出码 0（`--ignore` 仅用于放行项目既有的 sys.path 导入模式 E402 和 VL 提示词 f-string F541，F541 将在 Task 3 修复）。

- [ ] **Step 9: 提交**

```bash
git add tests/test_significance.py backend/analysis/info_analysis.py
git commit -m "feat(analysis): 文本分析增加重要度打分与归一化"
```

---

### Task 3: 分析层——视觉分析第 7 行重要度解析

**Files:**
- Modify: `tests/test_significance.py`
- Modify: `backend/analysis/info_analysis.py`

- [ ] **Step 1: 追加失败测试**

在 `tests/test_significance.py` 末尾追加：

```python
from analysis.info_analysis import parse_vl_significance


def test_parse_vl_significance_plain():
    """标准输出行 '7. 8' 解析为 8"""
    assert parse_vl_significance("7. 8") == 8


def test_parse_vl_significance_labeled():
    """带标签输出 '7. 重要度打分：7' 解析为 7"""
    assert parse_vl_significance("7. 重要度打分：7") == 7


def test_parse_vl_significance_missing():
    """没有第 7 行时返回 None"""
    assert parse_vl_significance("6. 页面截图描述：新闻页面") is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_significance.py -k "parse_vl" -v`

Expected: FAIL，`ImportError: cannot import name 'parse_vl_significance'`。

- [ ] **Step 3: 新增 `parse_vl_significance` 函数**

在 `normalize_significance` 函数之后插入：

```python
def parse_vl_significance(content):
    """从 VL 自然语言输出中解析第 7 行重要度分数（0-10 整数）"""
    if not content:
        return None
    import re
    match = re.search(r'^7\.\s*(?:[^\n]*?)(\d{1,2})\s*$', content, re.MULTILINE)
    if not match:
        return None
    return normalize_significance(match.group(1))
```

- [ ] **Step 4: 修改 `analyze_with_vl` 提示词**

在 `analyze_with_vl` 的 `vl_prompt` 中做三处修改：

1. `请输出以下6行：` 改为 `请输出以下7行：`；
2. 在第 6 行（截图内容描述）之后新增一行：

```text
7. 重要度打分：只输出 0-10 的整数，数字越大越重要
```

3. 在格式示例中，`6. 网页截图显示...` 示例行之后新增示例行：

```text
7. 8
```

4. 该 `vl_prompt` 字符串没有占位符，顺手把 `vl_prompt = f"""` 改为 `vl_prompt = """`（修复存量 F541 告警，内容不变）。

- [ ] **Step 5: 修改 `analyze_with_vl` 解析逻辑**

1. 在 `result = {...}` 默认字典中新增键（放在 `"image_desc": ""` 后面）：

```python
            "significant": None,
```

2. 在 image_desc 解析代码（`# 提取 image_desc` 块）之后新增：

```python
        # 提取 significant - 查找"7."开头的行
        result["significant"] = parse_vl_significance(content)
```

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m pytest tests/test_significance.py -v`

Expected: PASS，全部测试通过。

- [ ] **Step 7: Ruff 检查**

Run: `ruff check backend/analysis/info_analysis.py --ignore E402`

Expected: 无错误输出，退出码 0。

- [ ] **Step 8: 提交**

```bash
git add tests/test_significance.py backend/analysis/info_analysis.py
git commit -m "feat(analysis): 视觉分析增加重要度打分解析"
```

---

### Task 4: 数据库查询返回 significance

**Files:**
- Create: `tests/test_database_significance.py`
- Modify: `backend/database.py`

- [ ] **Step 1: 写失败测试**

新建 `tests/test_database_significance.py`：

```python
# tests/test_database_significance.py
"""时间窗口查询返回 significance 字段测试"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import database


def test_get_articles_by_time_range_strict_returns_significance(tmp_path, monkeypatch):
    """查询结果同时包含 is_significant 与 significance 字段"""
    db_file = tmp_path / "test_dredge.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_file))

    conn = sqlite3.connect(str(db_file))
    c = conn.cursor()
    c.execute('''
        CREATE TABLE articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT, title TEXT, title_cn TEXT, pub_date TEXT,
            source_type TEXT, source_name TEXT, summary_cn TEXT,
            full_text_cn TEXT, content TEXT, screenshot_path TEXT,
            vl_desc TEXT, created_at TEXT, valid INTEGER DEFAULT 1,
            category TEXT, is_hidden INTEGER DEFAULT 0,
            is_retained INTEGER DEFAULT 0, is_significant INTEGER
        )
    ''')
    c.execute(
        "INSERT INTO articles (title, title_cn, summary_cn, created_at, valid, category, is_retained, is_significant) "
        "VALUES (?, ?, ?, ?, 1, 'Bid', 1, ?)",
        ("Test", "测试", "摘要", "2026-08-13T07:00:00", 7),
    )
    conn.commit()
    conn.close()

    articles = database.get_articles_by_time_range_strict(
        "2026-08-13T06:00:00", "2026-08-13T08:00:00", is_retained=1
    )
    assert len(articles) == 1
    assert articles[0]["significance"] == 7
    assert articles[0]["is_significant"] == 7
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_database_significance.py -v`

Expected: FAIL，`KeyError: 'significance'`。

- [ ] **Step 3: 修改 `get_articles_by_time_range_strict` 的 SELECT**

把 SELECT 最后一列从：

```python
            a.category, a.is_retained
```

改为：

```python
            a.category, a.is_retained, a.is_significant
```

- [ ] **Step 4: 修改返回字典映射**

把结果循环：

```python
    for row in rows:
        item = dict(row)
        category = item.get("category")
        item["categories"] = [category] if category else []
        results.append(item)
```

改为：

```python
    for row in rows:
        item = dict(row)
        category = item.get("category")
        item["categories"] = [category] if category else []
        item["significance"] = item.get("is_significant")
        results.append(item)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_database_significance.py -v`

Expected: PASS。

- [ ] **Step 6: Ruff 检查**

Run: `ruff check backend/database.py`

Expected: 无错误输出，退出码 0。

- [ ] **Step 7: 提交**

```bash
git add tests/test_database_significance.py backend/database.py
git commit -m "feat(database): 时间窗口查询返回 significance 字段"
```

---

### Task 5: 推送层——新增 payload 构造纯函数

**Files:**
- Create: `tests/test_wecom_payload.py`
- Modify: `backend/reporting/wecom_push.py`

- [ ] **Step 1: 写失败测试**

新建 `tests/test_wecom_payload.py`：

```python
# tests/test_wecom_payload.py
"""企业微信推送 payload 构造测试"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from reporting.wecom_push import (
    CATEGORY_PRIORITY,
    build_markdown_fallback,
    build_news_payload,
    build_push_messages,
    build_summary_card_payload,
    rank_articles_for_push,
    truncate_for_wecom,
)


def make_article(article_id, category="Bid", significance=5, created_at="2026-08-13T07:00:00"):
    """构造测试文章字典"""
    return {
        "id": article_id,
        "title": f"Title {article_id}",
        "title_cn": f"中文标题{article_id}",
        "summary_cn": f"摘要{article_id}",
        "category": category,
        "significance": significance,
        "created_at": created_at,
    }


def test_rank_articles_by_significance():
    """分数高的在前，未打分的排最后"""
    articles = [
        make_article(1, significance=3, created_at="2026-08-13T08:00:00"),
        make_article(2, significance=9, created_at="2026-08-13T07:00:00"),
        make_article(3, significance=None, created_at="2026-08-13T09:00:00"),
    ]
    result = rank_articles_for_push(articles, max_items=5)
    assert [a["id"] for a in result] == [2, 1, 3]


def test_rank_tiebreak_by_category_priority():
    """同分时按分类优先级排序（Bid 优先于 Project）"""
    articles = [
        make_article(1, category="Project", significance=5),
        make_article(2, category="Bid", significance=5),
    ]
    result = rank_articles_for_push(articles, max_items=5)
    assert [a["id"] for a in result] == [2, 1]
    assert CATEGORY_PRIORITY.index("Bid") < CATEGORY_PRIORITY.index("Project")


def test_rank_limits_to_max_items():
    """最多返回 max_items 条"""
    articles = [make_article(i, significance=10 - i) for i in range(1, 8)]
    result = rank_articles_for_push(articles, max_items=5)
    assert len(result) == 5


def test_build_news_payload_structure():
    """news 消息含新闻条目与查看全部，不含图片字段"""
    articles = [make_article(1), make_article(2)]
    payload = build_news_payload(articles, "https://example.com", total_count=2)
    assert payload["msgtype"] == "news"
    items = payload["news"]["articles"]
    assert len(items) == 3
    assert items[0]["url"] == "https://example.com/?id=1"
    assert "picurl" not in items[0]
    assert items[-1]["title"] == "查看全部 2 条 →"


def test_build_news_payload_empty_returns_none():
    """没有可推送文章时返回 None"""
    assert build_news_payload([], "https://example.com", total_count=0) is None


def test_truncate_for_wecom():
    """超长文本按字符截断并以省略号结尾"""
    assert truncate_for_wecom("短文本", 40) == "短文本"
    long_text = "中" * 50
    assert len(truncate_for_wecom(long_text, 40)) == 40
    assert truncate_for_wecom(long_text, 40).endswith("…")


def test_build_summary_card_payload_has_no_image():
    """汇总卡片无图片，logo 为 🚢 文本，跳转总览"""
    payload = build_summary_card_payload("8月13日早报", 12, "中标 2 | 项目 3", "https://example.com")
    card = payload["template_card"]
    assert "card_image" not in card
    assert card["source"]["desc"] == "🚢 全球疏浚情报"
    assert card["main_title"]["title"] == "8月13日早报"
    assert card["card_action"]["url"] == "https://example.com/?mode=recent"


def test_build_markdown_fallback_contains_links():
    """markdown 降级消息包含每条新闻的直达链接"""
    articles = [make_article(1), make_article(2)]
    payload = build_markdown_fallback("8月13日早报", 2, "中标 2", articles, "https://example.com")
    content = payload["markdown"]["content"]
    assert "https://example.com/?id=1" in content
    assert "查看全部 2 条" in content


def test_build_push_messages_structure():
    """一次推送的消息集合包含卡片、新闻列表与降级文本"""
    articles = [make_article(1), make_article(2)]
    messages = build_push_messages(articles, "8月13日早报", 2, "中标 2", "https://example.com")
    assert messages["card"]["msgtype"] == "template_card"
    assert messages["news"]["msgtype"] == "news"
    assert len(messages["news"]["news"]["articles"]) == 3
    assert messages["markdown"]["msgtype"] == "markdown"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_wecom_payload.py -v`

Expected: FAIL，`ImportError: cannot import name 'CATEGORY_PRIORITY'`。

- [ ] **Step 3: 新增模块常量与工具函数**

在 `CATEGORIES_MAP` 字典定义之后新增：

```python
CATEGORY_PRIORITY = ["Bid", "Project", "Equipment", "Regulation", "R&D", "Market"]
```

在 `build_hot_news_titles` 函数之后新增：

```python
def truncate_for_wecom(text, max_chars=40):
    """按字符数截断文本，超出长度时以省略号结尾"""
    if not text:
        return ""
    text = str(text).strip().replace("\n", " ").replace("\r", " ")
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"
```

- [ ] **Step 4: 新增排序函数**

在 `truncate_for_wecom` 之后新增：

```python
def rank_articles_for_push(articles, max_items=5):
    """按重要度分数降序、分类优先级、入库时间倒序排序并截取"""
    def sort_key(article):
        significance = article.get("significance")
        score = significance if isinstance(significance, int) and not isinstance(significance, bool) else -1
        category = article.get("category") or DEFAULT_CATEGORY
        priority = CATEGORY_PRIORITY.index(category) if category in CATEGORY_PRIORITY else len(CATEGORY_PRIORITY)
        created_at = article.get("created_at") or ""
        return (score, -priority, created_at)

    return sorted(articles, key=sort_key, reverse=True)[:max_items]
```

- [ ] **Step 5: 新增 payload 构造函数**

在 `rank_articles_for_push` 之后新增：

```python
def build_summary_card_payload(label, total_count, category_line, base_url):
    """构造汇总模板卡片（无图片，logo 用 🚢 文本）"""
    return {
        "msgtype": "template_card",
        "template_card": {
            "card_type": "news_notice",
            "source": {"desc": "🚢 全球疏浚情报", "desc_color": 0},
            "main_title": {"title": label, "desc": f"本次更新: {total_count} 条"},
            "vertical_content_list": [{"title": "分类分布", "desc": category_line}],
            "card_action": {"type": 1, "url": f"{base_url.rstrip('/')}/?mode=recent"},
        },
    }


def build_news_payload(articles, base_url, total_count):
    """构造重要新闻列表（news 图文消息），末尾追加查看全部条目"""
    news_articles = []
    for article in articles:
        article_id = article.get("id")
        if article_id is None:
            continue
        title = truncate_for_wecom(article.get("title_cn") or article.get("title"), 40)
        description = truncate_for_wecom(article.get("summary_cn") or title, 160)
        news_articles.append({
            "title": title or "未命名新闻",
            "description": description,
            "url": f"{base_url.rstrip('/')}/?id={article_id}",
        })
    if not news_articles:
        return None
    news_articles.append({
        "title": f"查看全部 {total_count} 条 →",
        "description": "进入系统查看完整列表",
        "url": f"{base_url.rstrip('/')}/?mode=recent",
    })
    return {"msgtype": "news", "news": {"articles": news_articles}}


def build_markdown_fallback(label, total_count, category_line, articles, base_url):
    """构造 news 发送失败时的 markdown 降级消息"""
    lines = [f"【全球疏浚情报 {label}】", f"本次更新: {total_count} 条", category_line, ""]
    for article in articles:
        article_id = article.get("id")
        if article_id is None:
            continue
        title = truncate_for_wecom(article.get("title_cn") or article.get("title"), 40)
        lines.append(f"[{title}]({base_url.rstrip('/')}/?id={article_id})")
    lines.append(f"[查看全部 {total_count} 条 →]({base_url.rstrip('/')}/?mode=recent)")
    return {"msgtype": "markdown", "markdown": {"content": "\n".join(lines)}}


def build_push_messages(articles, label, total_count, category_line, base_url):
    """构造本次推送的全部消息（汇总卡片、新闻列表、降级文本）"""
    top_articles = rank_articles_for_push(articles, max_items=5)
    return {
        "card": build_summary_card_payload(label, total_count, category_line, base_url),
        "news": build_news_payload(top_articles, base_url, total_count),
        "markdown": build_markdown_fallback(label, total_count, category_line, top_articles, base_url),
    }
```

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m pytest tests/test_wecom_payload.py -v`

Expected: PASS，全部测试通过。

- [ ] **Step 7: Ruff 检查**

Run: `ruff check backend/reporting/wecom_push.py --ignore E402,F401`

Expected: 无错误输出，退出码 0（`F401` 存量未使用导入 `json` 将在 Task 6 清理）。

- [ ] **Step 8: 提交**

```bash
git add tests/test_wecom_payload.py backend/reporting/wecom_push.py
git commit -m "feat(reporting): 新增汇总卡片与重要新闻列表 payload 构造"
```

---

### Task 6: 推送主流程接线

**Files:**
- Modify: `backend/reporting/wecom_push.py`

- [ ] **Step 1: 替换 `push_daily_report` 函数**

找到文件顶部 `import urllib.parse` 一行，删除；再删除 `import json` 一行（新流程不再使用）。然后找到现有的 `def push_daily_report():` 函数，整体替换为：

```python
def push_daily_report():
    """推送日报到企业微信：汇总卡片 + 重要新闻列表"""
    now = datetime.now()
    start_dt, end_dt, label = get_push_window(now)
    start_time = start_dt.isoformat()
    end_time = end_dt.isoformat()

    articles = database.get_articles_by_time_range_strict(start_time, end_time, is_retained=1)
    raw_event_count = len(articles)

    if not articles:
        print("无新情报，发送空消息通知")
        write_scheduler_log(f"推送统计: 窗口{label} 原始记录{raw_event_count} 过滤后0 推送0")
        payload = {
            "msgtype": "text",
            "text": {
                "content": f"【全球疏浚情报 {label}】\n截至目前，暂无最新情报更新。"
            }
        }
        resp_json = post_wecom_webhook(payload, label)
        if resp_json.get("errcode") == 0:
            print("[Push] 已发送无情报通知")
        else:
            print(f"[Push] 无情报通知发送失败: {resp_json}")
        return

    for e in articles:
        e["category"] = pick_primary_category(e.get("categories") or [])

    total_count = len(articles)
    category_counts = build_category_counts(articles)
    category_labels = {
        "Market": "市场",
        "Bid": "中标",
        "Project": "项目",
        "Equipment": "设备",
        "R&D": "研发",
        "Regulation": "法规"
    }
    category_line = " | ".join([f"{category_labels[k]}{category_counts.get(k, 0)}" for k in category_labels.keys() if category_counts.get(k, 0) > 0])
    write_scheduler_log(
        f"推送统计: 窗口{label} 原始记录{raw_event_count} 推送{total_count}"
    )

    base_url = config.PUSH_BASE_URL
    messages = build_push_messages(articles, label, total_count, category_line, base_url)

    # 消息一：汇总卡片；失败时降级为文本
    resp_json = post_wecom_webhook(messages["card"], label)
    if resp_json.get("errcode") != 0:
        print("Template Card 推送失败，尝试降级为 Text 消息...")
        text_content = f"【全球疏浚情报 {label}】\n"
        text_content += f"本次更新: {total_count} 条\n\n"
        text_content += f"{category_line}\n"
        text_content += f"\n详情请访问: {base_url.rstrip('/')}/?mode=recent"
        text_payload = {
            "msgtype": "text",
            "text": {
                "content": text_content
            }
        }
        fallback_resp = post_wecom_webhook(text_payload, label)
        if fallback_resp.get("errcode") != 0:
            print(f"[Push] 降级文本推送失败: {fallback_resp}")

    # 消息二：重要新闻列表；失败时降级为 markdown 链接
    news_payload = messages["news"]
    if news_payload:
        resp_json = post_wecom_webhook(news_payload, label)
        if resp_json.get("errcode") != 0:
            print("News 推送失败，尝试降级为 Markdown 消息...")
            fallback_resp = post_wecom_webhook(messages["markdown"], label)
            if fallback_resp.get("errcode") != 0:
                print(f"[Push] 降级 Markdown 推送失败: {fallback_resp}")
```

- [ ] **Step 2: 运行现有单测确认无回归**

Run: `python -m pytest tests/test_wecom_payload.py tests/test_significance.py tests/test_database_significance.py -v`

Expected: PASS。

- [ ] **Step 3: Ruff 检查**

Run: `ruff check backend/ --ignore E402`

Expected: 无错误输出，退出码 0（`E402` 为本项目既有 sys.path 导入模式，不做重构）。

- [ ] **Step 4: 提交**

```bash
git add backend/reporting/wecom_push.py
git commit -m "feat(reporting): 日报推送改为汇总卡片 + 重要新闻列表"
```

---

### Task 7: 前端 `?id=` 直达详情弹窗

**Files:**
- Modify: `frontend/src/views/Dashboard.vue`

- [ ] **Step 1: 引入 useRoute**

把脚本区第一行 import 从：

```ts
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
```

改为：

```ts
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
```

并在 `const newsStore = useNewsStore()` 之后新增：

```ts
const route = useRoute()
```

- [ ] **Step 2: 新增直达函数**

在 `openDetail` 函数之后新增：

```ts
async function openArticleFromQuery(id: string) {
  try {
    const response = await fetch(`/api/article/${encodeURIComponent(id)}`)
    const data = await response.json()
    const article = data?.article
    if (!article) return
    currentArticle.value = { ...article, id: String(article.id) }
    modalVisible.value = true
  } catch (error) {
    console.error('打开推送直达文章失败', error)
  }
}
```

- [ ] **Step 3: onMounted 处理查询参数**

把 `onMounted` 改为：

```ts
onMounted(async () => {
  await Promise.all([newsStore.fetchNews(), vesselStore.fetchVessels()])
  loading.value = false

  // Auto-refresh every 5 minutes
  refreshTimer = window.setInterval(
    async () => {
      await Promise.all([newsStore.fetchNews(), vesselStore.fetchVessels()])
    },
    5 * 60 * 1000
  )

  // 企业微信推送直达：/?id=123 自动打开对应详情弹窗
  const queryId = route.query.id
  if (queryId && typeof queryId === 'string') {
    await openArticleFromQuery(queryId)
  }
})
```

- [ ] **Step 4: Lint 检查**

Run: `pnpm run lint`

Expected: 无错误输出。

- [ ] **Step 5: 手动验证直达**

Run: `pnpm run dev`

Expected: 打开 `http://localhost:3000/?id=1`（id 换成数据库中真实存在的文章 id），页面加载完成后自动弹出该文章的详情弹窗；打开 `http://localhost:3000/?id=999999` 不弹窗、页面正常。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/views/Dashboard.vue
git commit -m "feat(frontend): 支持 ?id= 直达打开文章详情弹窗"
```

---

### Task 8: 整体验证

**Files:** 无新增

- [ ] **Step 1: 运行全部相关测试**

Run: `python -m pytest tests/test_significance.py tests/test_wecom_payload.py tests/test_database_significance.py -v`

Expected: 全部 PASS。

- [ ] **Step 2: 后端 lint**

Run: `ruff check backend/ --ignore E402`

Expected: 无错误输出，退出码 0。

- [ ] **Step 3: 前端 lint**

Run: `pnpm run lint`

Expected: 无错误输出。

- [ ] **Step 4: 打印推送 payload 进行 dry-run 检查**

Run（PowerShell）：

```powershell
python -c "import sys; sys.path.insert(0, 'backend'); from reporting import wecom_push as w; arts=[{'id':1,'title_cn':'测试新闻A','summary_cn':'摘要A','category':'Bid','significance':8,'created_at':'2026-08-13T07:00:00'},{'id':2,'title_cn':'测试新闻B','summary_cn':'摘要B','category':'Project','significance':None,'created_at':'2026-08-13T07:10:00'}]; msgs=w.build_push_messages(arts, '8月13日早报', 2, '中标1 | 项目1', 'https://example.com'); print(msgs['card']); print(msgs['news'])"
```

Expected: 输出两条 payload：

- `card` 为 template_card，`source.desc` 含 `🚢`，无 `card_image`；
- `news` 的 `articles` 共 3 条（2 条新闻 + 1 条查看全部），第一条 url 为 `https://example.com/?id=1`，无 `picurl`。

- [ ] **Step 5: 真实推送演练（可选，需已配置 webhook）**

Run: `python tests/verify_push.py`

Expected: 调度日志出现推送统计，企业微信测试群收到汇总卡片 + 新闻列表两条消息；点击新闻条目可打开对应详情弹窗。演练完成后确认数据库中测试数据已被清理（该脚本自带清理逻辑）。
