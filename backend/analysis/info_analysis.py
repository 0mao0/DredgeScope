import asyncio
import json
import base64
import os
from playwright.async_api import async_playwright
from openai import AsyncOpenAI
import config

DEFAULT_CATEGORY = "Market"

ALLOWED_CATEGORIES = {
    "Bid",
    "Equipment",
    "Market",
    "Project",
    "Regulation",
    "R&D"
}

KEYWORD_CATEGORY_MAP = [
    (["contract", "tender", "bid", "award", "funding", "budget", "procurement"], "Bid"),
    (["delivery", "launch", "vessel", "ship", "dredger", "keel", "shipyard", "equipment", "fleet"], "Equipment"),
    (["acquire", "acquisition", "merger", "financial", "profit", "revenue", "earnings", "market", "investor", "share", "plan", "planning", "strategy", "strategic", "roadmap", "program", "programme", "initiative", "five-year", "five year", "5-year", "master plan"], "Market"),
    (["project", "construction", "progress", "dredging", "completion", "completed", "underway", "restoration", "maintenance", "works"], "Project"),
    (["regulation", "policy", "law", "act", "legislation", "tariff", "compliance", "standard", "guideline", "guidelines", "requirement", "requirements", "permit", "approval", "overview", "introduction", "intro", "basics", "guide", "101"], "Regulation"),
    (["research", "technology", "innovation", "laboratory", "prototype", "r&d", "rd"], "R&D")
]

