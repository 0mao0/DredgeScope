"""
IADC Dredging Web采集源

国际疏浚公司协会新闻
"""

from ..base import WebSource


class IADCSource(WebSource):
    """IADC Dredging Web采集器"""

    name = "IADC Dredging"
    index_url = "https://www.iadc-dredging.com/news/"
    selector = "article"
    max_links = 20
