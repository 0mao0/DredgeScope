"""
采集源注册表

管理所有可用的采集源，提供统一的发现和调用接口
"""

from typing import Dict, List, Type, Optional, Any
import importlib
import os
import glob

from .base import BaseSource, RSSSource, WebSource


class SourceRegistry:
    """采集源注册表"""

    _instance = None
    _sources: Dict[str, Type[BaseSource]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._discover_sources()
        return cls._instance

    def _discover_sources(self):
        """自动发现并注册所有采集源"""
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # 发现RSS源
        rss_dir = os.path.join(current_dir, 'rss')
        if os.path.exists(rss_dir):
            for file in glob.glob(os.path.join(rss_dir, '*.py')):
                if file.endswith('__init__.py'):
                    continue
                self._register_from_file(file, 'acquisition.sources.rss')

        # 发现Web源
        web_dir = os.path.join(current_dir, 'web')
        if os.path.exists(web_dir):
            for file in glob.glob(os.path.join(web_dir, '*.py')):
                if file.endswith('__init__.py'):
                    continue
                self._register_from_file(file, 'acquisition.sources.web')

    def _register_from_file(self, file_path: str, package: str):
        """从文件注册采集源"""
        try:
            module_name = os.path.basename(file_path)[:-3]  # 去掉.py
            full_module = f"{package}.{module_name}"

            module = importlib.import_module(full_module)

            # 查找模块中的Source类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    issubclass(attr, BaseSource) and
                    attr not in (BaseSource, RSSSource, WebSource) and
                    hasattr(attr, 'name') and attr.name):
                    self.register(attr.name, attr)
                    print(f"[Registry] 注册采集源: {attr.name} ({full_module})")

        except Exception as e:
            print(f"[Registry] 注册失败 {file_path}: {e}")

    def register(self, name: str, source_class: Type[BaseSource]):
        """
        手动注册采集源

        Args:
            name: 采集源名称
            source_class: 采集源类
        """
        self._sources[name] = source_class

    def get(self, name: str) -> Optional[Type[BaseSource]]:
        """
        获取采集源类

        Args:
            name: 采集源名称

        Returns:
            采集源类或None
        """
        return self._sources.get(name)

    def create(self, name: str, config: Optional[Dict[str, Any]] = None) -> Optional[BaseSource]:
        """
        创建采集源实例

        Args:
            name: 采集源名称
            config: 配置字典

        Returns:
            采集源实例或None
        """
        source_class = self.get(name)
        if source_class:
            return source_class(config)
        return None

    def list_sources(self) -> List[str]:
        """列出所有已注册的采集源名称"""
        return list(self._sources.keys())

    def list_by_type(self, source_type: str) -> List[str]:
        """
        按类型列出采集源

        Args:
            source_type: 类型 (rss, web, wechat)

        Returns:
            采集源名称列表
        """
        result = []
        for name, source_class in self._sources.items():
            if getattr(source_class, 'source_type', '') == source_type:
                result.append(name)
        return result


# 全局注册表实例
registry = SourceRegistry()
