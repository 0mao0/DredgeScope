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
