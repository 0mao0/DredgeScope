import os
import sys
import unittest
from playwright.async_api import async_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import acquisition.info_acquisition as info_acquisition


class TestAcquisitionUI(unittest.IsolatedAsyncioTestCase):
    async def test_acquisition_flow(self):
        """验证采集流程与页面可访问性"""
        items = await info_acquisition.get_all_items()
        self.assertGreater(len(items), 0, "采集结果为空，无法验证采集链路")
        sample = items[0]
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(sample["link"], wait_until="domcontentloaded", timeout=30000)
            page_title = await page.title()
            await browser.close()
        self.assertTrue(page_title, "页面标题为空，可能未正常加载")
