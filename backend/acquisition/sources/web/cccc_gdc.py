"""
CCCC Guangzhou Dredging Web采集源

中交广航局新闻
"""

from ..base import WebSource


class CCCCGdcSource(WebSource):
    """CCCC Guangzhou Dredging Web采集器"""

    name = "CCCC Guangzhou Dredging News"
    index_url = "https://www.ccgdc.com/cccc-gdc/channels/1945.html"
    selector = ".news-list, .content-list, body"
    max_links = 30
