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

def _clean_vl_description(text):
    """清理VL描述中的结构化标记，保留纯描述内容"""
    import re
    
    # 移除 Markdown 粗体标记 **xxx**
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    
    # 移除 bullet point 标记 (*   )
    text = re.sub(r'^\s*\*\s+', '', text, flags=re.MULTILINE)
    
    # 移除 "页面类型："、"标题："、"正文内容：" 等结构化前缀
    text = re.sub(r'^(?:页面类型|标题|正文内容|主要内容|截图内容)[：:]\s*', '', text, flags=re.MULTILINE)
    
    # 合并多行，用空格连接
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    text = ' '.join(lines)
    
    # 清理多余空格
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def normalize_significance(value):
    """将 LLM 返回的重要度分数归一化为 0-10 整数，缺失或非法返回 None"""
    if value is None:
        return None
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(10, score))

def parse_vl_significance(content):
    """从 VL 自然语言输出中解析第 7 行重要度分数（0-10 整数）"""
    if not content:
        return None
    import re
    match = re.search(r'^7\.\s*(?:[^\n]*?)(\d{1,2})\s*$', content, re.MULTILINE)
    if not match:
        return None
    return normalize_significance(match.group(1))

async def analyze_with_vl(client, item, b64_img):
    """
    使用视觉模型进行首要分析
    """
    print(f"[VL] 正在进行视觉分析: {item['title']}")
    
    # Qwen3.5 是推理模型，无法直接输出 JSON，使用自然语言提示
    vl_prompt = """分析这张网页截图，提取疏浚行业新闻信息。

【重要】请只输出最终答案，不要输出任何分析过程、思考步骤或结构化标记（如"**标题**"、"正文内容"等）。

请输出以下7行：
1. 是否是404/登录页/无关内容？只回答一个字：是 或 否
2. 属于哪类：只回答类别名：Project/Equipment/Bid/Regulation/R&D/Market
3. 中文标题：谁+在哪里+做了什么（不超过30字）
4. 中文摘要：概括文章核心内容（不超过100字）
5. 发布日期：YYYY-MM-DD格式（从页面中寻找，找不到则留空）
6. 截图内容描述：用一段话描述截图中显示的网页主要内容（不超过150字，纯描述，不要分析）
7. 重要度打分：只输出 0-10 的整数，数字越大越重要

【格式示例】
1. 否
2. Project
3. 美国陆军工程兵团在缅因州推进航道疏浚项目
4. 美国陆军工程兵团新英格兰区表示，位于缅因州的纳拉瓜古斯河联邦航道项目进展顺利，预计将于2026年4月完工，将疏浚约15.4万立方码沙子。
5. 2026-03-12
6. 网页截图显示DredgingToday.com的新闻详情页，标题为Narraguagus River Federal Navigation Project moves ahead，正文介绍美国陆军工程兵团的疏浚项目进展，配有一张挖泥船作业图片。
7. 8"""
    
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
            extra_body={
                "chat_template_kwargs": {
                    "enable_thinking": False
                }
            }
        )
        
        # Qwen3.5 关闭思考模式后，答案直接在 content 字段
        message = resp_vl.choices[0].message
        content = message.content
        
        # 如果 content 为空，尝试从 reasoning 获取（兼容模式）
        if not content:
            if hasattr(message, 'reasoning') and message.reasoning:
                content = message.reasoning
            else:
                print("[VL] 警告: 无法从响应中获取内容")
                return None
        
        import re
        
        result = {
            "is_junk": False,
            "category": "Market",
            "title_cn": "",
            "summary_cn": "",
            "publish_time": "",
            "image_desc": "",
            "significant": None
        }
        
        # 提取 is_junk - 查找"1."开头的行，提取"是"或"否"
        is_junk_match = re.search(r'^1\.\s*(?:[^\n]*?)(是|否)', content, re.I | re.MULTILINE)
        if is_junk_match:
            result["is_junk"] = is_junk_match.group(1).strip() == '是'
        else:
            # 备选：查找明确标记为无关的内容
            if re.search(r'(?:404页面|登录页面|完全无关)(?!.*正常)', content, re.I):
                result["is_junk"] = True
            
        # 提取 category - 查找"2."开头的行
        category_match = re.search(r'^2\.\s*(?:[^\n]*?)(Project|Equipment|Bid|Regulation|R&D|Market)', content, re.I | re.MULTILINE)
        if category_match:
            result["category"] = category_match.group(1).strip()
        else:
            # 备选：从内容中匹配类别关键词
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
        
        # 提取 title_cn - 查找"3."开头的行，提取后面的内容
        title_match = re.search(r'^3\.\s*(?:[^\n]*?)[：:\s]*\n*\s*([^\n]+)', content, re.I | re.MULTILINE)
        if title_match:
            result["title_cn"] = title_match.group(1).strip()
        
        # 提取 summary_cn - 查找"4."开头的行
        summary_match = re.search(r'^4\.\s*(?:[^\n]*?)[：:\s]*\n*\s*([^\n]+(?:\n[^\n]+)?)', content, re.I | re.MULTILINE)
        if summary_match:
            result["summary_cn"] = summary_match.group(1).strip()[:300]
        
        # 提取 publish_time - 查找"5."开头的行中的日期格式
        date_match = re.search(r'^5\.\s*(?:[^\n]*?)(\d{4})\s*[-年/]\s*(\d{1,2})\s*[-月/]\s*(\d{1,2})', content, re.I | re.MULTILINE)
        if date_match:
            result["publish_time"] = f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"
        
        # 提取 image_desc - 查找"6."开头的行
        desc_match = re.search(r'^6\.\s*(?:[^\n]*?)[：:\s]*\n*\s*([^\n]+(?:\n[^\n]+)?)', content, re.I | re.MULTILINE)
        if desc_match:
            image_desc = desc_match.group(1).strip()[:500]
            # 清理结构化标记，保留纯描述内容
            image_desc = _clean_vl_description(image_desc)
            result["image_desc"] = image_desc

        # 提取 significant - 查找"7."开头的行
        result["significant"] = parse_vl_significance(content)
        
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
   - summary_cn: 中文摘要。用2-3句话概括文章核心内容，突出关键信息（谁、在哪里、做了什么、为什么重要）。
   - full_text_cn: 中文全文翻译。必须翻译完整的正文内容，不要只翻译摘要！
     - 翻译整个文章正文，保持原文段落结构
     - 仅包含正文内容，不要包含导航、菜单、页脚、隐私政策、Cookie提示、社交链接
     - 如果正文很长，优先翻译前3000字的内容
   - publish_time: 提取文章的发布日期（格式 YYYY-MM-DD）。如果文中明确提到时间（如"2024年9月2日"），请提取该时间。
   
   【重要】summary_cn 和 full_text_cn 必须是不同的内容：
   - summary_cn 是简短摘要（2-3句话）
   - full_text_cn 是完整正文翻译（包含所有细节）
