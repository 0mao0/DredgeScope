"""
DredgeWire RSS采集源

美国疏浚行业新闻网站，响应较慢需要特殊处理
"""

from ..base import RSSSource


class DredgeWireSource(RSSSource):
    """DredgeWire RSS采集器
    
    注意：该网站响应较慢，网页抓取时需要增加超时时间
    """

    name = "DredgeWire"
    feed_url = "https://dredgewire.com/feed/"