def normalize_category(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    lower = text.lower()
    exact_map = {
        "bid": "Bid",
        "equipment": "Equipment",
        "market": "Market",
        "project": "Project",
        "regulation": "Regulation",
        "r&d": "R&D",
        "rd": "R&D",
        "r and d": "R&D",
        "research and development": "R&D"
    }
    if lower in exact_map:
        return exact_map[lower]
    compact = "".join(ch for ch in lower if ch.isalnum())
    if compact in ["rd", "researchdevelopment"]:
        return "R&D"
    for keywords, category in KEYWORD_CATEGORY_MAP:
        if any(k in lower for k in keywords):
            return category
    return None

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

def extract_regulation_core(evt):
    """提取法规事件的核心内容用于去重"""
    if not isinstance(evt, dict):
        return ""
    parts = [
        evt.get("project_name"),
        evt.get("content"),
        evt.get("location"),
        evt.get("time")
    ]
    merged = " ".join([str(p) for p in parts if p])
    return normalize_event_text(merged)

def consolidate_regulation_events(events):
    """合并同一文章中过量拆分的法规事件"""
    if not events:
        return []
    reg_indices = [(idx, evt) for idx, evt in enumerate(events) if evt.get("category") == "Regulation"]
    if len(reg_indices) <= 1:
        return events
    cores = [(idx, evt, extract_regulation_core(evt)) for idx, evt in reg_indices]
    meaningful = [(idx, evt, core) for idx, evt, core in cores if core]
    if len(meaningful) <= 1:
        keep_indices = {reg_indices[0][0]}
    else:
        seen = set()
        keep_indices = set()
        for idx, evt, core in cores:
            key = core or "regulation"
            if key in seen:
                continue
            seen.add(key)
            keep_indices.add(idx)
    return [evt for idx, evt in enumerate(events) if evt.get("category") != "Regulation" or idx in keep_indices]

def normalize_event_text(value):
    """归一化事件字段文本"""
    if not value:
        return ""
    text = str(value).strip().lower()
    return "".join(ch for ch in text if ch.isalnum() or ch.isspace())

def build_event_signature(evt):
    """生成事件指纹用于去重"""
    if not isinstance(evt, dict):
        return ""
    parts = [
        evt.get("category"),
        evt.get("project_name"),
        evt.get("location"),
        evt.get("contractor"),
        evt.get("client"),
        evt.get("time"),
        evt.get("content"),
        evt.get("amount"),
        evt.get("currency")
    ]
    normalized = [normalize_event_text(p) for p in parts if p]
    return "|".join([p for p in normalized if p])

async def analyze_with_vl(client, item, b64_img):
    """
    使用视觉模型进行首要分析
    """
    print(f"[VL] 正在进行视觉分析: {item['title']}")
    
    vl_prompt = f"""
你是一名疏浚行业情报分析专家。请根据网页截图内容，进行深度的语义分析。
标题: {item['title']}

任务说明：
1. 【深度语义分类】请基于新闻的核心语义和主要事件类型，将其归入以下六类别之一。
   - Bid (中标/合同): 核心事件是关于合同签署、项目中标、招标公告发布、资金/预算获批。关键词：Secures, Wins, Contract, Tender, Awarded, Funding, Budget。
   - Equipment (装备动态): 核心事件是关于船舶/设备的建造、交付、下水、购买、维修或技术升级。关键词：Vessel, Dredger, Delivery, Launch, Keel Laying。
   - Market (市场情报): 核心事件是关于公司并购、财务报告、高层人事变动、战略合作、市场趋势分析、行业规划/战略/路线图/中长期计划。关键词：Acquire, Merger, Financial, Profit, Market, Plan, Strategy, Roadmap。
   - Project (项目进展): 核心事件是关于工程项目的物理进展（如开工、施工中、完工、验收、疏浚作业详情）。关键词：Begins, Completed, Dredging works, Progress。
   - Regulation (政策法规): 核心事件是关于政府政策、环保法规、行业标准、限制令、关税、指南/规范/许可审批，以及政策解读/基础知识科普类内容。
   - R&D (科技研发): 核心事件是关于技术研发、创新项目、研究成果发布等。
   - 不允许输出其他类别，必须从上述六类中选择最接近的一类。

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
1. 【语义分类】(Category) - 请根据文章描述的核心事件性质进行分类：
   - Bid: 核心是关于合同签署、中标、招标或资金获批。包括 "secures contract", "wins tender", "funding approved"。
   - Equipment: 核心是关于船舶/设备的建造、交付、交易或维护。
   - Market: 核心是关于公司财务、人事、并购或市场分析，以及行业规划/战略/路线图/中长期计划。包括 "acquisition", "merger", "plan", "strategy"。
   - Project: 核心是关于项目的物理施工进展（开工/完工/施工中）。包括 "begins", "completed", "underway"。
   - Regulation: 核心是关于政策法规、标准、指南、许可审批或政策解读/基础知识科普内容。
   - R&D: 核心是关于科技研发。
   - 不允许输出其他类别，必须从上述六类中选择最接近的一类。

2. 【有效性】(is_junk) - 排除无关或无效内容（如董事会名单、简单的链接列表）。
3. 【翻译与提取】(title_cn, summary_cn, full_text_cn, publish_time, events)。
   - title_cn: 中文标题。必须严格遵守 "谁(主体) + 在哪里(若有) + 做了什么(动作)" 的格式。
     - 涉及国外重点公司名称时，保持英文原名，不要翻译成中文。
     - 禁止使用 "董事会"、"可持续发展"、"我们的技术"、"市场更新" 等泛泛而谈的短语作为标题。
     - 正确示例："中交二航局在上海中标三个市政项目"、"Van Oord在荷兰完成海滩修复工程"。
   - publish_time: 提取文章的发布日期（格式 YYYY-MM-DD）。如果文中明确提到时间（如"2024年9月2日"），请提取该时间。
   - 重点提取 events 列表。
   - full_text_cn: 中文全文翻译，尽量保持原文段落结构。
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

        # 模拟滚动
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)
            await page.evaluate("window.scrollTo(0, 0)")
        except: pass
        
        # 2. 提取文本 (核心)
        try:
            # 移除干扰元素
            await page.evaluate("""() => {
                const trash = document.querySelectorAll('nav, footer, .ad, .advertisement, .sidebar, .cookie-consent, #cookie-banner');
                trash.forEach(el => el.remove());
            }""")
            
            # 优先提取 article
            text_content = await page.evaluate("""() => {
                const article = document.querySelector('article') || document.querySelector('.post-content') || document.querySelector('.entry-content') || document.body;
                return article.innerText.slice(0, 15000);
            }""")
        except:
            text_content = ""

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
                
            # 保存截图
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
            
            # Supplement events (User request: "Supplement text-llm")
            text_events = final_result.get('events', [])
            vl_events = vl_res.get('events', [])
            
            if vl_events:
                existing_signatures = {build_event_signature(e) for e in text_events if build_event_signature(e)}
                existing_cores = set()
                for e in text_events:
                    core = normalize_event_text(e.get("project_name") or e.get("content") or "")
                    if core:
                        existing_cores.add(core)
                count_added = 0
                for ve in vl_events:
                    sig = build_event_signature(ve)
                    core = normalize_event_text(ve.get("project_name") or ve.get("content") or "")
                    if (sig and sig in existing_signatures) or (core and core in existing_cores):
                        continue
                    text_events.append(ve)
                    if sig:
                        existing_signatures.add(sig)
                    if core:
                        existing_cores.add(core)
                    count_added += 1
                
                final_result['events'] = text_events
                if count_added > 0:
                    analysis_log.append(f"4.1. **VL辅助**: 补充了 {count_added} 个事件")
                else:
                    analysis_log.append("4.1. **VL辅助**: 图片描述已合并 (无新增事件)")
            else:
                analysis_log.append("4.1. **VL辅助**: 图片描述已合并")
            
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
        browser = None
        for channel in ["chrome", "msedge", "chromium"]:
            try:
                browser = await p.chromium.launch(channel=channel, headless=True)
                break
            except: pass
        if not browser: browser = await p.chromium.launch(headless=True)
            
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        
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
