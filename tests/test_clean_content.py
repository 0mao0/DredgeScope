# tests/test_clean_content.py
"""AI 正文清洗函数测试"""

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from analysis import info_analysis
import config


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
    item = {
        "url": "https://a.com/1",
        "content": "这是第一段正文，内容足够长，用来触发模型清洗调用。\nSubscribe\n这是第二段正文，同样足够长，确保不会被跳过。",
    }
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
    item = {
        "url": "https://a.com/1",
        "content": "真实正文第一段，内容足够长，用来触发模型清洗调用。\nSubscribe\n真实正文第二段，同样足够长，确保不会被跳过。",
    }
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
