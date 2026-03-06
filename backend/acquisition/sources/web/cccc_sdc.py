"""
CCCC Shanghai Dredging Web采集源

中交上航局新闻
"""

from ..base import WebSource


class CCCCSdcSource(WebSource):
    """CCCC Shanghai Dredging Web采集器"""

    name = "CCCC Shanghai Dredging News"
    index_url = "https://www.cccc-sdc.com/cccc-sdc/channels/2207.html"
    selector = ".news-list, .content-list, body"
    max_links = 30
