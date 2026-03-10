"""
微信公众号采集源

基于 WeWe RSS（微信读书）获取公众号文章
需自部署 WeWe RSS 服务：https://github.com/cooderl/wewe-rss

配置格式示例（sources.json）：
{
    "name": "中交疏浚",
    "type": "wechat",
    "wechat": {
        "feed_id": "MP_WXS_xxxxx"
    }
}
"""

import asyncio
import json
import os
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from datetime import datetime

import requests

from ..base import BaseSource


class WeChatSource(BaseSource):
    """微信公众号采集器（基于 WeWe RSS）"""

    name = "WeChat"
    source_type = "wechat"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)

        # 支持 Docker 内部网络通信，优先使用内部地址
        self.wewe_rss_base = os.getenv(
            "WEWE_RSS_URL",
            "http://wewe-rss:4000"  # Docker 内部网络地址
        )
        self.auth_code = os.getenv("WEWE_RSS_AUTH_CODE", "dredge2024")

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/xml, application/rss+xml, application/atom+xml, application/json, */*",
            "Authorization": self.auth_code,
        }

    async def fetch(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        获取所有配置的公众号文章

        Args:
            hours: 获取最近几小时的文章（用于时间过滤）

        Returns:
            文章列表
        """
        import time
        from database import record_source_health

        config_path = self._get_config_path()
        wechat_sources = self._load_wechat_sources(config_path)

        if not wechat_sources:
            print("[WeChat] 未找到微信公众号配置")
            return []

        all_items = []
        for source in wechat_sources:
            start_time = time.time()
            try:
                print(f"[WeChat] 正在采集: {source['name']}")
                items = await self._fetch_source(source, count=10)
                for item in items:
                    item["source_name"] = source["name"]
                all_items.extend(items)
                print(f"[WeChat] {source['name']} 获取 {len(items)} 篇文章")

                response_time = int((time.time() - start_time) * 1000)
                record_source_health(
                    source_name=source['name'],
                    source_type='wechat',
                    items_fetched=len(items),
                    status='success',
                    response_time_ms=response_time
                )
            except Exception as e:
                self.log_error(e, f"采集 {source['name']} 失败")
                response_time = int((time.time() - start_time) * 1000)
                record_source_health(
                    source_name=source['name'],
                    source_type='wechat',
                    items_fetched=0,
                    status='failed',
                    error_message=str(e),
                    response_time_ms=response_time
                )

        return all_items

    def _get_config_path(self) -> str:
        """获取配置文件路径"""
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "static", "sources.json"
        )

    def _load_wechat_sources(self, config_path: str) -> List[Dict[str, Any]]:
        """从配置文件加载微信公众号列表"""
        wechat_sources = []
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                sources = json.load(f)
                for src in sources:
                    if src.get("type") == "wechat":
                        wechat_sources.append(src)
        except Exception as e:
            print(f"[WeChat] 加载配置失败: {e}")
        return wechat_sources

    async def _fetch_source(self, source: Dict[str, Any], count: int = 10) -> List[Dict[str, Any]]:
        """
        获取单个公众号的文章

        Args:
            source: 公众号配置
            count: 获取数量

        Returns:
            文章列表
        """
        wechat_config = source.get("wechat", {})
        feed_id = wechat_config.get("feed_id")

        if not feed_id:
            print(f"[WeChat] 未配置 feed_id: {source['name']}")
            return []

        rss_url = f"{self.wewe_rss_base}/feeds/{feed_id}.rss"
        print(f"[WeChat] 请求 WeWe RSS: {rss_url}")

        return await self._fetch_rss(rss_url, count)

    async def _fetch_rss(self, rss_url: str, count: int) -> List[Dict[str, Any]]:
        """
        获取并解析 RSS 内容

        Args:
            rss_url: RSS 地址
            count: 获取数量

        Returns:
            文章列表
        """
        try:
            response = requests.get(rss_url, headers=self.headers, timeout=30)

            if response.status_code == 401:
                print(f"[WeChat] ⚠️ 认证失败！请检查 WeWe RSS 的 AUTH_CODE 配置，或账号登录状态可能已过期")
                raise Exception("WeWe RSS 认证失败 (401)，请检查 AUTH_CODE 或重新扫码登录")

            if response.status_code == 404:
                print(f"[WeChat] feed_id 不存在，请检查配置")
                raise Exception(f"WeWe RSS feed_id 不存在 (404)")

            if response.status_code == 500:
                print(f"[WeChat] ⚠️ WeWe RSS 服务内部错误，可能需要重新扫码登录")
                raise Exception("WeWe RSS 服务错误 (500)，账号可能已过期")

            if response.status_code != 200:
                print(f"[WeChat] RSS 请求失败: HTTP {response.status_code}")
                raise Exception(f"WeWe RSS 请求失败: HTTP {response.status_code}")

            articles = self._parse_rss(response.content, count)

            if not articles:
                print(f"[WeChat] ⚠️ RSS 返回空内容，可能需要检查 WeWe RSS 账号状态")

            return articles

        except requests.exceptions.Timeout:
            print(f"[WeChat] RSS 请求超时")
            raise Exception("WeWe RSS 请求超时")
        except requests.exceptions.RequestException as e:
            print(f"[WeChat] RSS 请求异常: {e}")
            raise Exception(f"WeWe RSS 请求异常: {e}")
        except Exception as e:
            if "WeWe RSS" in str(e):
                raise
            self.log_error(e, "RSS 解析失败")
            raise Exception(f"RSS 解析失败: {e}")

    def _parse_rss(self, content: bytes, count: int) -> List[Dict[str, Any]]:
        """
        解析 RSS 内容

        Args:
            content: RSS XML 内容
            count: 获取数量

        Returns:
            文章列表
        """
        articles = []

        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            print(f"[WeChat] XML 解析失败: {e}")
            return []

        items = root.findall(".//item")
        if not items:
            items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

        for item in items[:count]:
            article = self._parse_rss_item(item)
            if article:
                articles.append(article)

        return articles

    def _parse_rss_item(self, item) -> Optional[Dict[str, Any]]:
        """
        解析单个 RSS item

        Args:
            item: XML 元素

        Returns:
            文章字典或 None
        """
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        title_elem = item.find("title")
        link_elem = item.find("link")
        pub_date_elem = item.find("pubDate")
        description_elem = item.find("description")
        content_elem = item.find("content:encoded", namespaces={"content": "http://purl.org/rss/1.0/modules/content/"})

        if title_elem is None:
            title_elem = item.find("atom:title", ns)
        if link_elem is None:
            link_elem = item.find("atom:link", ns)
            if link_elem is not None:
                link = link_elem.get("href", "")
            else:
                link = ""
        else:
            link = link_elem.text or ""
        if pub_date_elem is None:
            pub_date_elem = item.find("atom:published", ns)

        title = title_elem.text if title_elem is not None else ""
        pub_date_raw = pub_date_elem.text if pub_date_elem is not None else ""

        if content_elem is not None and content_elem.text:
            description = content_elem.text
        elif description_elem is not None and description_elem.text:
            description = description_elem.text
        else:
            description = ""

        if not title:
            return None

        pub_date = self._parse_pub_date(pub_date_raw)

        return {
            'title': title.strip(),
            'link': link.strip(),
            'pub_date': pub_date,
            'summary_raw': description.strip()[:500] if description else "",
            'source_type': 'wechat',
            'source_name': ''
        }

    def _parse_pub_date(self, pub_date_raw: str) -> str:
        """
        解析发布日期

        Args:
            pub_date_raw: 原始日期字符串

        Returns:
            格式化的日期字符串 (YYYY-MM-DD)
        """
        if not pub_date_raw:
            return ""

        date_formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S GMT",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]

        for fmt in date_formats:
            try:
                dt = datetime.strptime(pub_date_raw.strip(), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        return ""
