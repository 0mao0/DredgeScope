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

    async def _launch_browser(self, p):
        """启动浏览器，忽略证书错误"""
        for channel in ["chrome", "msedge", "chromium"]:
            try:
                return await p.chromium.launch(
                    channel=channel,
                    headless=True,
                    args=["--ignore-certificate-errors", "--ignore-ssl-errors"]
                )
            except:
                pass
        return await p.chromium.launch(
            headless=True,
            args=["--ignore-certificate-errors", "--ignore-ssl-errors"]
        )
