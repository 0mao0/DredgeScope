import asyncio
import json
import base64
import os
from openai import AsyncOpenAI
import config
from static.constants import (
    DEFAULT_CATEGORY,
    ALLOWED_CATEGORIES,
    KEYWORD_CATEGORY_MAP,
    normalize_category,
    normalize_event_text,
    build_event_signature,
    extract_regulation_core,
    consolidate_regulation_events
)


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
   - Market (市场情报/新闻): 
     1. 公司动态：并购、财务报告、人事变动、战略合作。
     2. 市场分析：行业规划、战略、路线图。
     3. **兜底类别**：所有不属于上述5类的事件（如罢工、抗议、事故、地缘政治影响、无法明确分类的行业新闻），均归入 Market（新闻）。

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
   - Market (新闻兜底): 
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

def _normalize_llm_result(result, item):
    if isinstance(result, list):
        if len(result) == 1 and isinstance(result[0], dict):
            return result[0]
        return {
            "is_junk": False,
            "category": "Market",
            "title_cn": item.get("title"),
            "summary_cn": "",
            "full_text_cn": "",
            "publish_time": str(item.get("pub_date") or ""),
            "events": [e for e in result if isinstance(e, dict)]
        }
    return result

def _resolve_screenshot_path(screenshot_path, screenshot_filename):
    if screenshot_path:
        return screenshot_path
    if screenshot_filename:
        return f"assets/{screenshot_filename}"
    return ""

def _dedupe_events(events):
    if not events:
        return []
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
    return deduped

def _build_final_result(item, url, text_content, screenshot_path, screenshot_filename, analysis_log, text_res, vl_res):
    final_result = None
    if text_res and not text_res.get('is_junk'):
        final_result = text_res
        final_result['content'] = text_content
        analysis_log.append(f"4. **Text分析**: 成功 ({final_result.get('category')})")
        if vl_res and not vl_res.get('is_junk'):
            if not final_result.get('image_desc') and vl_res.get('image_desc'):
                final_result['image_desc'] = vl_res.get('image_desc', '')
            if not final_result.get('title_cn') and vl_res.get('title_cn'):
                final_result['title_cn'] = vl_res.get('title_cn')
            if not final_result.get('summary_cn') and vl_res.get('summary_cn'):
                final_result['summary_cn'] = vl_res.get('summary_cn')
            if not final_result.get('publish_time') and vl_res.get('publish_time'):
                final_result['publish_time'] = vl_res.get('publish_time')
            text_events = final_result.get('events', [])
            vl_events = vl_res.get('events', [])
            if (not text_events) and vl_events:
                final_result['events'] = vl_events
            analysis_log.append("4.1. **VL辅助**: 完成补充信息")
    elif text_res and text_res.get('is_junk'):
        analysis_log.append("4. **Text分析**: 判定为垃圾信息 (将归入'其他')")
        return {
            "title": item.get('title', ''),
            "title_cn": text_res.get("title_cn", item.get('title', '')),
            "url": url,
            "pub_date": str(item.get('pub_date', '')),
            "summary_cn": text_res.get("summary_cn", "垃圾信息/非新闻页面"),
            "full_text_cn": text_res.get("full_text_cn", ""),
            "content": text_content,
            "category": "Other",
            "valid": 0,
            "events": [],
            "image_desc": vl_res.get('image_desc', '') if vl_res else "",
            "screenshot_path": _resolve_screenshot_path(screenshot_path, screenshot_filename),
            "analysis_log": analysis_log,
            "source_type": item.get("source_type", "unknown"),
            "source_name": item.get("source_name", "")
        }
    elif vl_res:
        if vl_res.get('is_junk'):
            analysis_log.append("4. **VL分析**: 判定为垃圾信息 (将归入'其他')")
            return {
                "title": item.get('title', ''),
                "title_cn": vl_res.get("title_cn", item.get('title', '')),
                "url": url,
                "pub_date": str(item.get('pub_date', '')),
                "summary_cn": "垃圾信息/非新闻页面",
                "full_text_cn": "",
                "content": text_content,
                "category": "Other",
                "valid": 0,
                "events": [],
                "image_desc": vl_res.get('image_desc', ''),
                "screenshot_path": _resolve_screenshot_path(screenshot_path, screenshot_filename),
                "analysis_log": analysis_log,
                "source_type": item.get("source_type", "unknown"),
                "source_name": item.get("source_name", "")
            }
        else:
            final_result = vl_res
            final_result['content'] = text_content
            analysis_log.append(f"4. **VL分析**: 兜底成功 ({final_result.get('category')})")
    else:
        analysis_log.append("4. **分析失败**: 无有效文本且截图分析失败")
        return {
            "title": item.get('title', ''),
            "title_cn": item.get('title', ''),
            "url": url,
            "pub_date": str(item.get('pub_date', '')),
            "summary_cn": "分析失败",
            "full_text_cn": "",
            "content": text_content,
            "category": "Other",
            "valid": 0,
            "events": [],
            "image_desc": "",
            "screenshot_path": _resolve_screenshot_path(screenshot_path, screenshot_filename),
            "analysis_log": analysis_log,
            "source_type": item.get("source_type", "unknown"),
            "source_name": item.get("source_name", "")
        }

    article_category = normalize_category(final_result.get("category"))
    if not article_category:
        article_category = DEFAULT_CATEGORY

    events = normalize_events(final_result.get("events", []), article_category)
    events = _dedupe_events(events)

    is_valid = 1
    if not is_relevant_news(item, text_content, final_result):
        analysis_log.append("4.2. **相关性判断**: 非疏浚主题，标记为无效并归入'其他'")
        article_category = "Other"
        is_valid = 0

    pub_date = final_result.get("publish_time")
    if not pub_date or len(str(pub_date)) < 5:
        pub_date = str(item.get('pub_date', ''))

    return {
        "title": item.get('title', ''),
        "title_cn": final_result.get("title_cn", item.get('title', '')),
        "url": url,
        "pub_date": pub_date,
        "summary_cn": final_result.get("summary_cn", "暂无摘要"),
        "full_text_cn": final_result.get("full_text_cn", ""),
        "content": text_content,
        "category": article_category,
        "valid": is_valid,
        "events": events,
        "image_desc": final_result.get("image_desc", ""),
        "screenshot_path": _resolve_screenshot_path(screenshot_path, screenshot_filename),
        "analysis_log": analysis_log,
        "source_type": item.get("source_type", "unknown"),
        "source_name": item.get("source_name", "")
    }


