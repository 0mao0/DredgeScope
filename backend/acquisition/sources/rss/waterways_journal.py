"""
Waterways Journal RSS采集源

美国内河航运新闻
"""

from ..base import RSSSource


class WaterwaysJournalSource(RSSSource):
    """Waterways Journal RSS采集器"""

    name = "Waterways Journal"
    feed_url = "https://www.waterwaysjournal.net/category/dredging/feed/"
