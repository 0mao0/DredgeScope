import asyncio
import feedparser
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
import json
import os
import hashlib
import re
from email.utils import parsedate_to_datetime
import config

async def launch_chromium(p):
    """启动 Chromium 浏览器，必要时回退到系统浏览器路径"""
    last_error = None
    for channel in ["chrome", "msedge", "chromium"]:
        try:
            return await p.chromium.launch(channel=channel, headless=True)
        except Exception as e:
            last_error = e
    try:
        return await p.chromium.launch(headless=True)
    except Exception as e:
        last_error = e
    candidates = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable"
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return await p.chromium.launch(headless=True, executable_path=path)
            except Exception as e:
                last_error = e
    if last_error:
        raise last_error
    raise RuntimeError("Playwright 浏览器启动失败，未找到可用 Chromium 可执行文件")

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
            pub_dt = None
            pub_text = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                pub_dt = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                pub_dt = datetime(*entry.updated_parsed[:6])
            else:
                pub_text = _normalize_publish_date(entry.get("published") or entry.get("updated"))
                if pub_text:
                    try:
                        pub_dt = datetime.strptime(pub_text, "%Y-%m-%d")
                    except Exception:
                        pub_dt = None

            if not pub_dt:
                continue

            if pub_dt > cutoff:
                items.append({
                    'title': entry.title,
                    'link': entry.link,
                    'pub_date': pub_dt.strftime("%Y-%m-%d"),
                    'summary_raw': entry.summary if hasattr(entry, 'summary') else '',
                    'source_type': 'rss',
                    'source_name': source_name or ''
                })
        return items
    except Exception as e:
        print(f"[RSS] Error {url}: {e}")
        return []

async def goto_with_retry(page, url, attempts):
    """按多策略尝试打开页面，成功则返回 True，失败抛出最后异常"""
    last_error = None
    for attempt in attempts:
        try:
            await page.goto(url, wait_until=attempt["wait_until"], timeout=attempt["timeout_ms"])
            return True
        except Exception as e:
            last_error = e
    if last_error:
        raise last_error
    return False

async def fetch_web_index(context, source):
    """抓取网站索引页并提取候选链接"""
    url = source['url']
    print(f"[Web] 正在扫描索引页: {url}")
    items = []
    page = None
    try:
        page = await context.new_page()
        await goto_with_retry(
            page,
            url,
            [
                {"wait_until": "domcontentloaded", "timeout_ms": 30000},
                {"wait_until": "networkidle", "timeout_ms": 30000},
                {"wait_until": "load", "timeout_ms": 30000}
            ]
        )
        # 增加滚动以触发懒加载
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(5)
        
        # Cloudflare / Error Check
        current_url = page.url
        title = await page.title()
        if "cloudflare.com" in current_url or "5xx-error" in current_url or \
           "Just a moment" in title or "Attention Required" in title or \
           "Security Check" in title:
            print(f"[Web] Skip Cloudflare/Error page: {url} -> {current_url}")
            return []

        # 提取链接：简单的启发式，查找所有 a 标签
        # 优先使用 selector 限制范围
        selector = source.get('selector', 'body')
        max_links = source.get('max_links', 10)
        
        links = await page.evaluate("""(params) => {
            const selector = params.selector;
            const maxLinks = params.maxLinks;
            const results = [];
            const container = document.querySelector(selector) || document.body;
            const anchors = container.querySelectorAll('a');
            anchors.forEach(a => {
                const text = a.innerText.trim();
                const href = a.href;
                // 简单过滤：长度大于10，且不是 javascript: 或 #
                if (text.length > 10 && href.startsWith('http')) {
                    // 去重
                    if (!results.find(r => r.link === href)) {
                        results.push({title: text, link: href});
                    }
                }
            });
            return results.slice(0, maxLinks);
        }""", {"selector": selector, "maxLinks": max_links})
        
        for l in links:
            # Filter out cloudflare links
            if "cloudflare.com" in l['link'] or "5xx-error" in l['link']:
                continue
            
            # 应用源配置的黑名单
            blacklist = source.get('blacklist', [])
            if blacklist:
                link_lower = l['link'].lower()
                if any(pattern.lower() in link_lower for pattern in blacklist):
                    print(f"[Web] 黑名单过滤: {l['title']} -> {l['link']}")
                    continue
            
            # 过滤非新闻类页面（委员会、About、Team等）
            if not is_news_page(l['link'], l['title']):
                print(f"[Web] 过滤非新闻页面: {l['title']} -> {l['link']}")
                continue

            items.append({
                'title': l['title'],
                'link': l['link'],
                'pub_date': '',
                'summary_raw': '',
                'source_type': 'web',
                'source_name': source.get('name', '')
            })
    except Exception as e:
        print(f"[Web] Error {url}: {e}")
    finally:
        if page:
            await page.close()
    return items

