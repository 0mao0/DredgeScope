import asyncio
import os
import sys
from datetime import datetime

# 确保可以导入 backend 下的模块
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import acquisition.info_acquisition as info_acquisition
import acquisition.wechat_acquisition as wechat_acquisition
import analysis.info_analysis as info_analysis
import reporting.report_generation as report_generation
import reporting.wecom_push as wecom_push
import config

async def run_smoke_test():
    print("🚀 启动轻量级同步测试 (Smoke Test)...")
    
    # 1. 定义精简源 (2个国内网站, 3个国外网站)
    test_sources = [
        # 国内 (CCCC)
        {
            "name": "中交上海航道局",
            "url": "https://www.cccc-sdc.com/cccc-sdc/channels/2207.html",
            "type": "web",
            "selector": ".news-list, .content-list, body",
            "max_links": 2
        },
        {
            "name": "中交天航局",
            "url": "https://www.zjthbh.com/tjsj/channels/870.html",
            "type": "web",
            "selector": ".news-list, .content-list, body",
            "max_links": 2
        },
        # 国外 (RSS + Web)
        {
            "name": "Dredging Today",
            "url": "https://dredgingtoday.com/feed/",
            "type": "rss"
        },
        {
            "name": "DredgeWire",
            "url": "https://dredgewire.com/feed/",
            "type": "rss"
        },
        {
            "name": "IADC Dredging",
            "url": "https://www.iadc-dredging.com/news/",
            "type": "web",
            "selector": "article",
            "max_links": 2
        }
    ]

    # [阶段1] 采集
    print(">>> [阶段1] 正在采集精简源数据...")
    raw_items = []
    
    # 采集 Web/RSS
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await info_acquisition.launch_chromium(p)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            ignore_https_errors=True # 忽略 HTTPS 证书错误 (如天航局官网)
        )
        
        for s in test_sources:
            if s['type'] == 'rss':
                items = await info_acquisition.fetch_rss(s['url'], hours=24, source_name=s['name'])
                raw_items.extend(items[:2]) # 每个源只取2条
            elif s['type'] == 'web':
                items = await info_acquisition.fetch_web_index(context, s)
                raw_items.extend(items[:2])
        
        await browser.close()

    # 微信公众号 (自动从 session 文件加载)
    wechat_biz_list = [
        {"name": "中交疏浚", "fakeid": "MzI1NzYwNTQ5Ng=="},
        {"name": "中交天航局", "fakeid": "MzA5NTU2NTYyNQ=="}
    ]
    wechat_items = wechat_acquisition.wechat_scraper.batch_get_articles(wechat_biz_list, count_per_biz=1)
    if wechat_items:
        print(f"成功获取 {len(wechat_items)} 条微信公众号新闻")
        raw_items.extend(wechat_items)

    print(f"共采集到 {len(raw_items)} 条潜在新闻")

    if not raw_items:
        print("未采集到任何新闻，测试结束。")
        return

    # 3. 分析数据
    print(">>> [阶段2] 正在进行智能分析 (仅分析前 3 条以节省 Token)...")
    # 为了测试快速，我们只分析前 3 条
    items_to_process = raw_items[:3]
    results = await info_analysis.process_items(items_to_process)

    # 4. 保存并生成报告
    print(">>> [阶段3] 正在保存数据并生成报告...")
    report_generation.save_history(results)
    report_generation.generate_report(results)

    # 5. 推送至企业微信
    print(">>> [阶段4] 正在推送至企业微信...")
    wecom_push.push_daily_report()
    
    print("\n✅ 轻量级同步测试完成！")
    print(f"审计文档: {config.REPORT_FILE}")

if __name__ == "__main__":
    asyncio.run(run_smoke_test())
