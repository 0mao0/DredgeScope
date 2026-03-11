import asyncio
import json
import base64
import os
import sys
# Add backend directory to sys.path to allow importing database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database
from openai import AsyncOpenAI
import config
from static.constants import (
    DEFAULT_CATEGORY,
    ALLOWED_CATEGORIES,
    normalize_category
)

def is_relevant_news(item, text_content, final_result):
    # 防御性检查：final_result 必须是字典
    if not isinstance(final_result, dict):
        final_result = {}
    
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
    category = normalize_category(final_result.get("category")) if final_result else None
    if category and category != "Other":
        return True
    fields = [
        item.get("title"),
        final_result.get("title_cn") if final_result else None,
        final_result.get("summary_cn") if final_result else None,
        final_result.get("full_text_cn") if final_result else None,
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
    
    # Qwen3.5 是推理模型，无法直接输出 JSON，使用自然语言提示
    vl_prompt = f"""分析这张网页截图，提取疏浚行业新闻信息。

请分析后告诉我：
1. 这是否是404/登录页/无关内容？（是/否）
2. 属于哪类：Project(项目)/Equipment(设备)/Bid(中标)/Regulation(法规)/R&D(研发)/Market(市场)
3. 中文标题（谁+在哪里+做了什么）
4. 中文摘要
5. 发布日期（YYYY-MM-DD格式）
6. 截图内容描述

请用清晰的格式回答。"""
    
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
            temperature=0.1
        )
        
        # Qwen3.5 是推理模型，内容在 reasoning 字段而不是 content 字段
        message = resp_vl.choices[0].message
        content = message.content
        
        # 如果 content 为空，尝试从 reasoning 获取
        if not content:
            if hasattr(message, 'reasoning') and message.reasoning:
                content = message.reasoning
            else:
                print(f"[VL] 警告: 无法从响应中获取内容")
                return None
        
        # 从推理内容中提取字段
        import re
        result = {
            "is_junk": False,
            "category": "Market",
            "title_cn": "",
            "summary_cn": "",
            "publish_time": "",
            "image_desc": ""
        }
        
        # 提取 is_junk
        if re.search(r'is_junk.*?(true|是|yes|无关)', content, re.I):
            result["is_junk"] = True
        elif re.search(r'(404|登录页|login|禁止访问|cookie|订阅)', content, re.I):
            result["is_junk"] = True
            
        # 提取 category
        category_patterns = [
            (r'Project|项目', 'Project'),
            (r'Equipment|设备|船舶|挖泥船|dredger|vessel', 'Equipment'),
            (r'Bid|中标|合同|contract|award', 'Bid'),
            (r'Regulation|法规|政策|license|permit|approval', 'Regulation'),
            (r'R&D|研发|技术|研究|research|technology|innovation', 'R&D'),
            (r'Market|市场|company|财报|merger|acquisition', 'Market'),
        ]
        for pattern, cat in category_patterns:
            if re.search(pattern, content, re.I):
                result["category"] = cat
                break
        
        # 提取 title_cn - 查找包含"标题"或"title_cn"的行
        title_match = re.search(r'(?:标题|title_cn|title)[：:\s]+["\']?([^"\'\n]{5,100})["\']?', content, re.I)
        if title_match:
            result["title_cn"] = title_match.group(1).strip()
        
        # 提取 summary_cn - 查找包含"摘要"或"summary_cn"的行
        summary_match = re.search(r'(?:摘要|summary_cn|summary)[：:\s]+["\']?([^"\'\n]{10,300})["\']?', content, re.I)
        if summary_match:
            result["summary_cn"] = summary_match.group(1).strip()
        
        # 提取 publish_time - 查找日期格式
        date_match = re.search(r'(\d{4})\s*[-年/]\s*(\d{1,2})\s*[-月/]\s*(\d{1,2})', content)
        if date_match:
            result["publish_time"] = f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"
        
        # 提取 image_desc - 查找包含"描述"或"image_desc"的行
        desc_match = re.search(r'(?:描述|image_desc|description)[：:\s]+["\']?([^"\'\n]{10,500})["\']?', content, re.I)
        if desc_match:
            result["image_desc"] = desc_match.group(1).strip()
        
        # 如果标题为空，尝试从内容中提取其他可能的标题格式
        if not result["title_cn"]:
            # 尝试匹配 "中文标题" 后面的内容
            alt_title = re.search(r'中文标题[：:\s]+(.+?)(?:\n|$)', content)
            if alt_title:
                result["title_cn"] = alt_title.group(1).strip()
        
        return result
        
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
2. 【语义分类】(Category) - 请根据文章描述的核心事件性质进行分类：
   请使用**排除法**进行分类决策（优先级从上到下）：
   
   - **Project (项目)**: 涉及具体的疏浚/填海/海洋工程项目的物理进展。
     - 关键词: "completed", "begins", "underway", "progress", "works", "reclamation", "restoration", "maintenance dredging".
     - 示例: "X公司完成了Y港口的疏浚", "Z运河拓宽工程开工", "某海滩修复项目正在进行".
     
   - **Equipment (设备)**: 涉及船舶或疏浚设备的建造、交付、下水、龙骨铺设、买卖或技术升级。
     - 关键词: "vessel", "dredger", "ship", "delivery", "launched", "keel laying", "order", "acquisition".
     - 示例: "新挖泥船X号交付", "Y船厂获得新船订单", "Z公司购买了二手挖泥船".
     
   - **Bid (中标/合同)**: 仅涉及合同签署、中标通知、招标发布或资金获批，尚未进入施工阶段。
     - 关键词: "contract", "tender", "award", "funding", "grant", "secures deal".
     
   - **Regulation (法规/政策)**: 涉及政府/官方机构发布的政策、法律裁决、许可证发放/吊销、环保标准。
     - 关键词: "license", "permit", "court", "law", "policy", "EPA", "corps of engineers", "approval", "ban".
     - 示例: "法院撤销X项目许可", "新疏浚环保法规发布".
     
   - **R&D (技术/研发)**: 涉及新技术、新工艺、新材料的研究、测试或理论探讨。
     - 关键词: "technology", "research", "study", "method", "solution", "innovation", "paper", "soil", "testing".
     - 示例: "针对X土壤的打桩技术研究", "新型泥泵效率提升".

   - **Market (市场/其他)**: 
     1. 公司层面的动态：财报、人事变动、战略合作、并购。
     2. 宏观市场分析、行业会议、协会活动。
     3. **兜底类别**：如果不符合上述任何一类，归入此项。

   - 不允许输出其他类别，必须从上述六类中选择最接近的一类。