def _is_security_interstitial(title, url):
    title = (title or "").lower()
    url = (url or "").lower()
    if url.startswith("chrome-error://") or "net::err_cert" in title:
        return True
    keywords = [
        "your connection is not private",
        "privacy error",
        "connection is not secure",
        "您的连接不是私密连接",
        "您的连接不是安全连接",
        "此连接不是私密连接"
    ]
    return any(k in title for k in keywords)

def _clean_text(text_content):
    normalized = text_content.replace("\r", "\n")
    lines = [line.strip() for line in normalized.split("\n")]
    keywords = [
        "skip to main content",
        "about",
        "what we do",
        "home",
        "menu",
        "search",
        "privacy policy",
        "terms of use",
        "cookie",
        "contact",
        "subscribe",
        "sign in",
        "register",
        "login",
        "language"
    ]
    cleaned = []
    for line in lines:
        if not line:
            continue
        lower = line.lower()
        short_line = len(line) <= 50 and len(line.split()) <= 6
        if short_line and any(k in lower for k in keywords):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)

def _normalize_publish_date(value):
    """解析发布日期并返回 YYYY-MM-DD"""
    if not value:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    if not text:
        return None
    try:
        if "," in text and any(x in text for x in ["GMT", "+", "-"]):
            dt = parsedate_to_datetime(text)
            if dt:
                return dt.date().isoformat()
    except Exception:
        pass
    try:
        cleaned = text.replace("年", "-").replace("月", "-").replace("日", "")
        cleaned = cleaned.replace("/", "-")
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        if "T" in cleaned:
            dt = datetime.fromisoformat(cleaned)
            return dt.date().isoformat()
        if " " in cleaned and ":" in cleaned:
            dt = datetime.fromisoformat(cleaned.replace(" ", "T"))
            return dt.date().isoformat()
    except Exception:
        pass
    match = re.search(r"(\d{4})[./\-年](\d{1,2})[./\-月](\d{1,2})", text)
    if match:
        y, m, d = match.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    return None

def _safe_filename(title, url):
    base = "".join([c for c in str(title or "") if c.isalnum() or c in (" ", "-", "_")]).strip()
    if not base:
        base = "article"
    base = base.replace(" ", "_")[:40]
    digest = hashlib.md5(f"{title}|{url}".encode("utf-8")).hexdigest()[:8]
    return f"{base}_{digest}.jpg"

