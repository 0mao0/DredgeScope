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
