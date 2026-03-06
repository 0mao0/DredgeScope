"""
Jan De Nul Web采集源

比利时Jan De Nul疏浚公司新闻
"""

from ..base import WebSource


class JanDeNulSource(WebSource):
    """Jan De Nul Web采集器"""

    name = "Jan De Nul News"
    index_url = "https://www.jandenul.com/en/news/"
    selector = "article"
    max_links = 20