async def fetch_web_article(context, item):
    url = item.get("link")
    if not url:
        return item
    page = None
    text_content = ""
    screenshot_path = ""
    try:
        page = await context.new_page()
        await goto_with_retry(
            page,
            url,
            [
                {"wait_until": "domcontentloaded", "timeout_ms": 30000},
                {"wait_until": "networkidle", "timeout_ms": 30000},
                {"wait_until": "load", "timeout_ms": 30000}
            ]
        )
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(2)
        await page.evaluate("window.scrollTo(0, 0)")

        page_title = ""
        page_url = ""
        try:
            page_title = await page.title()
            page_url = page.url
        except:
            page_title = ""
            page_url = ""

        if not _is_security_interstitial(page_title, page_url):
            try:
                await page.evaluate("""() => {
                    const keywords = ['cookie', 'consent', 'gdpr', 'banner', 'popup', 'newsletter', 'subscribe', 'ad-', 'notice', 'policy', 'privacy'];
                    const cmpIds = ['onetrust-banner-sdk', 'CybotCookiebotDialog', 'usercentrics-root', 'cmpbox', 'cmp-container', 'cookie-law-info-bar'];
                    cmpIds.forEach(id => {
                        const el = document.getElementById(id);
                        if (el) el.remove();
                    });
                    document.querySelectorAll('*').forEach(el => {
                        const style = window.getComputedStyle(el);
                        if (style.position === 'fixed' || style.position === 'sticky') {
                            const id = (el.id || '').toLowerCase();
                            const className = (el.className || '').toString().toLowerCase();
                            const zIndex = parseInt(style.zIndex) || 0;
                            const tagName = el.tagName.toLowerCase();
                            if (keywords.some(k => id.includes(k) || className.includes(k))) {
                                el.remove();
                                return;
                            }
                            const rect = el.getBoundingClientRect();
                            const isBanner = (rect.height < 250 && rect.width > window.innerWidth * 0.8);
                            const isAtEdge = (rect.top < 100 || rect.bottom > window.innerHeight - 100);
                            if (isBanner && isAtEdge) {
                                if (!(id.includes('nav') || id.includes('header') || className.includes('nav') || className.includes('header') || tagName === 'nav' || tagName === 'header')) {
                                    el.remove();
                                    return;
                                }
                            }
                            if (rect.width > window.innerWidth * 0.9 && rect.height > window.innerHeight * 0.9 && zIndex > 50) {
                                el.remove();
                                return;
                            }
                        }
                    });
                    document.querySelectorAll('.modal-backdrop, .overlay, .fade.in, [class*="overlay"], [class*="backdrop"]').forEach(el => el.remove());
                    document.body.style.overflow = 'auto';
                    document.documentElement.style.overflow = 'auto';
                }""")
                await asyncio.sleep(1.0)
            except:
                pass

            try:
                text_content = await page.evaluate("""() => {
                    const selectors = [
                        'article',
                        '.post-content',
                        '.entry-content',
                        '.article-content',
                        '.article-body',
                        '.main-content',
                        'main',
                        '#content',
                        '.content'
                    ];
                    let articleElement = null;
                    for (const selector of selectors) {
                        const el = document.querySelector(selector);
                        if (el && el.innerText.trim().length > 200) {
                            articleElement = el;
                            break;
                        }
                    }
                    if (!articleElement) {
                        articleElement = document.body;
                    }
                    const cleanElement = articleElement.cloneNode(true);
                    const toRemove = cleanElement.querySelectorAll('script, style, nav, header, footer, aside, .sidebar, .ads, .menu');
                    toRemove.forEach(el => el.remove());
                    return cleanElement.innerText.slice(0, 15000);
                }""")
            except:
                text_content = ""

            if text_content:
                text_content = _clean_text(text_content)

            if not item.get("pub_date"):
                try:
                    raw_date = await page.evaluate("""() => {
                        const selectors = [
                            'meta[property="article:published_time"]',
                            'meta[property="og:published_time"]',
                            'meta[name="publishdate"]',
                            'meta[name="pubdate"]',
                            'meta[name="publish-date"]',
                            'meta[name="date"]',
                            'meta[itemprop="datePublished"]',
                            'meta[name="parsely-pub-date"]'
                        ];
                        for (const sel of selectors) {
                            const el = document.querySelector(sel);
                            if (el && el.content) return el.content;
                        }
                        const timeEl = document.querySelector('time[datetime]');
                        if (timeEl && timeEl.getAttribute('datetime')) {
                            return timeEl.getAttribute('datetime');
                        }
                        const timeText = document.querySelector('time');
                        if (timeText && timeText.innerText) {
                            return timeText.innerText;
                        }
                        return '';
                    }""")
                except Exception:
                    raw_date = ""
                normalized = _normalize_publish_date(raw_date)
                if normalized:
                    item["pub_date"] = normalized

            try:
                locator = page.locator('article').first
                box = None
                if await locator.count() > 0:
                    box = await locator.bounding_box()
                if box:
                    screenshot_bytes = await page.screenshot(type='jpeg', quality=70, clip=box)
                else:
                    await page.set_viewport_size({"width": 1280, "height": 1500})
                    screenshot_bytes = await page.screenshot(type='jpeg', quality=60, full_page=True)
                filename = _safe_filename(item.get("title"), url)
                local_path = os.path.join(config.ASSETS_DIR, filename)
                with open(local_path, 'wb') as f:
                    f.write(screenshot_bytes)
                screenshot_path = f"assets/{filename}"
            except:
                screenshot_path = ""
    except Exception as e:
        print(f"[Web] 内容抓取失败: {url} -> {e}")
    finally:
        if page:
            await page.close()

    if text_content:
        item["content"] = text_content
    if screenshot_path:
        item["screenshot_path"] = screenshot_path
    return item

