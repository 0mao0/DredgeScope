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
        print(f"开始采集 {len(sources_to_fetch)} 个数据源（顺序执行）")
        print(f"{'='*60}\n")

        # 顺序采集（避免并发导致的结果不稳定）
        for name, source in sources_to_fetch.items():
            try:
                items = await source.fetch(hours=hours)
                all_items.extend(items)
                self.stats['by_source'][name] = {
                    'status': 'success',
                    'count': len(items)
                }
                self.stats['total_success'] += 1
                self.stats['total_fetched'] += len(items)
            except Exception as e:
                error_msg = str(e)
                print(f"[Manager] {name} 采集失败: {error_msg}")
                self.stats['by_source'][name] = {
                    'status': 'failed',
                    'error': error_msg,
                    'count': 0
                }
                self.stats['total_failed'] += 1

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
                        # RSS源：始终进行完整网页抓取，获取完整内容、截图和准确时间
                        # 因为RSS通常只提供摘要，需要访问网页获取完整内容
                        await self._fetch_web_content(context, item, is_rss=True)
                    elif source_type == 'web':
                        # Web源：完整抓取
                        await self._fetch_web_content(context, item, is_rss=False)
                    elif source_type == 'wechat':
                        # 微信公众号：需要完整抓取内容和截图
                        print(f"[Enrich] 采集公众号文章: {item.get('title', '')[:40]}...")
                        await self._fetch_wechat_content(context, item)

                except Exception as e:
                    print(f"[Enrich] 失败 {link}: {e}")

                return item

        tasks = [enrich_item(item) for item in items]
        results = await asyncio.gather(*tasks)

        print(f"[Enrich] 补充采集完成\n")
        return results

    async def _fetch_rss_screenshot(self, context, item: Dict[str, Any], page=None):
        """为RSS条目获取截图
        
        Args:
            context: Playwright浏览器上下文
            item: 新闻条目
            page: 可选，如果提供了已打开的页面，则直接使用；否则创建新页面
        """
        new_page = None
        try:
            if page is None:
                new_page = await context.new_page()
                await new_page.goto(item['link'], wait_until='domcontentloaded', timeout=20000)
                await asyncio.sleep(1)
                page = new_page

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

            # 只有截图成功保存后才设置路径
            item['screenshot_path'] = f"assets/{filename}"
            print(f"[RSS截图] 成功 {item.get('title', '')[:50]}...")

        except Exception as e:
            print(f"[RSS截图] 失败 {item.get('link')}: {e}")
            # 截图失败时清除路径，避免数据库中有路径但文件不存在
            item['screenshot_path'] = None
        finally:
            if new_page:
                await new_page.close()

    async def _fetch_web_content(self, context, item: Dict[str, Any], is_rss: bool = False):
        """抓取网页内容
        
        Args:
            context: Playwright浏览器上下文
            item: 新闻条目
            is_rss: 是否为RSS源，RSS源需要强制更新内容和时间
        """
        page = None
        source_type_label = "RSS" if is_rss else "Web"
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

            # 提取内容 - RSS源强制更新，Web源只在无内容时更新
            content = await self._extract_page_content(page)
            if content:
                if is_rss:
                    # RSS源：用网页完整内容替换RSS摘要
                    item['content'] = content
                elif not item.get('content'):
                    item['content'] = content

            # 提取日期 - RSS源强制更新，Web源只在无时间时更新
            date = await self._extract_page_date(page)
            if date:
                if is_rss:
                    # RSS源：用网页准确时间替换RSS时间
                    item['pub_date'] = date
                elif not item.get('pub_date'):
                    item['pub_date'] = date

            # 截图 - 使用已打开的页面，避免重复创建页面
            await self._fetch_rss_screenshot(context, item, page=page)

            print(f"[{source_type_label}抓取] 成功 {item.get('title', '')[:50]}...")

        except Exception as e:
            print(f"[{source_type_label}抓取] 失败 {item.get('link')}: {e}")
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
        from datetime import datetime

        # 首先尝试从 meta 标签和 time 标签获取
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

        # 尝试从页面文本中提取日期（如 "Posted on March 10, 2026"）
        text_date_selectors = [
            '.posted-on', '.entry-date', '.publish-date', '.post-date',
            '.date', '[class*="date"]', '[class*="time"]'
        ]

        for selector in text_date_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    if text:
                        # 尝试解析英文日期格式，如 "March 10, 2026" 或 "Posted on March 10, 2026"
                        date_patterns = [
                            # March 10, 2026
                            r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})',
                            # 10 March 2026
                            r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
                        ]

                        for pattern in date_patterns:
                            match = re.search(pattern, text, re.IGNORECASE)
                            if match:
                                try:
                                    # 解析月份名称
                                    if pattern.startswith('(January'):
                                        month_names = ['january', 'february', 'march', 'april', 'may', 'june',
                                                      'july', 'august', 'september', 'october', 'november', 'december']
                                        month = month_names.index(match.group(1).lower()) + 1
                                        day = int(match.group(2))
                                        year = int(match.group(3))
                                    else:
                                        day = int(match.group(1))
                                        month_names = ['january', 'february', 'march', 'april', 'may', 'june',
                                                      'july', 'august', 'september', 'october', 'november', 'december']
                                        month = month_names.index(match.group(2).lower()) + 1
                                        year = int(match.group(3))

                                    # 验证日期有效性
                                    dt = datetime(year, month, day)
                                    return f"{year}-{month:02d}-{day:02d}"
                                except (ValueError, IndexError):
                                    continue
            except:
                pass

        return ''

    async def _fetch_wechat_content(self, context, item: Dict[str, Any]):
        """抓取微信公众号文章内容"""
        page = None
        try:
            page = await context.new_page()

            # 微信公众号页面加载策略
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

            # 等待文章内容加载
            await asyncio.sleep(3)

            # 尝试多种选择器提取公众号正文
            content_selectors = [
                '#js_content',  # 公众号文章正文ID
                '.rich_media_content',  # 公众号内容区
                '#img-content',  # 另一种内容区
                'article',  # 通用文章标签
                '.post-content',
                '#content'
            ]

            content = ''
            for selector in content_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        text = await element.inner_text()
                        if len(text.strip()) > 100:
                            content = text.strip()[:15000]
                            break
                except:
                    continue

            if content:
                item['content'] = content
                print(f"[公众号抓取] 成功获取正文: {len(content)} 字符")
            else:
                # 如果都没找到，尝试获取body
                try:
                    body = await page.query_selector('body')
                    if body:
                        content = (await body.inner_text()).strip()[:15000]
                        if len(content) > 100:
                            item['content'] = content
                            print(f"[公众号抓取] 使用body内容: {len(content)} 字符")
                except:
                    pass

            # 截图
            await self._fetch_rss_screenshot(context, item)

        except Exception as e:
            print(f"[公众号抓取] 失败 {item.get('link')}: {e}")
        finally:
            if page:
                await page.close()

    def get_stats(self) -> Dict[str, Any]:
        """获取采集统计信息"""
        return self.stats

    def list_sources(self) -> List[str]:
        """列出所有已加载的采集源"""
        return list(self.sources.keys())

    @staticmethod
    async def launch_browser(p):
        """
        启动 Playwright 浏览器

        Args:
            p: Playwright 实例

        Returns:
            Browser 实例
        """
        last_error = None

        # 尝试各种渠道
        for channel in ["chrome", "msedge", "chromium"]:
            try:
                return await p.chromium.launch(channel=channel, headless=True)
            except Exception as e:
                last_error = e

        # 尝试无渠道启动
        try:
            return await p.chromium.launch(headless=True)
        except Exception as e:
            last_error = e

        # 尝试常见路径
        candidates = [
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable"
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    return await p.chromium.launch(headless=True, executable_path=path)
                except Exception as e:
                    last_error = e

        if last_error:
            raise last_error
        raise RuntimeError("Playwright 浏览器启动失败")


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
