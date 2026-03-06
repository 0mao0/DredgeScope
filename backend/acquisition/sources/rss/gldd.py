"""
Great Lakes Dredge & Dock RSS采集源

美国最大疏浚公司新闻发布
"""

from ..base import RSSSource


class GLDDSource(RSSSource):
    """Great Lakes Dredge & Dock RSS采集器"""

    name = "Great Lakes Dredge & Dock"
    feed_url = "https://investor.gldd.com/rss/news-releases.xml"
