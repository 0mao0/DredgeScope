# tests/test_process_items_clean.py
"""分析流程集成 AI 正文清洗测试"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, Mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from analysis import info_analysis
import config


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
