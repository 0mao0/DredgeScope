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
