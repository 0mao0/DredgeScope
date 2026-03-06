"""
CCCC Dredging Group Web采集源

中交疏浚集团新闻
"""

from ..base import WebSource


class CCCCDredgingSource(WebSource):
    """CCCC Dredging Group Web采集器"""

    name = "CCCC Dredging Group News"
    index_url = "https://www.cccc-cdc.com/channels/1684.html"
    selector = "body"
    max_links = 30
