"""
CEDA Industry News Web采集源

欧洲疏浚协会新闻
"""

from ..base import WebSource


class CEDASource(WebSource):
    """CEDA Industry News Web采集器"""

    name = "CEDA Industry News"
    index_url = "https://dredging.org/news/industry-news/"
    selector = ".news-item, .view-content, .content"
    max_links = 20
    blacklist = [
        "/ceda/governance",
        "/ceda/about",
        "/ceda/member",
        "/ceda/committee"
    ]

    async def _goto_with_retry(self, page, url: str):
        """带重试的页面导航，增加超时时间"""
        from playwright.async_api import TimeoutError as PlaywrightTimeout

        strategies = [
            {"wait_until": "domcontentloaded", "timeout": 30000},
            {"wait_until": "load", "timeout": 60000},
            {"wait_until": "networkidle", "timeout": 60000}
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
