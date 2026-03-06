"""
采集源模块

为每个数据源提供独立的采集器，便于维护和调试。
"""

from .base import BaseSource, RSSSource, WebSource
from .registry import SourceRegistry

__all__ = ['BaseSource', 'RSSSource', 'WebSource', 'SourceRegistry']
