"""
采集源管理器

整合所有采集源，提供统一的采集接口
"""

import asyncio
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from .sources import SourceRegistry
from .sources.base import BaseSource, RSSSource, WebSource


class SourceManager:
    """采集源管理器"""

    def __init__(self, sources_config_path: Optional[str] = None):
        """
        初始化管理器

        Args:
            sources_config_path: sources.json 配置文件路径
        """
        self.registry = SourceRegistry()
        self.sources: Dict[str, BaseSource] = {}
        self.stats = {
            'start_time': None,
            'end_time': None,
            'total_fetched': 0,
            'total_success': 0,
            'total_failed': 0,
            'by_source': {}
        }

        # 加载配置
        if sources_config_path:
            self._load_config(sources_config_path)

    def _load_config(self, config_path: str):
        """从配置文件加载采集源"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                configs = json.load(f)

            for config in configs:
                source_type = config.get('type', 'web')
                name = config.get('name')

                if not name:
                    continue

                # 尝试从注册表创建
                source = self.registry.create(name, config)

                if source:
                    self.sources[name] = source
                    print(f"[Manager] 加载采集源: {name} ({source_type})")
                else:
                    # 如果注册表中没有，根据类型创建通用采集器
                    if source_type == 'rss':
                        source = self._create_generic_rss(config)
                    elif source_type == 'web':
                        source = self._create_generic_web(config)

                    if source:
                        self.sources[name] = source
                        print(f"[Manager] 创建通用采集源: {name} ({source_type})")

        except Exception as e:
            print(f"[Manager] 加载配置失败: {e}")

    def _create_generic_rss(self, config: Dict[str, Any]) -> Optional[RSSSource]:
        """创建通用RSS采集器"""
        class GenericRSS(RSSSource):
            name = config.get('name', 'Generic RSS')
            feed_url = config.get('url', '')

        if config.get('url'):
            return GenericRSS()
        return None

    def _create_generic_web(self, config: Dict[str, Any]) -> Optional[WebSource]:
        """创建通用Web采集器"""
        class GenericWeb(WebSource):
            name = config.get('name', 'Generic Web')
            index_url = config.get('url', '')
            selector = config.get('selector', 'body')
            max_links = config.get('max_links', 10)
            blacklist = config.get('blacklist', [])

        if config.get('url'):
            return GenericWeb()
        return None

    async def fetch_all(self, hours: int = 24, source_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        采集所有源的新闻

        Args:
            hours: 获取最近几小时的新闻
            source_names: 指定采集的源名称列表，None表示全部

        Returns:
            所有新闻条目列表
        """
        self.stats['start_time'] = datetime.now().isoformat()
        all_items = []

        # 确定要采集的源
        sources_to_fetch = {}
        if source_names:
            for name in source_names:
                if name in self.sources:
                    sources_to_fetch[name] = self.sources[name]
        else:
            sources_to_fetch = self.sources

        print(f"\n{'='*60}")
        print(f"开始采集 {len(sources_to_fetch)} 个数据源")
        print(f"{'='*60}\n")

        # 并发采集
        sem = asyncio.Semaphore(5)  # 最多5个并发

        async def fetch_with_source(name: str, source: BaseSource) -> tuple:
            async with sem:
                try:
                    items = await source.fetch(hours=hours)
                    return name, items, None
                except Exception as e:
                    return name, [], str(e)

        tasks = [
            fetch_with_source(name, source)
            for name, source in sources_to_fetch.items()
        ]

        results = await asyncio.gather(*tasks)

        # 处理结果
        for name, items, error in results:
            if error:
                print(f"[Manager] {name} 采集失败: {error}")
                self.stats['by_source'][name] = {
                    'status': 'failed',
                    'error': error,
                    'count': 0
                }
                self.stats['total_failed'] += 1
            else:
                all_items.extend(items)
                self.stats['by_source'][name] = {
                    'status': 'success',
                    'count': len(items)
                }
                self.stats['total_success'] += 1
                self.stats['total_fetched'] += len(items)

        self.stats['end_time'] = datetime.now().isoformat()

        print(f"\n{'='*60}")
        print(f"采集完成: 共 {len(all_items)} 条新闻")
        print(f"{'='*60}\n")

        return all_items

    async def enrich_items(self, items: List[Dict[str, Any]], context) -> List[Dict[str, Any]]:
        """
        补充采集网页内容

        Args:
            items: 新闻条目列表
            context: Playwright浏览器上下文

        Returns:
            补充内容后的条目列表
        """
        from playwright.async_api import TimeoutError as PlaywrightTimeout

        print(f"\n[Enrich] 开始补充采集 {len(items)} 条新闻...")

        sem = asyncio.Semaphore(3)
        results = []

        async def enrich_item(item: Dict[str, Any]) -> Dict[str, Any]:
            async with sem:
                source_name = item.get('source_name', '')
                link = item.get('link', '')
                source_type = item.get('source_type', '').lower()

                # 检查是否已有内容
                has_content = item.get('content') and len(item.get('content', '').strip()) > 100
                has_screenshot = item.get('screenshot_path') and len(item.get('screenshot_path', '')) > 0

                try:
                    if source_type == 'rss':
                        if has_content and not has_screenshot:
                            # RSS有内容但无截图：只获取截图
                            await self._fetch_rss_screenshot(context, item)
                        elif not has_content:
                            # RSS无内容：完整抓取
                            await self._fetch_web_content(context, item)
                    elif source_type == 'web':
                        # Web源：完整抓取
                        await self._fetch_web_content(context, item)

                except Exception as e:
                    print(f"[Enrich] 失败 {link}: {e}")

                return item

        tasks = [enrich_item(item) for item in items]
        results = await asyncio.gather(*tasks)

        print(f"[Enrich] 补充采集完成\n")
        return results

    async def _fetch_rss_screenshot(self, context, item: Dict[str, Any]):
        """为RSS条目获取截图"""
        page = None
        try:
            page = await context.new_page()
            await page.goto(item['link'], wait_until='domcontentloaded', timeout=20000)
            await asyncio.sleep(1)

            screenshot_bytes = await page.screenshot(type='jpeg', quality=60, full_page=True)

            # 保存截图
            import os
            import hashlib
            import sys
            sys.path.append(os.path.dirname(os.path.dirname(__file__)))
            import config

            base = "".join([c for c in item['link'] if c.isalnum()])[:40]
            digest = hashlib.md5(item['link'].encode()).hexdigest()[:8]
            filename = f"{base}_{digest}.jpg"

            local_path = os.path.join(config.ASSETS_DIR, filename)
            with open(local_path, 'wb') as f:
                f.write(screenshot_bytes)

            item['screenshot_path'] = f"assets/{filename}"
            print(f"[RSS截图] 成功 {item.get('title', '')[:50]}...")

        except Exception as e:
            print(f"[RSS截图] 失败 {item.get('link')}: {e}")
        finally:
            if page:
                await page.close()

    async def _fetch_web_content(self, context, item: Dict[str, Any]):
        """抓取网页内容"""
        page = None
        try:
            page = await context.new_page()

            # 使用重试策略
            strategies = [
                {"wait_until": "domcontentloaded", "timeout": 30000},
                {"wait_until": "load", "timeout": 45000}
            ]

            for strategy in strategies:
                try:
                    await page.goto(item['link'], **strategy)
                    break
                except Exception:
                    if strategy == strategies[-1]:
                        raise
                    continue

            await asyncio.sleep(2)

            # 提取内容
            content = await self._extract_page_content(page)
            if content:
                item['content'] = content

            # 提取日期
            date = await self._extract_page_date(page)
            if date and not item.get('pub_date'):
                item['pub_date'] = date

            # 截图
            await self._fetch_rss_screenshot(context, item)

            print(f"[Web抓取] 成功 {item.get('title', '')[:50]}...")

        except Exception as e:
            print(f"[Web抓取] 失败 {item.get('link')}: {e}")
        finally:
            if page:
                await page.close()

    async def _extract_page_content(self, page) -> str:
        """提取页面正文"""
        selectors = [
            'article', '.post-content', '.entry-content', '.article-content',
            '.article-body', '#article-body', '.body-content', '.main-content',
            'main', '#content', '.content'
        ]

        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    if len(text.strip()) > 200:
                        return text.strip()[:15000]
            except:
                continue

        try:
            body = await page.query_selector('body')
            if body:
                return (await body.inner_text()).strip()[:15000]
        except:
            pass

        return ''

    async def _extract_page_date(self, page) -> str:
        """提取页面日期"""
        import re

        date_selectors = [
            'meta[property="article:published_time"]',
            'meta[name="publishdate"]',
            'meta[name="date"]',
            'time[datetime]'
        ]

        for selector in date_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    if selector.endswith('[datetime]'):
                        date_str = await element.get_attribute('datetime')
                    else:
                        date_str = await element.get_attribute('content')

                    if date_str:
                        match = re.search(r'(\d{4})[-年\./](\d{1,2})[-月\./](\d{1,2})', date_str)
                        if match:
                            return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
            except:
                pass

        return ''

    def get_stats(self) -> Dict[str, Any]:
        """获取采集统计信息"""
        return self.stats

    def list_sources(self) -> List[str]:
        """列出所有已加载的采集源"""
        return list(self.sources.keys())


# 便捷函数
async def fetch_all_news(config_path: str = None, hours: int = 24) -> List[Dict[str, Any]]:
    """
    便捷函数：采集所有新闻

    Args:
        config_path: sources.json 路径
        hours: 获取最近几小时的新闻

    Returns:
        新闻条目列表
    """
    if not config_path:
        # 默认路径
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, 'static', 'sources.json')

    manager = SourceManager(config_path)
    return await manager.fetch_all(hours=hours)
