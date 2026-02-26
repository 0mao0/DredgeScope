import asyncio
import json
import base64
import os
from playwright.async_api import async_playwright
from openai import AsyncOpenAI
import config
from constants import (
    DEFAULT_CATEGORY,
    ALLOWED_CATEGORIES,
    KEYWORD_CATEGORY_MAP,
    normalize_category,
    normalize_event_text,
    build_event_signature,
    extract_regulation_core,
    consolidate_regulation_events
)

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

def normalize_events(events, fallback_category):
    if events is None:
        return []
    if isinstance(events, str):
        try:
            events = json.loads(events)
        except Exception:
            return []
    if not isinstance(events, list):
        return []
    normalized = []
    for evt in events:
        if isinstance(evt, str):
            try:
                evt = json.loads(evt)
            except Exception:
                continue
        if not isinstance(evt, dict):
            continue
        category = normalize_category(evt.get("category"))
        if not category:
            evt_type = evt.get("event_type") or evt.get("type") or evt.get("eventType")
            category = normalize_category(evt_type)
        if not category:
            category = fallback_category or DEFAULT_CATEGORY
        evt["category"] = category
        normalized.append(evt)
    return consolidate_regulation_events(normalized)

def is_relevant_news(item, text_content, final_result):
    fields = [
        item.get("title"),
        final_result.get("title_cn"),
        final_result.get("summary_cn"),
        final_result.get("full_text_cn"),
        text_content
    ]
    combined = " ".join([str(f) for f in fields if f])
    lower = combined.lower()
    strong_keywords = [
        "dredg", "dredger", "dredging", "dredged",
        "疏浚", "清淤", "吹填", "挖泥", "补砂", "海滩补砂", "航道疏浚", "港池疏浚"
    ]
    if any(k in lower for k in strong_keywords):
        return True
    secondary_keywords = [
        "port", "harbor", "harbour", "channel", "waterway", "navigation",
        "sediment", "reclamation", "coastal", "estuary", "river",
        "terminal", "berth", "quay", "dock", "maritime", "seabed", "offshore",
        "航道", "港口", "港航", "码头", "航运", "河道", "运河",
        "海岸", "海工", "海洋工程", "船坞", "泊位", "航道维护",
        "疏港", "港池", "填海", "围填海", "河口"
    ]
    hit_count = sum(1 for k in secondary_keywords if k in lower)
    return hit_count >= 2

