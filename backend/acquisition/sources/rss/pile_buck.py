"""
Pile Buck Magazine RSS采集源

桩基与疏浚工程杂志
"""

from ..base import RSSSource


class PileBuckSource(RSSSource):
    """Pile Buck Magazine RSS采集器"""

    name = "Pile Buck Magazine"
    feed_url = "https://pilebuck.com/feed"
