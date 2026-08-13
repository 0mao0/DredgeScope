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
    """news 消息以汇总为第一张，含新闻条目与查看全部，不含图片字段"""
    articles = [make_article(1), make_article(2)]
    payload = build_news_payload(articles, "https://example.com", total_count=2, label="8月14日早报", category_line="中标 1 | 项目 1")
    assert payload["msgtype"] == "news"
    items = payload["news"]["articles"]
    assert len(items) == 4
    assert items[0]["title"] == "8月14日早报 · 更新 2 条"
    assert items[0]["description"] == "中标 1 | 项目 1"
    assert items[0]["url"] == "https://example.com/?mode=recent"
    assert items[1]["url"] == "https://example.com/?id=1"
    assert "picurl" not in items[1]
    assert items[-1]["title"] == "查看全部 2 条 →"


def test_build_news_payload_empty_returns_none():
    """没有可推送文章时返回 None"""
    assert build_news_payload([], "https://example.com", total_count=0, label="8月14日早报", category_line="") is None


def test_truncate_for_wecom():
    """超长文本按字符截断并以省略号结尾"""
    assert truncate_for_wecom("短文本", 40) == "短文本"
    long_text = "中" * 50
    assert len(truncate_for_wecom(long_text, 40)) == 40
    assert truncate_for_wecom(long_text, 40).endswith("…")


def test_build_markdown_fallback_contains_links():
    """markdown 降级消息包含每条新闻的直达链接"""
    articles = [make_article(1), make_article(2)]
    payload = build_markdown_fallback("8月13日早报", 2, "中标 2", articles, "https://example.com")
    content = payload["markdown"]["content"]
    assert "https://example.com/?id=1" in content
    assert "查看全部 2 条" in content


def test_build_push_messages_structure():
    """一次推送的消息集合包含单条 news 列表与降级文本"""
    articles = [make_article(1), make_article(2)]
    messages = build_push_messages(articles, "8月13日早报", 2, "中标 2", "https://example.com")
    assert "card" not in messages
    assert messages["news"]["msgtype"] == "news"
    assert len(messages["news"]["news"]["articles"]) == 4
    assert messages["markdown"]["msgtype"] == "markdown"
