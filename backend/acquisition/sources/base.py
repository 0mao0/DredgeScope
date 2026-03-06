"""
采集源基类定义

提供统一的接口和通用功能
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio


class BaseSource(ABC):
    """采集源基类"""

    # 子类必须定义这些属性
    name: str = ""  # 数据源名称
    source_type: str = ""  # 类型: rss, web, wechat

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化采集器

        Args:
            config: 数据源配置字典
        """
        self.config = config or {}
        self.stats = {
            'fetched': 0,
            'success': 0,
            'failed': 0,
            'errors': []
        }

    @abstractmethod
    async def fetch(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        获取新闻列表

        Args:
            hours: 获取最近几小时的新闻

        Returns:
            新闻条目列表，每条新闻包含:
            - title: 标题
            - link: 链接
            - pub_date: 发布日期 (YYYY-MM-DD格式)
            - summary_raw: 原始摘要/内容 (RSS源必须)
            - source_type: 来源类型
            - source_name: 来源名称
        """
        pass

    def normalize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        标准化新闻条目

        Args:
            item: 原始新闻条目

        Returns:
            标准化后的条目
        """
        return {
            'title': item.get('title', ''),
            'link': item.get('link', ''),
            'pub_date': item.get('pub_date', ''),
            'summary_raw': item.get('summary_raw', ''),
            'source_type': self.source_type,
            'source_name': self.name,
            'fetched_at': datetime.now().isoformat()
        }

    def log_error(self, error: Exception, context: str = ""):
        """记录错误"""
        error_msg = f"[{self.name}] {context}: {str(error)}"
        self.stats['errors'].append({
            'time': datetime.now().isoformat(),
            'error': str(error),
            'context': context
        })
        print(error_msg)


class RSSSource(BaseSource):
    """RSS源基类"""

    source_type = "rss"
    feed_url: str = ""  # RSS feed地址

    async def fetch(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        获取RSS新闻

        Args:
            hours: 获取最近几小时的新闻

        Returns:
            新闻条目列表
        """
        import feedparser
        import requests
        from datetime import datetime, timedelta

        print(f"[RSS:{self.name}] 正在抓取: {self.feed_url}")

        try:
            # 使用requests获取内容
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(self.feed_url, headers=headers, timeout=20)
            response.raise_for_status()

            # 解析RSS
            d = feedparser.parse(response.content)
            items = []
            cutoff = datetime.now() - timedelta(hours=hours)

            for entry in d.entries:
                pub_dt = self._parse_date(entry)
                if not pub_dt:
                    continue

                if pub_dt > cutoff:
                    item = {
                        'title': entry.title,
                        'link': entry.link,
                        'pub_date': pub_dt.strftime("%Y-%m-%d"),
                        'summary_raw': entry.summary if hasattr(entry, 'summary') else '',
                    }
                    items.append(self.normalize_item(item))

            self.stats['fetched'] = len(items)
            self.stats['success'] = len(items)
            print(f"[RSS:{self.name}] 成功获取 {len(items)} 条新闻")
            return items

        except Exception as e:
            self.log_error(e, "RSS抓取失败")
            self.stats['failed'] += 1
            return []

    def _parse_date(self, entry) -> Optional[datetime]:
        """解析发布日期"""
        from datetime import datetime

        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            return datetime(*entry.published_parsed[:6])
        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            return datetime(*entry.updated_parsed[:6])
        elif hasattr(entry, 'published'):
            return self._normalize_date(entry.published)
        elif hasattr(entry, 'updated'):
            return self._normalize_date(entry.updated)
        return None

    def _normalize_date(self, date_str: str) -> Optional[datetime]:
        """标准化日期字符串"""
        import re
        from datetime import datetime

        if not date_str:
            return None

        # 尝试匹配各种格式
        patterns = [
            r'(\d{4})[-年\./](\d{1,2})[-月\./](\d{1,2})',
        ]

        for pattern in patterns:
            match = re.search(pattern, str(date_str))
            if match:
                y, m, d = match.groups()
                try:
                    return datetime(int(y), int(m), int(d))
                except:
                    pass
        return None


class WebSource(BaseSource):
    """Web源基类"""

    source_type = "web"
    index_url: str = ""  # 索引页URL
    selector: str = "body"  # 文章列表选择器
    max_links: int = 10  # 最大抓取链接数
    blacklist: List[str] = None  # 黑名单路径

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.blacklist = self.blacklist or []
        if config:
            self.index_url = config.get('url', self.index_url)
            self.selector = config.get('selector', self.selector)
            self.max_links = config.get('max_links', self.max_links)
            self.blacklist = config.get('blacklist', self.blacklist)

    async def fetch(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        获取网页新闻列表

        Args:
            hours: 获取最近几小时的新闻（Web源通常需要抓取详情页才能确定时间）

        Returns:
            新闻条目列表
        """
        print(f"[Web:{self.name}] 正在扫描索引页: {self.index_url}")

        # Web源需要Playwright上下文，这里只返回基本结构
        # 详细内容在enrich阶段抓取
        from playwright.async_api import async_playwright

        items = []
        try:
            async with async_playwright() as p:
                browser = await self._launch_browser(p)
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )

                page = await context.new_page()
                await self._goto_with_retry(page, self.index_url)

                # 提取链接
                links = await self._extract_links(page)

                for link in links[:self.max_links]:
                    if self._is_valid_link(link['url'], link['title']):
                        items.append(self.normalize_item({
                            'title': link['title'],
                            'link': link['url'],
                            'pub_date': '',  # Web源需要在详情页抓取时间
                            'summary_raw': '',  # Web源需要在详情页抓取内容
                        }))

                await browser.close()

            self.stats['fetched'] = len(items)
            self.stats['success'] = len(items)
            print(f"[Web:{self.name}] 成功获取 {len(items)} 条新闻链接")
            return items

        except Exception as e:
            self.log_error(e, "Web抓取失败")
            self.stats['failed'] += 1
            return []

    async def _launch_browser(self, p):
        """启动浏览器"""
        for channel in ["chrome", "msedge", "chromium"]:
            try:
                return await p.chromium.launch(channel=channel, headless=True)
            except:
                pass
        return await p.chromium.launch(headless=True)

    async def _goto_with_retry(self, page, url: str):
        """带重试的页面导航"""
        from playwright.async_api import TimeoutError as PlaywrightTimeout

        strategies = [
            {"wait_until": "domcontentloaded", "timeout": 20000},
            {"wait_until": "load", "timeout": 30000}
        ]

        last_error = None
        for strategy in strategies:
            try:
                await page.goto(url, **strategy)
                return
            except PlaywrightTimeout as e:
                last_error = e
                continue

        raise last_error

    async def _extract_links(self, page) -> List[Dict[str, str]]:
        """从页面提取链接"""
        return await page.evaluate(f"""(selector) => {{
            const container = document.querySelector(selector) || document.body;
            const anchors = container.querySelectorAll('a');
            const results = [];
            anchors.forEach(a => {{
                const text = a.innerText.trim();
                const href = a.href;
                if (text.length > 15 && href.startsWith('http')) {{
                    if (!results.find(r => r.url === href)) {{
                        results.push({{title: text, url: href}});
                    }}
                }}
            }});
            return results;
        }}""", self.selector)

    def _is_valid_link(self, url: str, title: str) -> bool:
        """检查链接是否有效"""
        if not url or not title:
            return False

        # 检查黑名单
        url_lower = url.lower()
        for pattern in self.blacklist:
            if pattern.lower() in url_lower:
                return False

        # 过滤导航类链接
        title_lower = title.lower()
        nav_patterns = ['skip to', 'back to', 'home', 'menu', 'cookie', 'privacy']
        for pattern in nav_patterns:
            if pattern in title_lower and len(title) < 30:
                return False

        return True

    async def fetch_article_content(self, context, url: str) -> Dict[str, Any]:
        """
        抓取文章详情页内容

        Args:
            context: Playwright浏览器上下文
            url: 文章URL

        Returns:
            包含content, pub_date, screenshot_path的字典
        """
        page = None
        result = {'content': '', 'pub_date': '', 'screenshot_path': ''}

        try:
            page = await context.new_page()
            await self._goto_with_retry(page, url)

            # 等待页面加载
            await asyncio.sleep(2)

            # 提取内容
            result['content'] = await self._extract_content(page)
            result['pub_date'] = await self._extract_date(page)
            result['screenshot_path'] = await self._take_screenshot(page, url)

        except Exception as e:
            self.log_error(e, f"抓取文章失败: {url}")
        finally:
            if page:
                await page.close()

        return result

    async def _extract_content(self, page) -> str:
        """提取文章正文"""
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

        # 如果都没找到，返回body内容
        try:
            body = await page.query_selector('body')
            if body:
                return (await body.inner_text()).strip()[:15000]
        except:
            pass

        return ''

    async def _extract_date(self, page) -> str:
        """提取发布日期"""
        import re

        # 尝试各种meta标签
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
                        # 提取 YYYY-MM-DD
                        match = re.search(r'(\d{4})[-年\./](\d{1,2})[-月\./](\d{1,2})', date_str)
                        if match:
                            return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
            except:
                pass

        return ''

    async def _take_screenshot(self, page, url: str) -> str:
        """截取网页截图"""
        import os
        import hashlib
        import sys
        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        import config

        try:
            screenshot_bytes = await page.screenshot(type='jpeg', quality=60, full_page=True)

            # 生成文件名
            base = "".join([c for c in url if c.isalnum()])[:40]
            digest = hashlib.md5(url.encode()).hexdigest()[:8]
            filename = f"{base}_{digest}.jpg"

            local_path = os.path.join(config.ASSETS_DIR, filename)
            with open(local_path, 'wb') as f:
                f.write(screenshot_bytes)

            return f"assets/{filename}"
        except:
            return ''
