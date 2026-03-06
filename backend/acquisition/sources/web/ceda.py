"""
CEDA Industry News Web采集源

欧洲疏浚协会新闻
"""

from ..base import WebSource


class CEDASource(WebSource):
    """CEDA Industry News Web采集器"""

    name = "CEDA Industry News"
    index_url = "https://dredging.org/news/industry-news/"
    selector = ".news-item"
    max_links = 20
    blacklist = [
        "/ceda/governance",
        "/ceda/about",
        "/ceda/member",
        "/ceda/committee"
    ]
