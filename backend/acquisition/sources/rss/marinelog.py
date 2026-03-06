"""
MarineLog Dredging RSS采集源

海事新闻网站疏浚板块
"""

from ..base import RSSSource


class MarineLogSource(RSSSource):
    """MarineLog Dredging RSS采集器"""

    name = "MarineLog Dredging"
    feed_url = "https://www.marinelog.com/category/inland-rivers-coastal-shipping/dredging/feed/"