async def analyze_with_vl(client, item, b64_img):
    """
    使用视觉模型进行首要分析
    """
    print(f"[VL] 正在进行视觉分析: {item['title']}")
    
    vl_prompt = f"""
你是一名疏浚行业情报分析专家。请根据网页截图内容，进行深度的语义分析。
标题: {item['title']}

任务说明：
1. 若内容与疏浚、港航、航道维护、疏浚设备或海洋工程无关，is_junk 必须为 true。
1. 【深度语义分类】请基于新闻的核心语义和主要事件类型，将其归入以下六类别之一。
   请使用**排除法**进行分类决策：
   - Bid (中标/合同): 仅包含合同签署、项目中标、招标公告发布、资金/预算获批。关键词：Secures, Wins, Contract, Tender, Awarded, Funding, Budget。
   - Equipment (装备动态): 仅包含船舶/设备的建造、交付、下水、购买、维修或技术升级。关键词：Vessel, Dredger, Delivery, Launch, Keel Laying。
   - Project (项目进展): 仅包含工程项目的**物理进展**（如开工、施工中、完工、验收、疏浚作业详情）。关键词：Begins, Completed, Dredging works, Progress。
   - R&D (科技研发): 仅包含技术研发、创新项目、研究成果发布。
   - Regulation (政策法规): 仅包含**官方发布**的政府政策、环保法规、行业标准、限制令、关税、指南/规范/许可审批。
     * 注意：针对政策的**抗议**、**罢工**、**争议**或**呼吁**，不属于 Regulation，应归入 Market。
   - Market (市场情报): 
     1. 公司动态：并购、财务报告、人事变动、战略合作。
     2. 市场分析：行业规划、战略、路线图。
     3. **兜底类别**：所有不属于上述5类的事件（如罢工、抗议、事故、地缘政治影响、无法明确分类的行业新闻），均归入 Market。

2. 【信息提取】
   - title_cn: 中文标题。必须严格遵守 "谁(主体) + 在哪里(若有) + 做了什么(动作)" 的格式。
     - 涉及国外重点公司名称时，保持英文原名，不要翻译成中文。
     - 禁止使用 "董事会"、"可持续发展"、"我们的技术"、"市场更新" 等泛泛而谈的短语作为标题。
     - 正确示例："中交二航局在上海中标三个市政项目"、"Van Oord在荷兰完成海滩修复工程"。
     - 错误示例："最新中标"、"项目动态"。
   - summary_cn: 中文摘要（简练精准，包含关键数据）。
   - publish_time: 文章发布的具体日期/时间 (YYYY-MM-DD 或 YYYY-MM-DD HH:MM)，若文中未明确提及则留空。
   - image_desc: 图片描述。
   - events: 提取关键事件列表。
     - 针对 "连中多标" (e.g. 中交二航局在上海连中3标) 的情况，必须将每个中标项目拆分为独立的 event 对象。
     - 针对政策法规/标准/指南/解读类内容，通常只生成 1 个事件；仅在明确出现多项不同法规/政策并列时才拆分为多条。
     - 每个 event 包含: 
       - project_name (项目名称)
       - location (详细地点/城市)
       - amount (金额)
       - currency (货币单位)
       - contractor (承建商)
       - client (业主)
       - time (中标/开工时间)
       - content (具体的建设内容描述)
   - events[].category: 每个事件的分类，必须是上述类别之一。

返回 JSON:
{{
  "is_junk": boolean,
  "category": "...",
  "title_cn": "...",
  "summary_cn": "...",
  "publish_time": "YYYY-MM-DD",
  "image_desc": "...",
  "events": [
    {{
      "project_name": "...",
      "location": "...",
      "amount": "...",
      "currency": "...",
      "contractor": "...",
      "client": "...",
      "time": "...",
      "content": "...",
      "category": "..."
    }}
  ]
}}
"""
    try:
        resp_vl = await client.chat.completions.create(
            model=config.VL_MODEL,
            messages=[
                {
                    "role": "user", 
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}},
                        {"type": "text", "text": vl_prompt}
                    ]
                }
            ],
            max_tokens=1000,
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        content = resp_vl.choices[0].message.content
        # 清洗 JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        return json.loads(content)
    except Exception as e:
        print(f"[VL] 分析失败: {e}")
        return None

