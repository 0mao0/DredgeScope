# tests/test_database_content_clean.py
"""articles.content_clean 列迁移、查询与回写测试"""

import os
import shutil
import sqlite3
import sys
import uuid

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
            title_cn TEXT,
            pub_date TEXT,
            source_type TEXT,
            source_name TEXT,
            summary_cn TEXT,
            full_text_cn TEXT,
            content TEXT,
            screenshot_path TEXT,
            is_significant BOOLEAN,
            vl_desc TEXT,
            category TEXT,
            is_hidden INTEGER DEFAULT 0,
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
