"""
微信公众号文章采集模块
功能：通过微信公众平台后台接口或模拟请求获取指定公众号的历史文章列表
"""

import requests
import time
import random
import logging
import json
import os
from typing import List, Dict, Any
import xml.etree.ElementTree as ET

# 设置日志
logger = logging.getLogger(__name__)

class WeChatAcquisition:
    """
    微信公众号采集类
    支持多策略：
    1. 官方后台接口 (需 Cookie，质量最高)
    2. RSSHub 路由 (免 Cookie，稳定性高)
    """
    
    def __init__(self, cookie: str = "", token: str = ""):
        """
        初始化采集器
        """
        self.cookie = cookie
        self.token = token
        self.base_url = "https://mp.weixin.qq.com/cgi-bin/appmsg"
        self.session_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "wechat_session.json")
        
        # 尝试从本地加载持久化的 Session
        self._load_session()
        
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Referer": "https://mp.weixin.qq.com/",
            "Cookie": self.cookie
        }
        
        # RSSHub 配置 (可以替换为私有实例以提高稳定性)
        self.rsshub_base = "https://rsshub.app" 

    def _save_session(self):
        """将当前 Cookie 和 Token 保存到本地"""
        try:
            os.makedirs(os.path.dirname(self.session_file), exist_ok=True)
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump({"cookie": self.cookie, "token": self.token}, f)
            logger.info("微信采集 Session 已保存到本地")
        except Exception as e:
            logger.error(f"保存微信 Session 失败: {e}")

    def _load_session(self):
        """从本地加载 Session"""
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if not self.cookie: self.cookie = data.get("cookie", "")
                    if not self.token: self.token = data.get("token", "")
                logger.info("已从本地加载微信 Session")
            except Exception as e:
                logger.error(f"加载微信 Session 失败: {e}")

    def set_auth(self, cookie: str, token: str):
        """
        更新授权信息并持久化
        """
        self.cookie = cookie
        self.token = token
        self.headers["Cookie"] = self.cookie
        self._save_session()
        logger.info("微信采集授权信息已更新并保存")

    def get_articles_by_rsshub(self, fakeid: str, count: int = 5) -> List[Dict[str, Any]]:
        """
        通过 RSSHub 获取文章 (免 Cookie 方案)
        """
        rss_url = f"{self.rsshub_base}/wechat/ershicimi/{fakeid}"
        logger.info(f"正在尝试通过 RSSHub 采集: {rss_url}")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        }
        
        try:
            response = requests.get(rss_url, headers=headers, timeout=20)
            if response.status_code != 200:
                logger.warning(f"RSSHub 请求失败 (状态码: {response.status_code})")
                return []
                
            # 解析 RSS (XML)
            root = ET.fromstring(response.content)
            articles = []
            
            # RSS 结构: channel -> item
            items = root.findall(".//item")
            for item in items[:count]:
                title_elem = item.find("title")
                link_elem = item.find("link")
                pub_date_elem = item.find("pubDate")
                
                title = title_elem.text if title_elem is not None else "无标题"
                link = link_elem.text if link_elem is not None else ""
                pub_date = pub_date_elem.text if pub_date_elem is not None else ""
                
                articles.append({
                    "title": title,
                    "link": link,
                    "date": pub_date, 
                    "source": "微信公众号 (RSS)",
                    "digest": "", 
                    "source_type": "rsshub"
                })
            
            return articles
        except Exception as e:
            logger.error(f"RSSHub 采集异常: {e}")
            return []

    def get_articles_by_biz(self, fakeid: str, count: int = 5) -> List[Dict[str, Any]]:
        """
        获取指定公众号的文章列表 (带自动回退逻辑)
        """
        # 1. 优先尝试官方接口
        articles = self._get_articles_official(fakeid, count)
        
        # 2. 如果官方接口失败 (可能是 Cookie 过期)，尝试 RSSHub
        if not articles:
            logger.warning(f"官方接口采集失败，尝试回退到 RSSHub 方案 (fakeid: {fakeid})")
            articles = self.get_articles_by_rsshub(fakeid, count)
            
        return articles

    def _get_articles_official(self, fakeid: str, count: int = 5) -> List[Dict[str, Any]]:
        """
        (内部方法) 官方后台接口采集逻辑
        """
        if not self.cookie or not self.token:
            return []

        params = {
            "action": "list_ex",
            "begin": "0",
            "count": str(count),
            "query": "",
            "fakeid": fakeid,
            "type": "9",
            "token": self.token,
            "lang": "zh_CN",
            "f": "json",
            "ajax": "1"
        }

        try:
            time.sleep(random.uniform(1, 3))
            response = requests.get(self.base_url, headers=self.headers, params=params, timeout=15)
            
            if response.status_code != 200:
                return []

            data = response.json()
            if data.get("base_resp", {}).get("ret") != 0:
                # 如果是 session 过期 (ret=200003 或 200040 等)
                ret = data.get("base_resp", {}).get("ret")
                if ret in [200003, 200040, -1]:
                    logger.warning(f"微信 Session 可能已过期 (ret={ret})")
                return []

            articles = []
            for msg in data.get("app_msg_list", []):
                articles.append({
                    "title": msg.get("title"),
                    "link": msg.get("link"),
                    "date": time.strftime("%Y-%m-%d", time.localtime(msg.get("update_time"))),
                    "source": "微信公众号",
                    "digest": msg.get("digest"),
                    "cover": msg.get("cover"),
                    "source_type": "official"
                })
            return articles
        except Exception as e:
            logger.error(f"官方接口采集异常: {e}")
            return []

    def batch_get_articles(self, biz_list: List[Dict[str, str]], count_per_biz: int = 5) -> List[Dict[str, Any]]:
        """
        批量获取多个公众号的文章
        
        :param biz_list: 包含 name 和 fakeid 的列表
        :param count_per_biz: 每个公众号获取的数量
        :return: 汇总后的文章列表
        """
        all_articles = []
        for biz_info in biz_list:
            name = biz_info.get("name")
            fakeid = biz_info.get("fakeid")
            if not fakeid:
                continue
                
            logger.info(f"正在采集公众号: {name} ({fakeid})")
            articles = self.get_articles_by_biz(fakeid, count=count_per_biz)
            
            # 注入来源名称
            for a in articles:
                a["source_name"] = name
                
            all_articles.extend(articles)
            
        return all_articles

# 导出实例供外部使用
wechat_scraper = WeChatAcquisition()
