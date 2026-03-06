"""
MarineLog Dredging RSS采集源

海事新闻网站疏浚板块，需要特殊请求头
"""

import feedparser
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any

from ..base import RSSSource


class MarineLogSource(RSSSource):
    """MarineLog Dredging RSS采集器

    注意：该网站有反爬虫机制，需要模拟浏览器请求头
    """

    name = "MarineLog Dredging"
    # 主站RSS可以访问，分类RSS被403
    feed_url = "https://www.marinelog.com/feed/"

    async def fetch(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        获取RSS新闻，使用增强的请求头

        Args:
            hours: 获取最近几小时的新闻

        Returns:
            新闻条目列表
        """
        import asyncio

        print(f"[RSS:{self.name}] 正在抓取: {self.feed_url}")

        try:
            # 使用更完整的浏览器请求头
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "application/rss+xml, application/xml, text/xml, */*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Cache-Control": "max-age=0",
                "Referer": "https://www.marinelog.com/"
            }

            loop = asyncio.get_running_loop()

            def fetch_with_requests():
                session = requests.Session()
                # 先访问主页获取cookie
                session.get("https://www.marinelog.com/", headers=headers, timeout=10)
                # 再获取RSS
                response = session.get(self.feed_url, headers=headers, timeout=20)
                response.raise_for_status()
                return response.content

            content = await loop.run_in_executor(None, fetch_with_requests)

            # 解析RSS
            d = feedparser.parse(content)
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
