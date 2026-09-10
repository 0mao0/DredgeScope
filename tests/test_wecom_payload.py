# tests/test_wecom_payload.py
"""企业微信推送 payload 构造测试"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import config
from reporting import wecom_push as wp
from reporting.wecom_push import (
    CATEGORY_PRIORITY,
    article_image_url,
    build_markdown_fallback,
    build_news_payload,
    build_push_messages,
    push_cover_picurl,
    rank_articles_for_push,
    truncate_for_wecom,
)

COVER_URL = "https://example.com/static/push_cover.jpg"

# autouse fixture 会把动态封面禁用为 None，动态封面专项测试需恢复真实实现
import reporting.push_cover as _pc  # noqa: E402

_REAL_ENSURE = _pc.ensure_dynamic_cover


@pytest.fixture(autouse=True)
def _default_cover_env(monkeypatch):
    """封面覆盖置空且禁用动态封面，保证测试走默认静态封面"""
    from reporting import push_cover

    monkeypatch.setattr(config, "PUSH_COVER_URL", "")
    monkeypatch.setattr(push_cover, "ensure_dynamic_cover", lambda label, now=None: None)


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
    """news 消息以汇总为第一张，含新闻条目与查看全部，无图片时不携带 picurl"""
    articles = [make_article(1), make_article(2)]
    payload = build_news_payload(articles, "https://example.com", total_count=2, label="8月14日早报", category_line="中标 1 | 项目 1")
    assert payload["msgtype"] == "news"
    items = payload["news"]["articles"]
    assert len(items) == 4
    assert items[0]["title"] == "8月14日早报 · 更新 2 条"
    assert items[0]["description"] == "中标 1 | 项目 1"
    assert items[0]["url"] == "https://example.com/?mode=recent"
    assert items[0]["picurl"] == COVER_URL  # 头部大图固定统一封面
    assert items[1]["url"] == "https://example.com/?id=1"
    assert "picurl" not in items[1]
    assert items[-1]["title"] == "查看全部 2 条 →"


def test_build_news_payload_with_images():
    """条目有截图时附带 picurl（缩略图不可用时回退原图），头部固定统一封面"""
    articles = [
        make_article(1),
        make_article(2, created_at="2026-08-13T07:00:01"),
        make_article(3),
    ]
    articles[0]["screenshot_path"] = ""
    articles[1]["screenshot_path"] = "assets/two.jpg"
    articles[2]["screenshot_path"] = "/assets/three.png"
    payload = build_news_payload(articles, "https://example.com/", total_count=3, label="8月14日早报", category_line="中标 3")
    items = payload["news"]["articles"]
    assert "picurl" not in items[1]  # 无图条目不携带
    assert items[2]["picurl"] == "https://example.com/assets/two.jpg"
    assert items[3]["picurl"] == "https://example.com/assets/three.png"
    assert items[0]["picurl"] == COVER_URL


def test_build_news_payload_skips_blank_image(monkeypatch):
    """白图条目不携带 picurl（ensure_push_thumb 返回空串）"""
    monkeypatch.setattr(wp, "ensure_push_thumb", lambda path: "")
    articles = [make_article(1)]
    articles[0]["screenshot_path"] = "assets/blank.jpg"
    payload = build_news_payload(articles, "https://example.com", total_count=1, label="8月14日早报", category_line="")
    items = payload["news"]["articles"]
    assert "picurl" not in items[1]
    assert items[0]["picurl"] == COVER_URL  # 白图不影响头部封面


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


# ---------- 缩略图与封面 ----------

def _use_tmp_assets(tmp_path, monkeypatch):
    """把 config 的数据/资源目录指向临时目录"""
    data = tmp_path / "data"
    assets = data / "assets"
    assets.mkdir(parents=True)
    monkeypatch.setattr(config, "DATA_DIR", str(data))
    monkeypatch.setattr(config, "ASSETS_DIR", str(assets))
    return assets


def test_ensure_push_thumb_generates_small_jpeg(tmp_path, monkeypatch):
    """长截图生成 2.4:1 缩略图，宽 640，带磁盘缓存"""
    from PIL import Image

    assets = _use_tmp_assets(tmp_path, monkeypatch)
    src = assets / "long.jpg"
    Image.effect_noise((1200, 6000), 60).convert("RGB").save(src, quality=90)

    rel = wp.ensure_push_thumb("assets/long.jpg")
    assert rel == "assets/thumbs/long.jpg"
    thumb_file = assets / "thumbs" / "long.jpg"
    assert thumb_file.exists()
    with Image.open(thumb_file) as t:
        w, h = t.size
        assert w == 640
        assert abs(w / h - wp.THUMB_ASPECT) < 0.1
    assert thumb_file.stat().st_size < src.stat().st_size / 4
    mtime_before = thumb_file.stat().st_mtime
    assert wp.ensure_push_thumb("assets/long.jpg") == rel  # 命中缓存
    assert thumb_file.stat().st_mtime == mtime_before


def test_ensure_push_thumb_skips_blank_image(tmp_path, monkeypatch):
    """纯白截图识别为白图，返回空串不生成缩略图"""
    from PIL import Image

    assets = _use_tmp_assets(tmp_path, monkeypatch)
    Image.new("RGB", (1200, 3000), (255, 255, 255)).save(assets / "blank.jpg")

    assert wp.ensure_push_thumb("assets/blank.jpg") == ""
    assert not (assets / "thumbs").exists()
    assert article_image_url({"screenshot_path": "assets/blank.jpg"}, "https://example.com") == ""


def test_ensure_push_thumb_missing_file_returns_none(tmp_path, monkeypatch):
    """源文件不存在时返回 None，article_image_url 回退原图 URL"""
    _use_tmp_assets(tmp_path, monkeypatch)
    assert wp.ensure_push_thumb("assets/missing.jpg") is None
    assert article_image_url({"screenshot_path": "/assets/missing.jpg"}, "https://example.com") == "https://example.com/assets/missing.jpg"
    assert article_image_url({"screenshot_path": ""}, "https://example.com") == ""


def test_push_cover_picurl_default_and_override(monkeypatch):
    """动态封面不可用时走 /static/push_cover.jpg，PUSH_COVER_URL 可覆盖"""
    assert push_cover_picurl("https://example.com/", "9月10日早报") == COVER_URL
    monkeypatch.setattr(config, "PUSH_COVER_URL", "https://cdn.example.com/cover.png")
    assert push_cover_picurl("https://example.com") == "https://cdn.example.com/cover.png"


def test_push_cover_picurl_prefers_dynamic(monkeypatch):
    """动态封面可用时优先使用，且随 label 传入时段标签"""
    from reporting import push_cover

    seen = {}

    def fake_dynamic(label, now=None):
        seen["label"] = label
        return "assets/covers/push_cover_20260910_am.jpg"

    monkeypatch.setattr(push_cover, "ensure_dynamic_cover", fake_dynamic)
    url = push_cover_picurl("https://example.com", "9月10日早报")
    assert url == "https://example.com/assets/covers/push_cover_20260910_am.jpg"
    assert seen["label"] == "9月10日早报"


def test_ensure_dynamic_cover_generates_and_caches(tmp_path, monkeypatch):
    """早报/晚报各自生成当日封面并缓存；产物 2.4:1 且体积可控"""
    pytest.importorskip("PIL")
    from datetime import datetime

    from reporting import push_cover

    if push_cover.find_font(False, 12) is None:
        pytest.skip("运行环境缺少中文字体")
    monkeypatch.setattr(push_cover, "ensure_dynamic_cover", _REAL_ENSURE)
    assets = _use_tmp_assets(tmp_path, monkeypatch)
    now = datetime(2026, 9, 10, 19, 0)

    rel_am = push_cover.ensure_dynamic_cover("9月10日早报", now=now)
    rel_pm = push_cover.ensure_dynamic_cover("9月10日晚报", now=now)
    assert rel_am == "assets/covers/push_cover_20260910_am.jpg"
    assert rel_pm == "assets/covers/push_cover_20260910_pm.jpg"
    from PIL import Image

    for rel in (rel_am, rel_pm):
        p = assets / "covers" / rel.split("/")[-1]
        assert p.exists() and p.stat().st_size < 300 * 1024
        with Image.open(p) as im:
            assert abs(im.size[0] / im.size[1] - wp.THUMB_ASPECT) < 0.1
    mtime = (assets / "covers" / "push_cover_20260910_am.jpg").stat().st_mtime
    assert push_cover.ensure_dynamic_cover("9月10日早报", now=now) == rel_am
    assert (assets / "covers" / "push_cover_20260910_am.jpg").stat().st_mtime == mtime


def test_ensure_dynamic_cover_falls_back_without_font(tmp_path, monkeypatch):
    """无中文字体时返回 None，由调用方回退静态封面"""
    from datetime import datetime

    from reporting import push_cover

    monkeypatch.setattr(push_cover, "ensure_dynamic_cover", _REAL_ENSURE)
    _use_tmp_assets(tmp_path, monkeypatch)  # 避开真实目录里已缓存的当日封面
    monkeypatch.setattr(push_cover, "find_font", lambda bold, size: None)
    assert push_cover.ensure_dynamic_cover("9月10日早报", now=datetime(2026, 9, 10)) is None
