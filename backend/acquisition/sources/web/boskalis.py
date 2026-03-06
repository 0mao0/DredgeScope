"""
Boskalis Web采集源

荷兰Boskalis疏浚公司新闻
注意：该网站使用动态加载，需要特殊处理
"""

from playwright.async_api import Page
from typing import List, Dict, Any
import asyncio

from ..base import WebSource


class BoskalisSource(WebSource):
    """Boskalis Web采集器

    注意：该网站使用JavaScript动态加载内容，需要等待渲染
    """

    name = "Boskalis News"
    # 正确的URL是 /press/ 而不是 /news/
    index_url = "https://boskalis.com/press/press-releases-and-company-news"
    selector = "body"
    max_links = 20

    async def fetch(self, hours: int = 24) -> List[Dict[str, Any]]:
        """获取新闻，增加等待时间让JavaScript渲染"""
        from playwright.async_api import async_playwright

        print(f"[Web:{self.name}] 正在扫描: {self.index_url}")

        try:
            async with async_playwright() as p:
                browser = await self._launch_browser(p)
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )

                page = await context.new_page()
                await self._goto_with_retry(page, self.index_url)

                # 等待JavaScript渲染 - 增加等待时间
                await asyncio.sleep(5)

                # 尝试滚动页面触发懒加载
                await page.evaluate("""() => {
                    window.scrollTo(0, document.body.scrollHeight);
                }""")
                await asyncio.sleep(3)

                # 提取链接
                links = await self._extract_links(page)

                await browser.close()

                # 过滤有效链接
                items = []
                for link in links[:self.max_links]:
                    if self._is_valid_link(link['url'], link['title']):
                        items.append(self.normalize_item({
                            'title': link['title'],
                            'link': link['url'],
                            'pub_date': '',
                            'summary_raw': '',
                        }))

                self.stats['fetched'] = len(items)
                self.stats['success'] = len(items)
                print(f"[Web:{self.name}] 成功获取 {len(items)} 条新闻链接")
                return items

        except Exception as e:
            self.log_error(e, "Web抓取失败")
            self.stats['failed'] += 1
            return []

    async def _extract_links(self, page: Page) -> List[Dict[str, str]]:
        """从Boskalis页面提取新闻链接"""
        return await page.evaluate("""() => {
            const results = [];

            // 尝试多种可能的选择器
            const selectors = [
                'article a', '.news-item a', '.card a', '.news a',
                '.press-item a', '.release a', '.item a',
                '[class*="news"] a', '[class*="press"] a',
                '.overview a', '.listing a', '.items a',
                'h2 a', 'h3 a', 'h4 a'  // 标题链接
            ];

            for (const selector of selectors) {
                const links = document.querySelectorAll(selector);
                links.forEach(a => {
                    const text = a.innerText.trim();
                    const href = a.href;
                    if (text.length > 15 && href &&
                        (href.includes('boskalis.com') || href.startsWith('/')) &&
                        !href.includes('unsubscribe') &&
                        !href.includes('subscription') &&
                        !href.includes('media-library') &&
                        !href.includes('#')) {
                        // 转换为绝对URL
                        const absoluteUrl = href.startsWith('/') ? 'https://boskalis.com' + href : href;
                        if (!results.find(r => r.url === absoluteUrl)) {
                            results.push({title: text, url: absoluteUrl});
                        }
                    }
                });
            }

            // 如果上面没找到，尝试更通用的方式
            if (results.length === 0) {
                const allLinks = document.querySelectorAll('a');
                allLinks.forEach(a => {
                    const text = a.innerText.trim();
                    const href = a.href;
                    // Boskalis新闻链接通常包含 /press/ 或特定模式
                    if (text.length > 20 && href &&
                        (href.includes('/press/') || href.includes('/news/')) &&
                        !href.includes('unsubscribe') &&
                        !href.includes('subscription') &&
                        !href.includes('media-library') &&
                        !href.includes('#')) {
                        const absoluteUrl = href.startsWith('/') ? 'https://boskalis.com' + href : href;
                        if (!results.find(r => r.url === absoluteUrl)) {
                            results.push({title: text, url: absoluteUrl});
                        }
                    }
                });
            }

            return results;
        }""")

    def _is_valid_link(self, url: str, title: str) -> bool:
        """检查链接是否有效"""
        if not url or not title:
            return False

        # 过滤导航类链接
        url_lower = url.lower()
        title_lower = title.lower()

        # 排除特定路径
        exclude_patterns = [
            'unsubscribe', 'subscription', 'media-library',
            'cookie', 'privacy', 'terms', 'contact',
            'about', 'career', 'investor'
        ]

        for pattern in exclude_patterns:
            if pattern in url_lower or pattern in title_lower:
                return False

        # 标题不能太短
        if len(title) < 15:
            return False

        return True
