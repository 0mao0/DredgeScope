"""
Dredging Contractors of America Web采集源

美国疏浚承包商协会新闻
"""

from ..base import WebSource


class DredgingContractorsSource(WebSource):
    """Dredging Contractors of America Web采集器"""

    name = "Dredging Contractors of America"
    index_url = "https://dredgingcontractors.org/news"
    selector = ".news-item"
    max_links = 20
    blacklist = [
        "/dredging-101/",
        "/maritime-links/"
    ]