5. 【重要度打分】(significance) - 基于以下标准输出 0-10 的整数，数字越大越重要：
   - 与疏浚、港口、航道、海洋工程的直接相关度（相关度越高分越高）；
   - 商业价值：中标、合同、金额、大型企业动态（金额越大、企业越知名分越高）；
   - 影响范围：国家级/区域级项目、法规政策变化、重大事故或里程碑；
   - 时效性：新发布、正在进行的重大事件优先。
   只输出整数，不要输出小数或理由。

返回 JSON:
{{
  "is_junk": boolean,
  "category": "...",
  "title_cn": "...",
  "summary_cn": "...",
  "full_text_cn": "...",
  "publish_time": "YYYY-MM-DD",
  "significance": 8
}}
"""
    try:
        # 判断是否为 Qwen3.5 模型，需要添加 enable_thinking 参数
        is_qwen35 = "qwen3.5" in config.TEXT_MODEL.lower()
        
        if is_qwen35:
            resp = await client.chat.completions.create(
                model=config.TEXT_MODEL,
                messages=[{"role": "user", "content": filter_prompt}],
                extra_body={
                    "chat_template_kwargs": {
                        "enable_thinking": False
                    }
                }
            )
        else:
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

CLEAN_PROMPT = """你是新闻网页正文清洗助手。下面是从新闻网页抓取到的完整文本，可能包含导航、页眉、标签、相关新闻、订阅提示、页脚等冗余内容。

请只输出【这篇新闻的主体正文】：
1. 从报道正文第一段开始，到最后一个正文段落为止；
2. 保留作者/日期行之外的正文内容，图片说明（如“（照片由…提供）”）可以保留在对应段落位置；
3. 必须去掉标题重复、面包屑导航（如“主页”“回到总览”）、“查看帖子标签”、“分享这篇文章”、“相关新闻”、“订阅通讯”、“关注我们”及其之后的所有内容；
4. 不要翻译、不要总结、不要改写，也不要加任何解释，原样输出清洗后的正文段落。

