"""
微信公众号采集源实现

通过 WeWe RSS 服务获取微信公众号文章
"""

import os
import requests
import feedparser
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from database import record_source_health
import time

from ..base import BaseSource


class WeChatSource(BaseSource):
    """微信公众号采集器 (基于 WeWe RSS)"""

    source_type = "wechat"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化微信公众号采集器

        Args:
            config: 配置字典，需包含 wechat.feed_id
        """
        super().__init__(config)
        self.feed_id = self.config.get('wechat', {}).get('feed_id', '')

        # WeWe RSS 服务配置
        self.wewe_rss_url = os.getenv('WEWE_RSS_URL', 'http://localhost:4000')
        self.wewe_rss_auth = os.getenv('WEWE_RSS_AUTH_CODE', '')

    async def fetch(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        获取微信公众号文章

        Args:
            hours: 获取最近几小时的文章

        Returns:
            文章列表
        """
        if not self.feed_id:
            print(f"[WeChat:{self.name}] 错误: 未配置 feed_id")
            return []

        print(f"[WeChat:{self.name}] 正在抓取 (feed_id: {self.feed_id})")

        start_time = time.time()
        items = []
        error_msg = None

        try:
            # 构建 RSS feed URL
            feed_url = f"{self.wewe_rss_url}/feeds/{self.feed_id}.xml"

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            # 添加授权码（如果配置了）
            if self.wewe_rss_auth:
                headers['Authorization'] = f'Bearer {self.wewe_rss_auth}'

            response = requests.get(feed_url, headers=headers, timeout=30)
            response.raise_for_status()

            # 解析 RSS
            d = feedparser.parse(response.content)
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
            print(f"[WeChat:{self.name}] 成功获取 {len(items)} 篇文章")

            # 记录健康状态
            response_time = int((time.time() - start_time) * 1000)
            record_source_health(
                source_name=self.name,
                source_type='wechat',
                items_fetched=len(items),
                status='success',
                response_time_ms=response_time
            )

            return items

        except requests.exceptions.ConnectionError as e:
            error_msg = f"无法连接到 WeWe RSS 服务: {e}"
            self.log_error(e, "连接失败，请检查 WEWE_RSS_URL 配置")
            self.stats['failed'] += 1

        except Exception as e:
            error_msg = str(e)
            self.log_error(e, "抓取失败")
            self.stats['failed'] += 1

        # 记录失败状态
        response_time = int((time.time() - start_time) * 1000)
        record_source_health(
            source_name=self.name,
            source_type='wechat',
            items_fetched=0,
            status='failed',
            error_message=error_msg,
            response_time_ms=response_time
        )

        return []

    def _parse_date(self, entry) -> Optional[datetime]:
        """
        解析发布日期

        Args:
            entry: RSS entry 对象

        Returns:
            datetime 对象或 None
        """
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            return datetime(*entry.published_parsed[:6])
        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            return datetime(*entry.updated_parsed[:6])
        elif hasattr(entry, 'published') and entry.published:
            try:
                return datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %z')
            except ValueError:
                pass
        return None