3. 【有效性】(is_junk) - 排除无关或无效内容（如董事会名单、简单的链接列表、单纯的广告推广）。
4. 【翻译与提取】(title_cn, summary_cn, full_text_cn, publish_time)。
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
    # 防御性检查：如果 result 为 None 或不是字典/列表，返回默认结构
    if result is None:
        return {
            "is_junk": False,
            "category": "Market",
            "title_cn": item.get("title"),
            "summary_cn": "",
            "full_text_cn": "",
            "publish_time": str(item.get("pub_date") or ""),
            "image_desc": ""
        }
    
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
            "image_desc": ""
        }
    
    # 如果是字典，确保有必要的字段
    if isinstance(result, dict):
        return {
            "is_junk": result.get("is_junk", False),
            "category": result.get("category", "Market"),
            "title_cn": result.get("title_cn", item.get("title", "")),
            "summary_cn": result.get("summary_cn", ""),
            "full_text_cn": result.get("full_text_cn", ""),
            "publish_time": result.get("publish_time", str(item.get("pub_date") or "")),
            "image_desc": result.get("image_desc", "")
        }
    
    # 其他类型，返回默认结构
    return {
        "is_junk": False,
        "category": "Market",
        "title_cn": item.get("title"),
        "summary_cn": "",
        "full_text_cn": "",
        "publish_time": str(item.get("pub_date") or ""),
        "image_desc": ""
    }

def _resolve_screenshot_path(screenshot_path, screenshot_filename):
    if screenshot_path:
        return screenshot_path
    if screenshot_filename:
        return f"assets/{screenshot_filename}"
    return ""