【文本开始】
%s
【文本结束】
"""


async def clean_content_with_llm(client, item):
    """
    使用 LLM 从抓取文本中提取主体正文（去除标签/相关新闻/订阅等冗余）

    Args:
        client: AsyncOpenAI 客户端
        item: 文章字典，需包含 content

    Returns:
        清洗后的正文；内容过短或调用失败时返回 None
    """
    raw = (item.get('content') or '').strip()
    if len(raw) < 50:
        return None

    pre = clean_article_text(raw)
    if len(pre) > 12000:
        pre = pre[:12000]
    prompt = CLEAN_PROMPT % pre
    try:
        resp = await client.chat.completions.create(
            model=config.TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
        )
        content = resp.choices[0].message.content
        return content.strip() if content and content.strip() else None
    except Exception as e:
        print(f"[Text] 正文清洗失败 {item.get('url', '')}: {e}")
        return None


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
    """归一化 LLM 分析结果，保证必填字段与重要度分数类型一致"""
    if isinstance(result, list):
        if len(result) == 1 and isinstance(result[0], dict):
            result = result[0]
        else:
            return {
                "is_junk": False,
                "category": "Market",
                "title_cn": item.get("title"),
                "summary_cn": "",
                "full_text_cn": "",
                "publish_time": str(item.get("pub_date") or ""),
                "image_desc": "",
                "significant": None,
            }

    if isinstance(result, dict):
        return {
            "is_junk": result.get("is_junk", False),
            "category": result.get("category", "Market"),
            "title_cn": result.get("title_cn", item.get("title", "")),
            "summary_cn": result.get("summary_cn", ""),
            "full_text_cn": result.get("full_text_cn", ""),
            "publish_time": result.get("publish_time", str(item.get("pub_date") or "")),
            "image_desc": result.get("image_desc", ""),
            "significant": normalize_significance(result.get("significance")),
        }

    return {
        "is_junk": False,
        "category": "Market",
        "title_cn": item.get("title"),
        "summary_cn": "",
        "full_text_cn": "",
        "publish_time": str(item.get("pub_date") or ""),
        "image_desc": "",
        "significant": None,
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
            "significant": 0,
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
            "significant": 0,
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
        # 验证日期合理性：不能是未来日期，也不能是太早的日期（超过1年）
        try:
            from datetime import datetime
            extracted_date = datetime.strptime(str(pub_date)[:10], "%Y-%m-%d")
            now = datetime.now()
            # 如果提取的日期在未来，或者超过1年前，可能是错误的
            if extracted_date > now:
                analysis_log.append(f"4.3. **时间验证**: 提取日期{pub_date}在未来，使用原始时间")
                pub_date = str(item.get('pub_date', ''))
            elif (now - extracted_date).days > 365:
                analysis_log.append(f"4.3. **时间验证**: 提取日期{pub_date}超过1年前，尝试使用VL时间或原始时间")
                # 尝试使用VL的时间
                if vl_res and vl_res.get('publish_time'):
                    vl_date = datetime.strptime(str(vl_res['publish_time'])[:10], "%Y-%m-%d")
                    if vl_date <= now and (now - vl_date).days <= 365:
                        pub_date = vl_res['publish_time']
                        analysis_log.append(f"4.3. **时间修正**: 使用VL提取的时间{pub_date}")
                    else:
                        pub_date = str(item.get('pub_date', ''))
                else:
                    pub_date = str(item.get('pub_date', ''))
        except Exception:
            # 日期解析失败，回退到原始时间
            pub_date = str(item.get('pub_date', ''))
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
        "significant": final_result.get("significant"),
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
            # AI 正文清洗：先清理冗余，再用于后续分析
            if not (item.get('content_clean') or '').strip() and (item.get('content') or '').strip():
                cleaned = await clean_content_with_llm(client, item)
                if cleaned:
                    item['content_clean'] = cleaned
                    item['content'] = cleaned
                    article_id = item.get('id')
                    if article_id:
                        try:
                            database.update_content_clean(article_id, cleaned)
                        except Exception as e:
                            print(f"[Text] 清洗结果回写失败 id={article_id}: {e}")
            res = await analyze_item_from_db(client, item)
            if res:
                # 分析完成后立即保存回数据库
                database.save_article(res)
                results.append(res)

    tasks = [runner(item) for item in items]
    await asyncio.gather(*tasks)
    return results
