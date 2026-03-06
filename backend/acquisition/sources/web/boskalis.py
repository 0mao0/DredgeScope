"""
Boskalis Web采集源

荷兰Boskalis疏浚公司新闻
"""

from ..base import WebSource


class BoskalisSource(WebSource):
    """Boskalis Web采集器"""

    name = "Boskalis News"
    index_url = "https://boskalis.com/news"
    selector = "article"
    max_links = 20
