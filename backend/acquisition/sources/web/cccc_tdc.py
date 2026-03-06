"""
CCCC Tianjin Dredging Web采集源

中交天航局新闻
"""

from ..base import WebSource


class CCCCTdcSource(WebSource):
    """CCCC Tianjin Dredging Web采集器"""

    name = "CCCC Tianjin Dredging News"
    index_url = "https://www.zjthbh.com/tjsj/channels/870.html"
    selector = ".news-list, .content-list, body"
    max_links = 30
