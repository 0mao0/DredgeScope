"""
China Dredging Association Web采集源

中国疏浚协会市场信息
"""

from ..base import WebSource


class ChinaDredgingSource(WebSource):
    """China Dredging Association Web采集器"""

    name = "China Dredging Association"
    index_url = "http://www.chida.org/Market/"
    selector = ".content-list"
    max_links = 10
