# tests/test_wecom_payload.py
"""企业微信推送 payload 构造测试"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from reporting.wecom_push import (
    CATEGORY_PRIORITY,
    build_markdown_payload,
    build_push_messages,
    build_text_fallback,
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


def test_truncate_for_wecom():
    """超长文本按字符截断并以省略号结尾"""
    assert truncate_for_wecom("短文本", 40) == "短文本"
    long_text = "中" * 50
    assert len(truncate_for_wecom(long_text, 40)) == 40
    assert truncate_for_wecom(long_text, 40).endswith("…")


def test_build_markdown_payload_contains_links():
    """markdown 消息包含汇总与每条新闻的直达链接，无图片字段"""
    articles = [make_article(1), make_article(2)]
    payload = build_markdown_payload("8月14日早报", 2, "中标 2", articles, "https://example.com")
    content = payload["markdown"]["content"]
    assert "本次更新: 2 条" in content
    assert "1. [" in content
    assert "2. [" in content
    assert "https://example.com/?id=1" in content
    assert "查看全部 2 条" in content


def test_build_push_messages_structure():
    """一次推送的消息集合包含单条 markdown 与纯文本降级"""
    articles = [make_article(1), make_article(2)]
    messages = build_push_messages(articles, "8月13日早报", 2, "中标 2", "https://example.com")
    assert "news" not in messages
    assert messages["markdown"]["msgtype"] == "markdown"
    assert messages["text"]["msgtype"] == "text"


def test_build_text_fallback_structure():
    """纯文本降级消息包含汇总与总览链接"""
    payload = build_text_fallback("8月14日早报", 2, "中标 2", "https://example.com")
    assert payload["msgtype"] == "text"
    content = payload["text"]["content"]
    assert "本次更新: 2 条" in content
    assert "https://example.com/?mode=recent" in content
