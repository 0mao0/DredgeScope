import asyncio
import json
import base64
import os
from openai import AsyncOpenAI
import config
from static.constants import (
    DEFAULT_CATEGORY,
    ALLOWED_CATEGORIES,
    normalize_category
)

def is_relevant_news(item, text_content, final_result):
    source_name = str(item.get("source_name") or "")
    if source_name:
        source_lower = source_name.lower()
        source_keywords = ["疏浚", "航道", "港航", "港口", "港务", "航务", "水道", "水运", "海工", "中交", "dredg", "dredging", "waterway", "harbor", "harbour", "port"]
        if any(k in source_lower for k in source_keywords):
            return True
    url = str(item.get("link") or item.get("url") or "")
    if url:
        url_lower = url.lower()
        if any(k in url_lower for k in ["dredg", "dredging", "waterway", "harbor", "harbour", "port", "channel"]):
            return True
    category = normalize_category(final_result.get("category")) if isinstance(final_result, dict) else None
    if category and category != "Other":
        return True
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
请基于这张网页截图和以下基本信息，提取并分析疏浚行业新闻：
标题：{item['title']}
URL：{item.get('url', '')}

任务说明：
1. 【有效性】(is_junk) - 如果截图显示的是“404”、“禁止访问”、“Cookie设置”、“订阅提示”、“登录页面”或与疏浚行业完全无关的内容（如纯广告、纯人事变动列表），is_junk 设为 true。
2. 【语义分类】(Category) - 请根据截图描述的核心事件性质进行分类：
   - Bid: 合同签署、中标、招标或资金获批。
   - Equipment: 船舶/设备的建造、交付、交易或维护。
   - Project: 项目的物理施工进展（开工/完工/施工中）。
   - R&D: 科技研发。
   - Regulation: 官方发布的政策法规、标准、指南、许可审批。
   - Market: 公司动态（财务/人事/战略）、市场分析、行业规划，或其他无法归入上述类别的行业新闻。
3. 【信息提取】
   - title_cn: 中文标题。必须严格遵守 "谁(主体) + 在哪里(若有) + 做了什么(动作)" 的格式。
   - summary_cn: 中文摘要（简练精准，包含关键数据）。
   - publish_time: 【极重要】请仔细逐行扫描截图文字（特别是标题下方、文章开头、页眉页脚、来源旁），寻找发布的具体日期/时间。
     - 格式必须统一为 YYYY-MM-DD。
     - 识别 "2025-01-21", "2025.01.21", "Jan 21, 2025", "2025年1月21日", "21/01/2025" 等所有格式。
     - 若仅有月份（如"2025年1月"），默认为该月1号（2025-01-01）。
     - 若为相对时间（如"2 days ago", "昨天"），请基于当前日期（{item.get('date', '')}）推算。
     - 若找不到确切日期，但内容提及"本周"、"近日"且有明确年份上下文，可估算为当月1号。
     - 只有在完全无法找到任何时间信息时才留空。
   - image_desc: 简要描述截图中展示的主要画面内容。

