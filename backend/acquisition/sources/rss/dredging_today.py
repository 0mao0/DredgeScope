"""
Dredging Today RSS采集源

疏浚行业知名新闻网站
"""

from ..base import RSSSource


class DredgingTodaySource(RSSSource):
    """Dredging Today RSS采集器"""

    name = "Dredging Today"
    feed_url = "https://dredgingtoday.com/feed/"
