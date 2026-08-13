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
