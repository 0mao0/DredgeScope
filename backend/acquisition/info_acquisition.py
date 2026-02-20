import asyncio
import feedparser
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
import json
import os
import config

async def fetch_rss(url, hours=24, source_name=None):
    """抓取 RSS 源"""
    print(f"[RSS] 正在抓取: {url}")
    try:
        loop = asyncio.get_running_loop()
        # Adding User-Agent to avoid 403
        d = await loop.run_in_executor(None, lambda: feedparser.parse(url, agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"))
        
        items = []
        cutoff = datetime.now() - timedelta(hours=hours)
        for entry in d.entries:
            pub_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                pub_date = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                pub_date = datetime(*entry.updated_parsed[:6])
            
            # Fallback to now if no date found, but maybe mark it
            if not pub_date: 
                pub_date = datetime.now()
            
            if pub_date > cutoff:
                items.append({
                    'title': entry.title,
                    'link': entry.link,
                    'pub_date': pub_date,
                    'summary_raw': entry.summary if hasattr(entry, 'summary') else '',
                    'source_type': 'rss',
                    'source_name': source_name or ''
                })
        return items
    except Exception as e:
        print(f"[RSS] Error {url}: {e}")
        return []

async def fetch_web_index(context, source):
    url = source['url']
    print(f"[Web] 正在扫描索引页: {url}")
    items = []
    try:
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3) # 等待渲染
        
        # 提取链接：简单的启发式，查找所有 a 标签
        # 优先使用 selector 限制范围
        selector = source.get('selector', 'body')
        
        links = await page.evaluate(f"""(selector) => {{
            const results = [];
            const container = document.querySelector('{selector}') || document.body;
            const anchors = container.querySelectorAll('a');
            anchors.forEach(a => {{
                const text = a.innerText.trim();
                const href = a.href;
                // 简单过滤：长度大于10，且不是 javascript: 或 #
                if (text.length > 10 && href.startsWith('http')) {{
                    // 去重
                    if (!results.find(r => r.link === href)) {{
                        results.push({{title: text, link: href}});
                    }}
                }}
            }});
            return results.slice(0, 10); // 只取前10个
        }}""", selector)
        
        for l in links:
            items.append({
                'title': l['title'],
                'link': l['link'],
                'pub_date': datetime.now(), # 暂无准确时间，默认最新
                'summary_raw': '',
                'source_type': 'web',
                'source_name': source.get('name', '')
            })
        await page.close()
            
    except Exception as e:
        print(f"[Web] Error {url}: {e}")
    return items

def contains_dredging_keywords(text):
    if not text:
        return False
    lower = str(text).lower()
    keywords = [
        "疏浚", "清淤", "航道", "港池", "港口", "码头", "吹填", "围填", "抛砂",
        "海岸", "海堤", "护岸", "滩涂", "采砂", "河道", "运河", "水道",
        "通航", "航运", "船闸", "船坞", "泊位", "航道整治", "水域", "滨海",
        "河湖治理", "河道治理", "清淤工程", "淤泥清理", "水环境治理", "生态修复",
        "岸线整治", "堤岸整治", "水系连通", "航道维护", "航道疏浚",
        "湖泊治理", "库区清淤", "河口治理", "海域整治", "河道保洁",
        "水利疏浚", "港池疏浚", "淤积清理", "底泥", "泥沙",
        "河道疏浚", "湖泊清淤", "清淤疏浚", "水系治理",
        "dredge", "dredging", "channel", "harbor", "harbour", "port", "berth"
    ]
    return any(k in lower for k in keywords)

async def get_all_items():
    """获取所有来源的新闻"""
    # 1. 加载源
    if not os.path.exists(config.SOURCES_FILE):
        print("未找到 sources.json")
        return []
        
    with open(config.SOURCES_FILE, 'r', encoding='utf-8') as f:
        sources = json.load(f)
    
    all_items = []
    
    # 2. 抓取 RSS
    for s in sources:
        if s.get('type') == 'rss':
            items = await fetch_rss(s['url'], source_name=s.get('name'))
            all_items.extend(items)
    
    # 3. 抓取 Web (需要 Playwright)
    # 检查是否有 Web 源
    has_web = any(s.get('type') == 'web' for s in sources)
    if has_web:
        async with async_playwright() as p:
            browser = None
            for channel in ["chrome", "msedge", "chromium"]:
                try:
                    browser = await p.chromium.launch(channel=channel, headless=True)
                    break
                except: pass
            if not browser: 
                browser = await p.chromium.launch(headless=True)
                
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                locale="zh-CN"
            )
            
            for s in sources:
                if s.get('type') == 'web':
                    web_items = await fetch_web_index(context, s)
                    all_items.extend(web_items)
            
            await browser.close()

    # 去重 (按链接)
    unique_items = []
    seen_links = set()
    for item in all_items:
        if item['link'] not in seen_links:
            unique_items.append(item)
            seen_links.add(item['link'])
            
    return unique_items