def _build_final_result(item, url, text_content, screenshot_path, screenshot_filename, analysis_log, text_res, vl_res):
    final_result = {}
    
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
            "remark": "标题命中垃圾关键词",
            "screenshot_path": _resolve_screenshot_path(screenshot_path, screenshot_filename),
            "analysis_log": analysis_log,
            "source_type": item.get("source_type", "unknown"),
            "source_name": item.get("source_name", ""),
            "id": item.get("id")
        }

    # 优先级策略：Text (文本) 优先，VLM (视觉) 作为补充或兜底
    # 因为文本模型通常在分类和摘要生成上更稳定，且成本更低
    
    # 1. 首先尝试使用 Text 结果作为基础
    if text_res and not text_res.get('is_junk'):
        final_result = text_res.copy()
        analysis_log.append(f"4. **Text分析 (优先)**: 成功 ({final_result.get('category')})")
        
        # 2. 如果有 VLM 结果，进行补充
        if vl_res and not vl_res.get('is_junk'):
            # 补充图片描述
            final_result['image_desc'] = vl_res.get('image_desc', '')
            
            # 如果 Text 没提取到时间，尝试用 VLM 的时间
            if not final_result.get('publish_time') and vl_res.get('publish_time'):
                final_result['publish_time'] = vl_res.get('publish_time')
                
            # 如果 Text 没提取到中文标题（极少见），尝试用 VLM
            if not final_result.get('title_cn'):
                final_result['title_cn'] = vl_res.get('title_cn')
                
            analysis_log.append("4.1. **VL辅助**: 补充图片描述与时间")
        else:
            final_result['image_desc'] = ""
            analysis_log.append("4.1. **VL辅助**: 无有效视觉内容")

    # 3. 如果 Text 失败或为 Junk，尝试使用 VLM 兜底
    elif vl_res and not vl_res.get('is_junk'):
        final_result = vl_res.copy()
        final_result['full_text_cn'] = "" # VLM 通常无法提取全文
        analysis_log.append(f"4. **VL分析 (兜底)**: 成功 ({final_result.get('category')})")
        
    else:
        # 全部失败或判定为 Junk
        reason = "判定为垃圾信息" if (vl_res and vl_res.get('is_junk')) or (text_res and text_res.get('is_junk')) else "分析失败"
        analysis_log.append(f"4. **分析结论**: {reason}")
        
        return {
            "title": item.get('title', ''),
            "title_cn": (vl_res or text_res or {}).get("title_cn", item.get('title', '')),
            "url": url,
            "pub_date": str(item.get('pub_date', '')),
            "summary_cn": (vl_res or text_res or {}).get("summary_cn", reason),
            "full_text_cn": "",
            "content": text_content,
            "category": "Other",
            "valid": 0,
            "is_retained": 0,
            "is_junk": True,
            "remark": reason,
            "image_desc": (vl_res or {}).get('image_desc', ''),
            "screenshot_path": _resolve_screenshot_path(screenshot_path, screenshot_filename),
            "analysis_log": analysis_log,
            "source_type": item.get("source_type", "unknown"),
            "source_name": item.get("source_name", ""),
            "id": item.get("id")
        }

    # 最终字段整理
    article_category = normalize_category(final_result.get("category"))
    if not article_category:
        article_category = DEFAULT_CATEGORY

    is_valid = 1
    if not is_relevant_news(item, text_content, final_result):
        analysis_log.append("4.2. **相关性判断**: 非疏浚主题，标记为无效并归入'其他'")
        article_category = "Other"
        is_valid = 0
    
    is_retained = 1 if is_valid == 1 and article_category != "Other" else 0

    remark = "保留" if is_retained == 1 else "AI判定无关"
    if is_valid == 0:
        remark = "无效数据"

    pub_date = final_result.get("publish_time")
    # 如果 VL/Text 提取到了有效时间（格式正确），则使用它
    # 否则回退到原始 item 的 pub_date
    if pub_date and len(str(pub_date)) >= 10:
        pass # keep extracted date
    else:
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
        "remark": remark,
        "image_desc": final_result.get("image_desc", ""),
        "screenshot_path": _resolve_screenshot_path(screenshot_path, screenshot_filename),
        "analysis_log": analysis_log,
        "source_type": item.get("source_type", "unknown"),
        "source_name": item.get("source_name", ""),
        "id": item.get("id")
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
        if not config.VL_LLM_API_KEY:
            analysis_log.append("4. **VL分析**: 失败 (API Key 未配置)")
            print("[VL] Error: VL_LLM_API_KEY is not set in config.")
        else:
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
    
    if not config.TEXT_LLM_API_KEY:
        print("[Text] Error: TEXT_LLM_API_KEY is not set in config.")
        return []
        
    client = AsyncOpenAI(api_key=config.TEXT_LLM_API_KEY, base_url=config.TEXT_LLM_API_BASE)
    results = []
    sem = asyncio.Semaphore(3)

    async def runner(item):
        async with sem:
            res = await analyze_item_from_db(client, item)
            if res:
                # 分析完成后立即保存回数据库
                database.save_article(res)
                results.append(res)

    tasks = [runner(item) for item in items]
    await asyncio.gather(*tasks)
    return results
