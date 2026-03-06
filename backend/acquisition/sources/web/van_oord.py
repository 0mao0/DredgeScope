"""
Van Oord Web采集源

荷兰Van Oord疏浚公司新闻
"""

from ..base import WebSource


class VanOordSource(WebSource):
    """Van Oord Web采集器"""

    name = "Van Oord News"
    index_url = "https://www.vanoord.com/en/news/"
    selector = "article"
    max_links = 20