async def enrich_web_items(context, items):
    if not items:
        return []
    results = []
    sem = asyncio.Semaphore(3)

    async def runner(item):
        async with sem:
            source_type = (item.get("source_type") or "").lower()
            link = (item.get("link") or "").lower()
            if source_type in ["web", "wechat", "official", "rsshub"] or "mp.weixin.qq.com" in link:
                await fetch_web_article(context, item)
            results.append(item)

    tasks = [runner(item) for item in items]
    await asyncio.gather(*tasks)
    return results

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

def is_news_page(url, title):
    """
    判断是否为新闻类页面，排除委员会、About、Team等非新闻页面
    """
    if not url:
        return False
    
    url_lower = url.lower()
    title_lower = title.lower() if title else ""
    
    # 1. 过滤带锚点的URL（如 #a11y-footer, #top）
    if '#' in url:
        return False
    
    # 2. 过滤 /expertise/ 等专业领域/服务页面
    if '/expertise/' in url_lower or '/services/' in url_lower or '/solutions/' in url_lower:
        return False
    
    # 3. 过滤 /updates/ 索引页（这是列表页，不是具体新闻）
    if url_lower.endswith('/updates/') or url_lower.endswith('/updates'):
        return False
    
    # 4. 过滤导航类标题
    skip_title_patterns = [
        'skip to', 'back to', 'return to', 'go to',
        'home', 'homepage', 'frontpage', 'main menu',
        'previous', 'next', 'read more', 'learn more',
        'cookie', 'accept', 'agree', 'privacy policy',
        'terms of', 'contact us', 'about us'
    ]
    for pattern in skip_title_patterns:
        if pattern in title_lower and len(title.strip()) < 30:
            return False
    
    # 5. 非新闻类URL路径关键词
    non_news_patterns = [
        "/about", "/team", "/staff", "/governance", "/committee", 
        "/contact", "/career", "/jobs", "/careers", "/join",
        "/publication", "/publications", "/member", "/members",
        "/event", "/events", "/conference", "/workshop",
        "/award", "/awards", "/grant", "/grants",
        "/policy", "/policies", "/document", "/documents",
        "/report", "/reports", "/annual", "/financial",
        "/press", "/media", "/gallery", "/video", "/videos",
        "/faq", "/faq's", "/terms", "/privacy", "/legal",
        "/sitemap", "/link", "/links", "/partner", "/partners",
        "/newsroom", "/insight", "/insights", "/knowledge",
        "/history", "/milestone", "/milestones", "/achievement",
        "/board", "/directors", "/management", "/executive",
        "/mission", "/vision", "/values", "/who-we-are",
        "/community", "/forum", "/blog", "/opinion", "/perspective"
    ]
    
    # 检查URL是否包含非新闻模式
    for pattern in non_news_patterns:
        if pattern in url_lower:
            # 但如果URL包含news或newsletter，则认为是新闻
            if "/news" in url_lower or "/newsletter" in url_lower:
                continue
            return False
    
    # 非新闻类标题关键词
    non_news_title_patterns = [
        "about", "team", "staff", "governance", "committee", "commission",
        "career", "job", "jobs", "join us", "vacancy", "vacancies",
        "publication", "document", "report", "annual report",
        "press release", "media", "gallery", "video",
        "faq", "terms", "privacy", "legal", "contact",
        "who we are", "our mission", "vision", "values",
        "board of", "directors", "management team", "executive team",
        "partner", "partners", "membership", "member",
        "conference", "workshop", "event", "symposium",
        "award", "grant", "scholarship", "funding",
    ]
    
    # 检查标题是否包含非新闻模式
    for pattern in non_news_title_patterns:
        if pattern in title_lower:
            # 但如果同时包含疏浚相关关键词，则可能是新闻
            if contains_dredging_keywords(title):
                continue
            return False
    
    return True

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
            # 增加抓取时长到 72 小时 (3天)，防止周末断更
            items = await fetch_rss(s['url'], hours=72, source_name=s.get('name'))
            all_items.extend(items)
    
    # 3. 抓取 Web (需要 Playwright)
    # 检查是否有 Web 源
    has_web = any(s.get('type') == 'web' for s in sources)
    if has_web:
        async with async_playwright() as p:
            browser = await launch_chromium(p)
                
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                locale="zh-CN",
                ignore_https_errors=True
            )
            
            web_items = []
            for s in sources:
                if s.get('type') == 'web':
                    source_items = await fetch_web_index(context, s)
                    web_items.extend(source_items)
            if web_items:
                web_items = await enrich_web_items(context, web_items)
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