async def analyze_item_from_db(client, item):
    url = item.get("url") or item.get("link") or ""
    analysis_log = []
    if url:
        analysis_log.append(f"1. **访问目标**: [{item.get('title', '')}]({url})")
    text_content = item.get("content") or ""
    screenshot_path = item.get("screenshot_path") or ""
    screenshot_filename = os.path.basename(screenshot_path) if screenshot_path else ""
    screenshot_bytes = None
    if screenshot_path:
        img_path = screenshot_path
        if not os.path.isabs(img_path):
            img_path = os.path.join(config.DATA_DIR, img_path)
        if os.path.exists(img_path):
            try:
                with open(img_path, "rb") as f:
                    screenshot_bytes = f.read()
            except Exception as e:
                analysis_log.append(f"截图读取失败: {e}")

    text_res = None
    vl_res = None

    if text_content and len(text_content.strip()) > 50:
        text_res = await analyze_with_text(client, item, text_content)
        if isinstance(text_res, Exception):
            print(f"[Text] Error: {text_res}")
            text_res = None
        text_res = _normalize_llm_result(text_res, item)

    if screenshot_bytes:
        vl_client = AsyncOpenAI(api_key=config.VL_LLM_API_KEY, base_url=config.VL_LLM_API_BASE)
        b64_img = base64.b64encode(screenshot_bytes).decode('utf-8')
        vl_res = await analyze_with_vl(vl_client, item, b64_img)
        if isinstance(vl_res, Exception):
            print(f"[VL] Error: {vl_res}")
            vl_res = None
        vl_res = _normalize_llm_result(vl_res, item)

    return _build_final_result(item, url, text_content, screenshot_path, screenshot_filename, analysis_log, text_res, vl_res)

async def process_items_from_db(items):
    if not items:
        return []
    client = AsyncOpenAI(api_key=config.TEXT_LLM_API_KEY, base_url=config.TEXT_LLM_API_BASE)
    results = []
    sem = asyncio.Semaphore(3)

    async def runner(item):
        async with sem:
            res = await analyze_item_from_db(client, item)
            if res:
                results.append(res)

    tasks = [runner(item) for item in items]
    await asyncio.gather(*tasks)
    return results
