"""
DEME Web采集源

比利时DEME疏浚公司新闻
"""

from ..base import WebSource


class DEMESource(WebSource):
    """DEME Web采集器"""

    name = "DEME News"
    index_url = "https://www.deme-group.com/news"
    selector = "article"
    max_links = 20
