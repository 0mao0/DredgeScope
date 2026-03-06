"""
微信公众号采集源

支持多策略：
1. 官方后台接口 (需 Cookie，质量最高)
2. RSSHub 路由 (免 Cookie，稳定性高)
"""

import asyncio
import json
import os
import time
import random
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from datetime import datetime

import requests

from ..base import BaseSource


class WeChatSource(BaseSource):
    """微信公众号采集器"""

    name = "WeChat"
    source_type = "wechat"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.cookie = ""
        self.token = ""
        self.base_url = "https://mp.weixin.qq.com/cgi-bin/appmsg"
        self.session_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "static", "wechat_session.json"
        )

        # 加载本地Session
        self._load_session()

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://mp.weixin.qq.com/",
            "Cookie": self.cookie
        }

        # RSSHub配置
        self.rsshub_bases = [
            "https://rsshub.app",
            "https://rsshub.rssforever.com"
        ]

    def _load_session(self):
        """从本地加载Session"""
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.cookie = data.get("cookie", "")
                    self.token = data.get("token", "")
                print("[WeChat] 已从本地加载Session")
            except Exception as e:
                print(f"[WeChat] 加载Session失败: {e}")

    def _save_session(self):
        """保存Session到本地"""
        try:
            os.makedirs(os.path.dirname(self.session_file), exist_ok=True)
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump({"cookie": self.cookie, "token": self.token}, f)
        except Exception as e:
            print(f"[WeChat] 保存Session失败: {e}")

    def set_auth(self, cookie: str, token: str):
        """更新授权信息"""
        self.cookie = cookie
        self.token = token
        self.headers["Cookie"] = self.cookie
        self._save_session()
        print("[WeChat] 授权信息已更新")

    async def fetch(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        获取所有配置的公众号文章

        Args:
            hours: 获取最近几小时的文章

        Returns:
            文章列表
        """
        # 从配置文件加载公众号列表
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "static", "sources.json"
        )

        wechat_biz_list = []
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                sources = json.load(f)
                for src in sources:
                    if src.get("type") == "wechat" and src.get("fakeid"):
                        wechat_biz_list.append({
                            "name": src.get("name"),
                            "fakeid": src.get("fakeid")
                        })
        except Exception as e:
            print(f"[WeChat] 加载配置失败: {e}")
            return []

        all_items = []
        for biz in wechat_biz_list:
            try:
                items = await self.fetch_by_biz(biz["fakeid"], count=10)
                for item in items:
                    item["source_name"] = biz["name"]
                all_items.extend(items)
            except Exception as e:
                self.log_error(e, f"采集 {biz['name']} 失败")

        return all_items

    async def fetch_by_biz(self, fakeid: str, count: int = 5) -> List[Dict[str, Any]]:
        """
        获取指定公众号的文章

        Args:
            fakeid: 公众号fakeid
            count: 获取数量

        Returns:
            文章列表
        """
        # 优先尝试官方接口
        articles = await self._fetch_official(fakeid, count)

        # 如果失败，回退到RSSHub
        if not articles:
            print(f"[WeChat] 官方接口失败，尝试RSSHub (fakeid: {fakeid})")
            articles = await self._fetch_rsshub(fakeid, count)

        return articles

    async def _fetch_official(self, fakeid: str, count: int, max_pages: int = 5) -> List[Dict[str, Any]]:
        """通过官方接口获取"""
        if not self.cookie or not self.token:
            return []

        articles = []
        begin = 0
        page = 0

        while len(articles) < count and page < max_pages:
            page_size = min(20, count - len(articles))
            params = {
                "action": "list_ex",
                "begin": str(begin),
                "count": str(page_size),
                "query": "",
                "fakeid": fakeid,
                "type": "9",
                "token": self.token,
                "lang": "zh_CN",
                "f": "json",
                "ajax": "1"
            }

            await asyncio.sleep(random.uniform(1, 3))

            try:
                response = requests.get(
                    self.base_url,
                    headers=self.headers,
                    params=params,
                    timeout=15
                )

                if response.status_code != 200:
                    break

                data = response.json()
                if data.get("base_resp", {}).get("ret") != 0:
                    ret = data.get("base_resp", {}).get("ret")
                    if ret in [200003, 200040, -1]:
                        print(f"[WeChat] Session可能已过期 (ret={ret})")
                    break

                app_list = data.get("app_msg_list", [])
                if not app_list:
                    break

                for msg in app_list:
                    articles.append({
                        'title': msg.get("title"),
                        'link': msg.get("link"),
                        'pub_date': time.strftime("%Y-%m-%d", time.localtime(msg.get("update_time"))),
                        'summary_raw': msg.get("digest", ""),
                        'source_type': 'wechat',
                        'source_name': '',
                        'cover': msg.get("cover")
                    })

                    if len(articles) >= count:
                        break

                begin += page_size
                page += 1

            except Exception as e:
                self.log_error(e, "官方接口请求失败")
                break

        return articles

    async def _fetch_rsshub(self, fakeid: str, count: int = 5) -> List[Dict[str, Any]]:
        """通过RSSHub获取"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        for base in self.rsshub_bases:
            rss_url = f"{base.rstrip('/')}/wechat/ershicimi/{fakeid}"
            print(f"[WeChat] 尝试RSSHub: {rss_url}")

            try:
                response = requests.get(rss_url, headers=headers, timeout=20)

                if response.status_code != 200:
                    continue

                root = ET.fromstring(response.content)
                articles = []
                items = root.findall(".//item")

                for item in items[:count]:
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    pub_date_elem = item.find("pubDate")

                    title = title_elem.text if title_elem is not None else "无标题"
                    link = link_elem.text if link_elem is not None else ""
                    pub_date = pub_date_elem.text if pub_date_elem is not None else ""

                    # 解析日期
                    pub_date_normalized = ""
                    if pub_date:
                        try:
                            dt = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %z")
                            pub_date_normalized = dt.strftime("%Y-%m-%d")
                        except:
                            pass

                    articles.append({
                        'title': title,
                        'link': link,
                        'pub_date': pub_date_normalized,
                        'summary_raw': '',
                        'source_type': 'wechat',
                        'source_name': ''
                    })

                if articles:
                    return articles

            except Exception as e:
                self.log_error(e, f"RSSHub请求失败: {base}")
                continue

        return []