async def analyze_with_text(client, item, text_content, vl_context=None):
    """
    使用文本模型进行兜底或补充分析
    """
    print(f"[Text] 正在进行文本分析 (Fallback/Refine): {item['title']}")
    text_block = text_content[:8000]
    
    filter_prompt = f"""
请基于深度语义分析这篇疏浚行业新闻。
标题: {item['title']}
正文片段: {text_block}
视觉分析参考: {json.dumps(vl_context, ensure_ascii=False) if vl_context else "无"}

任务说明：
1. 若内容与疏浚、港航、航道维护、疏浚设备或海洋工程无关，is_junk 必须为 true。
1. 【语义分类】(Category) - 请根据文章描述的核心事件性质进行分类：
   请使用**排除法**进行分类决策：
   - Bid: 仅包含合同签署、中标、招标或资金获批。包括 "secures contract", "wins tender", "funding approved"。
   - Equipment: 仅包含船舶/设备的建造、交付、交易或维护。
   - Project: 仅包含项目的**物理施工进展**（开工/完工/施工中）。包括 "begins", "completed", "underway"。
   - R&D: 仅包含科技研发。
   - Regulation: 仅包含**官方发布**的政策法规、标准、指南、许可审批或政策解读。
     * 针对政策的**抗议**、**罢工**、**争议**或**呼吁**，不属于 Regulation，应归入 Market。
   - Market: 
     1. 核心是关于公司财务、人事、并购或市场分析，以及行业规划/战略。
     2. **兜底类别**：如果事件涉及罢工、抗议、地缘政治影响、意外事故等非标准事件，或者无法归入其他5类，请归入此项。
   - 不允许输出其他类别，必须从上述六类中选择最接近的一类。

2. 【有效性】(is_junk) - 排除无关或无效内容（如董事会名单、简单的链接列表）。
3. 【翻译与提取】(title_cn, summary_cn, full_text_cn, publish_time, events)。
   - title_cn: 中文标题。必须严格遵守 "谁(主体) + 在哪里(若有) + 做了什么(动作)" 的格式。
     - 涉及国外重点公司名称时，保持英文原名，不要翻译成中文。
     - 禁止使用 "董事会"、"可持续发展"、"我们的技术"、"市场更新" 等泛泛而谈的短语作为标题。
     - 正确示例："中交二航局在上海中标三个市政项目"、"Van Oord在荷兰完成海滩修复工程"。
   - publish_time: 提取文章的发布日期（格式 YYYY-MM-DD）。如果文中明确提到时间（如"2024年9月2日"），请提取该时间。
   - 重点提取 events 列表。
   - full_text_cn: 中文全文翻译，仅包含正文内容，不要包含导航、菜单、页脚、隐私政策、Cookie提示、社交链接或站内栏目标题；尽量保持原文段落结构。
   - 针对 "连中多标" (e.g. 中交二航局在上海连中3标) 的情况，必须将每个中标项目拆分为独立的 event 对象。
   - 针对政策法规/标准/指南/解读类内容，通常只生成 1 个事件；仅在明确出现多项不同法规/政策并列时才拆分为多条。
   - 每个 event 字段:
     - project_name (项目名称)
     - location (详细地点/城市)
     - amount (金额)
     - currency (货币单位)
     - contractor (承建商)
     - client (业主)
     - time (中标/开工时间)
     - content (具体的建设内容描述)
     - category (必须是上述分类之一)

返回 JSON:
{{
  "is_junk": boolean,
  "category": "...",
  "title_cn": "...",
  "summary_cn": "...",
  "full_text_cn": "...",
  "publish_time": "YYYY-MM-DD",
  "events": [
    {{
      "project_name": "...",
      "location": "...",
      "amount": "...",
      "currency": "...",
      "contractor": "...",
      "client": "...",
      "time": "...",
      "content": "...",
      "category": "..."
    }}
  ]
}}
"""
    try:
        resp = await client.chat.completions.create(
            model=config.TEXT_MODEL,
            messages=[{"role": "user", "content": filter_prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        print(f"[Text] 分析失败: {e}")
        return None

def is_security_interstitial(page_title, page_url):
    """判断是否为证书/安全拦截页"""
    title = (page_title or "").lower()
    url = (page_url or "").lower()
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

def clean_article_text(text_content):
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

async def analyze_item(context, client, item):
    """
    核心分析流程 (Text-First 模式):
   # 1. 访问网页 -> 截图 & 提取文本
    # Pre-check blacklist
    if any(x in item['title'].lower() for x in ["about us", "contact us", "privacy policy"]):
        print(f"[分析] 命中黑名单，跳过: {item['title']}")
        return None

    2. Text LLM (主): 负责分类、摘要、事件提取。
    3. Vision LLM (辅): 负责图片描述、无文本时的兜底。
    4. 决策逻辑: 
       - Text 判定 Junk -> 丢弃
       - Text 成功 -> 采用 Text 结果 + VL 的 image_desc
       - Text 无内容/失败 -> 采用 VL 结果
       - 默认分类 -> Market
    """
    url = item['link']
    print(f"[分析] 处理中: {url}")
    
    analysis_log = []
    analysis_log.append(f"1. **访问目标**: [{item['title']}]({url})")
    
    page = await context.new_page()
    screenshot_bytes = None
    text_content = ""
    screenshot_filename = ""
    
    try:
        # 1. 访问页面
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            analysis_log.append(f"2. **页面加载**: 成功")
        except Exception as e:
            print(f"[分析] 加载超时 {url}，尝试继续处理...")
            analysis_log.append(f"2. **页面加载**: 超时 (尝试继续处理)")

        page_title = ""
        page_url = ""
        try:
            page_title = await page.title()
            page_url = page.url
        except:
            page_title = ""
            page_url = ""

        # 模拟滚动
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)
            await page.evaluate("window.scrollTo(0, 0)")
        except: pass
        
        # --- 处理 Cookie 弹窗与遮挡 (增强版 v2) ---
        try:
            # 1. 尝试点击常见的同意按钮 (非阻塞)
            try:
                # 高优先级关键词 (全选)
                high_priority_keywords = ["Accept All", "Allow All", "Agree All", "全部接受", "全部同意", "Accept cookies"]
                for kw in high_priority_keywords:
                     btn = page.locator(f"button:visible:has-text('{kw}'), a:visible:has-text('{kw}')").first
                     if await btn.count() > 0:
                        print(f"[Cookie] 尝试点击高优先级: {kw}")
                        await btn.click(timeout=1000)
                        await asyncio.sleep(1.0)
                        break

                # 普通关键词
                keywords = [
                    "Accept", "Agree", "Allow", "Got it", "I understand", 
                    "同意", "接受", "我知道了", "允许", "好", "确定", 
                    "OK", "Yes", "Close", "关闭"
                ]
                for kw in keywords:
                    # 查找可见的按钮或链接，增加 div[role='button']
                    btn = page.locator(f"button:visible:has-text('{kw}'), a:visible:has-text('{kw}'), div[role='button']:visible:has-text('{kw}')").first
                    if await btn.count() > 0:
                        print(f"[Cookie] 尝试点击: {kw}")
                        await btn.click(timeout=1000)
                        await asyncio.sleep(1.0)
                        break
            except: 
                pass

            # 2. 暴力移除干扰元素
            await page.evaluate("""() => {
                // 常见 Cookie/广告 ID 和 Class 关键词
                const keywords = ['cookie', 'consent', 'gdpr', 'banner', 'popup', 'newsletter', 'subscribe', 'ad-', 'notice', 'policy', 'privacy'];
                
                // 常见 CMP (Consent Management Platform) 的 ID
                const cmpIds = ['onetrust-banner-sdk', 'CybotCookiebotDialog', 'usercentrics-root', 'cmpbox', 'cmp-container', 'cookie-law-info-bar'];
                
                // 1. 直接移除已知的 CMP
                cmpIds.forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.remove();
                });

                // 2. 遍历所有元素，移除固定定位且符合特征的元素
                document.querySelectorAll('*').forEach(el => {
                    const style = window.getComputedStyle(el);
                    
                    // 检查是否固定定位或粘性定位
                    if (style.position === 'fixed' || style.position === 'sticky') {
                        const id = el.id.toLowerCase();
                        const className = el.className.toString().toLowerCase();
                        const zIndex = parseInt(style.zIndex) || 0;
                        const tagName = el.tagName.toLowerCase();
                        
                        // 2.1 关键词匹配
                        if (keywords.some(k => id.includes(k) || className.includes(k))) {
                            el.remove();
                            return;
                        }
                        
                        // 2.2 位于底部或顶部的横幅 (高度较小，宽度较大)
                        const rect = el.getBoundingClientRect();
                        const isBanner = (rect.height < 250 && rect.width > window.innerWidth * 0.8);
                        const isAtEdge = (rect.top < 100 || rect.bottom > window.innerHeight - 100);
                        
                        if (isBanner && isAtEdge) {
                             // 避免移除顶部导航栏 (通常包含 nav, header 关键词)
                             if (!(id.includes('nav') || id.includes('header') || className.includes('nav') || className.includes('header') || tagName === 'nav' || tagName === 'header')) {
                                el.remove();
                                return;
                             }
                        }
                        
                        // 2.3 遮挡屏幕大部分的元素 (可能是全屏弹窗，且z-index较高)
                        if (rect.width > window.innerWidth * 0.9 && rect.height > window.innerHeight * 0.9 && zIndex > 50) {
                             el.remove();
                             return;
                        }
                    }
                });
                
                // 3. 移除常见的遮罩层
                document.querySelectorAll('.modal-backdrop, .overlay, .fade.in, [class*="overlay"], [class*="backdrop"]').forEach(el => el.remove());
                
                // 4. 强制恢复滚动
                document.body.style.overflow = 'auto';
                document.documentElement.style.overflow = 'auto';
            }""")
            await asyncio.sleep(1.0) # 等待移除生效
        except Exception as e:
            print(f"[Cookie清理] 异常: {e}")

        if is_security_interstitial(page_title, page_url):
            analysis_log.append("2. **页面加载**: 命中安全拦截页，跳过截图")
        else:
            # 2. 提取文本 (核心)
            try:
                text_content = await page.evaluate("""() => {
                    const article = document.querySelector('article') || document.querySelector('.post-content') || document.querySelector('.entry-content') || document.body;
                    return article.innerText.slice(0, 15000);
                }""")
            except:
                text_content = ""
            if text_content:
                text_content = clean_article_text(text_content)

            # 3. 截图 (辅助 & 兜底)
            try:
                locator = page.locator('article').first
                box = None
                if await locator.count() > 0:
                    box = await locator.bounding_box()
                if box:
                    screenshot_bytes = await page.screenshot(type='jpeg', quality=70, clip=box)
                    log_ss = "内容区域截图"
                else:
                    await page.set_viewport_size({"width": 1280, "height": 1500})
                    screenshot_bytes = await page.screenshot(type='jpeg', quality=60, full_page=True)
                    log_ss = "全页截图"
                    
                safe_title = "".join([c for c in item['title'] if c.isalnum() or c in (' ','-','_')]).strip()[:50]
                screenshot_filename = f"{safe_title}.jpg"
                screenshot_path = os.path.join(config.ASSETS_DIR, screenshot_filename)
                with open(screenshot_path, 'wb') as f:
                    f.write(screenshot_bytes)
                analysis_log.append(f"3. **截图**: {log_ss}成功")
                
            except Exception as e:
                print(f"截图失败: {e}")
                analysis_log.append(f"3. **截图**: 失败 ({e})")

    except Exception as e:
        print(f"页面处理异常: {e}")
    finally:
        await page.close()

    # 4. 智能分析 (Text First, VL Second)
    final_result = None
    
    # 初始化任务
    text_task = None
    vl_task = None
    
    # 启动 Text Analysis
    if text_content and len(text_content.strip()) > 50:
        text_task = analyze_with_text(client, item, text_content)
        
    # 启动 VL Analysis
    if screenshot_bytes:
        vl_client = AsyncOpenAI(api_key=config.VL_LLM_API_KEY, base_url=config.VL_LLM_API_BASE)
        b64_img = base64.b64encode(screenshot_bytes).decode('utf-8')
        vl_task = analyze_with_vl(vl_client, item, b64_img)
        
    # 并发执行
    results = await asyncio.gather(
        text_task if text_task else asyncio.sleep(0), 
        vl_task if vl_task else asyncio.sleep(0),
        return_exceptions=True
    )
    
    text_res = results[0] if text_task else None
    vl_res = results[1] if vl_task else None
    
    # 处理异常
    if isinstance(text_res, Exception):
        print(f"[Text] Error: {text_res}")
        text_res = None
    if isinstance(vl_res, Exception):
        print(f"[VL] Error: {vl_res}")
        vl_res = None
        
    # 决策逻辑
    
    # Case 1: Text 认为有效
    if text_res and not text_res.get('is_junk'):
        final_result = text_res
        analysis_log.append(f"4. **Text分析**: 成功 ({final_result.get('category')})")
        
        # 尝试合并 VL 的图片描述
        if vl_res and not vl_res.get('is_junk'):
            final_result['image_desc'] = vl_res.get('image_desc', '')
            
            # Supplement events logic: Only use VL events if Text events are empty.
            # This prevents duplicates caused by language differences (EN vs CN) or slightly different extractions.
            text_events = final_result.get('events', [])
            vl_events = vl_res.get('events', [])
            
            if not text_events and vl_events:
                final_result['events'] = vl_events
                analysis_log.append(f"4.1. **VL辅助**: 文本提取为空，采用了VL提取的 {len(vl_events)} 个事件")
            elif text_events and vl_events:
                # Log that we ignored VL events to avoid duplicates
                analysis_log.append(f"4.1. **VL辅助**: 文本已提取 {len(text_events)} 个事件，忽略VL事件以防重复")
            else:
                analysis_log.append("4.1. **VL辅助**: 图片描述已合并 (无新增事件)")
            
    # Case 2: Text 认为是 Junk -> 丢弃
    elif text_res and text_res.get('is_junk'):
        analysis_log.append("4. **Text分析**: 判定为垃圾信息 (已丢弃)")
        return None
        
    # Case 3: Text 没跑 (无文本) 或 失败 -> 依赖 VL
    elif vl_res:
        if vl_res.get('is_junk'):
            analysis_log.append("4. **VL分析**: 判定为垃圾信息")
            return None
        else:
            final_result = vl_res
            analysis_log.append(f"4. **VL分析**: 兜底成功 ({final_result.get('category')})")
            
    # Case 4: 都失败
    else:
        analysis_log.append("4. **分析失败**: 无有效文本且截图分析失败")
        return None

    # 5. 后处理 (Normalization & Formatting)
    if final_result.get("is_junk"):
        return None

    # 分类归一化
    article_category = normalize_category(final_result.get("category"))
    if not article_category:
        article_category = DEFAULT_CATEGORY # Market
        
    events = normalize_events(final_result.get("events", []), article_category)
    if events:
        seen_signatures = set()
        deduped = []
        for evt in events:
            sig = build_event_signature(evt)
            if not sig:
                sig = f"empty|{evt.get('category', '')}"
            if sig in seen_signatures:
                continue
            seen_signatures.add(sig)
            deduped.append(evt)
        events = deduped

    if not is_relevant_news(item, text_content, final_result):
        analysis_log.append("4.2. **相关性判断**: 非疏浚主题，已丢弃")
        return None

    # 优先使用分析出的发布时间 (Text First)
    pub_date = final_result.get("publish_time")
    if not pub_date or len(str(pub_date)) < 5:
         pub_date = str(item['pub_date']) # Fallback to crawl time

    return {
        "title": item['title'],
        "title_cn": final_result.get("title_cn", item['title']),
        "url": url,
        "pub_date": pub_date,
        "summary_cn": final_result.get("summary_cn", "暂无摘要"),
        "full_text_cn": final_result.get("full_text_cn", ""),
        "category": article_category,
        "events": events,
        "image_desc": final_result.get("image_desc", ""),
        "screenshot_path": f"assets/{screenshot_filename}" if screenshot_filename else "",
        "analysis_log": analysis_log,
        "source_type": item.get("source_type", "unknown"),
        "source_name": item.get("source_name", "")
    }


async def process_items(items):
    """并发处理所有条目"""
    if not items:
        return []
        
    client = AsyncOpenAI(api_key=config.TEXT_LLM_API_KEY, base_url=config.TEXT_LLM_API_BASE)
    
    async with async_playwright() as p:
        # 启动浏览器用于分析阶段 (截图)
        browser = await launch_chromium(p)
            
        context = await browser.new_context(viewport={"width": 1280, "height": 800}, ignore_https_errors=True)
        
        results = []
        sem = asyncio.Semaphore(3) # 并发控制
        
        async def runner(item):
            async with sem:
                res = await analyze_item(context, client, item)
                if res:
                    results.append(res)
        
        # 限制数量用于测试，或者全部
        # 生产环境应该去掉切片
        tasks = [runner(item) for item in items] 
        await asyncio.gather(*tasks)
        
        await browser.close()
        return results