返回 JSON:
{{
  "is_junk": boolean,
  "category": "...",
  "title_cn": "...",
  "summary_cn": "...",
  "publish_time": "YYYY-MM-DD",
  "image_desc": "..."
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
3. 【翻译与提取】(title_cn, summary_cn, full_text_cn, publish_time)。
   - title_cn: 中文标题。必须严格遵守 "谁(主体) + 在哪里(若有) + 做了什么(动作)" 的格式。
     - 涉及国外重点公司名称时，保持英文原名，不要翻译成中文。
     - 禁止使用 "董事会"、"可持续发展"、"我们的技术"、"市场更新" 等泛泛而谈的短语作为标题。
     - 正确示例："中交二航局在上海中标三个市政项目"、"Van Oord在荷兰完成海滩修复工程"。
   - publish_time: 提取文章的发布日期（格式 YYYY-MM-DD）。如果文中明确提到时间（如"2024年9月2日"），请提取该时间。
   - full_text_cn: 中文全文翻译，仅包含正文内容，不要包含导航、菜单、页脚、隐私政策、Cookie提示、社交链接或站内栏目标题；尽量保持原文段落结构。

返回 JSON:
{{
  "is_junk": boolean,
  "category": "...",
  "title_cn": "...",
  "summary_cn": "...",
  "full_text_cn": "...",
  "publish_time": "YYYY-MM-DD"
}}
"""
    try:
        resp = await client.chat.completions.create(
            model=config.TEXT_MODEL,
            messages=[{"role": "user", "content": filter_prompt}],
            response_format={"type": "json_object"}
        )
        content = resp.choices[0].message.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        return json.loads(content)
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

def is_obvious_junk(title):
    """判断标题是否为明显的垃圾信息"""
    if not title:
        return True
    
    title_lower = title.lower()
    
    # 垃圾关键词
    junk_patterns = [
        "skip to", "back to", "return to", "go to",
        "home", "homepage", "frontpage", "main menu",
        "previous", "next", "read more", "learn more",
        "cookie", "accept", "agree", "privacy policy",
        "terms of", "contact us", "about us",
        "sitemap", "accessibility", "subscribe",
        "board of directors", "management team", "executive team",
        "investor relations", "financial reports",
        "career", "job", "vacancy", "vacancies",
        "mailchimp", "email service", "correcting the record",
        "unsubscribe", "view in browser", "update your preferences"
    ]
    
    for pattern in junk_patterns:
        if pattern in title_lower:
            return True
            
    # 极短且无意义的标题
    if len(title.strip()) < 5:
        return True
        
    return False

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
            "publish_time": str(item.get("pub_date") or "")
        }
    return result

def _resolve_screenshot_path(screenshot_path, screenshot_filename):
    if screenshot_path:
        return screenshot_path
    if screenshot_filename:
        return f"assets/{screenshot_filename}"
    return ""

def _build_final_result(item, url, text_content, screenshot_path, screenshot_filename, analysis_log, text_res, vl_res):
    final_result = None
    
    # 强制检查：如果标题是明显垃圾，直接判定为无效
    if is_obvious_junk(item.get('title')):
        analysis_log.append("4. **前置检查**: 标题命中垃圾关键词")
        return {
            "title": item.get('title', ''),
            "title_cn": item.get('title', ''),
            "url": url,
            "pub_date": str(item.get('pub_date', '')),
            "summary_cn": "垃圾信息/非新闻页面",
            "full_text_cn": "",
            "content": text_content,
            "category": "Other",
            "valid": 0,
            "is_retained": 0,
            "image_desc": "",
            "screenshot_path": _resolve_screenshot_path(screenshot_path, screenshot_filename),
            "analysis_log": analysis_log,
            "source_type": item.get("source_type", "unknown"),
            "source_name": item.get("source_name", "")
        }

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
            "is_retained": 0,
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
                "is_retained": 0,
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
            "is_retained": 0,
            "image_desc": "",
            "screenshot_path": _resolve_screenshot_path(screenshot_path, screenshot_filename),
            "analysis_log": analysis_log,
            "source_type": item.get("source_type", "unknown"),
            "source_name": item.get("source_name", "")
        }

    article_category = normalize_category(final_result.get("category"))
    if not article_category:
        article_category = DEFAULT_CATEGORY

    is_valid = 1
    if not is_relevant_news(item, text_content, final_result):
        analysis_log.append("4.2. **相关性判断**: 非疏浚主题，标记为无效并归入'其他'")
        article_category = "Other"
        is_valid = 0
    
    # 只有 valid=1 且不是 Other 类别的，才标记为保留 (is_retained)
    # 或者 valid=1 但 category=Other (例如没分类出来但是是疏浚相关的?) 
    # 这里严格一点：必须是有效且有明确分类的，或者 LLM 认为是非 junk 的
    is_retained = 1 if is_valid == 1 and article_category != "Other" else 0

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
        "is_retained": is_retained,
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
