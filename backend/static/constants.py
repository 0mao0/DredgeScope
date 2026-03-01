"""
公共常量模块 - 集中管理全系统共享的常量和配置
"""

DEFAULT_CATEGORY = "Market"

ALLOWED_CATEGORIES = {
    "Bid",
    "Equipment",
    "Market",
    "Project",
    "Regulation",
    "R&D",
    "Other"
}

KEYWORD_CATEGORY_MAP = [
    (["contract", "tender", "bid", "award", "funding", "budget", "procurement"], "Bid"),
    (["delivery", "launch", "vessel", "ship", "dredger", "keel", "shipyard", "equipment", "fleet"], "Equipment"),
    (["acquire", "acquisition", "merger", "financial", "profit", "revenue", "earnings", "market", "investor", "share", "plan", "planning", "strategy", "strategic", "roadmap", "program", "programme", "initiative", "five-year", "five year", "5-year", "master plan", "protest", "strike", "blockade", "demonstration", "dispute", "conflict"], "Market"),
    (["project", "construction", "progress", "dredging", "completion", "completed", "underway", "restoration", "maintenance", "works"], "Project"),
    (["regulation", "policy", "law", "act", "legislation", "tariff", "compliance", "standard", "guideline", "guidelines", "requirement", "requirements", "permit", "approval", "overview", "introduction", "intro", "basics", "guide", "101"], "Regulation"),
    (["research", "technology", "innovation", "laboratory", "prototype", "r&d", "rd"], "R&D")
]

CATEGORY_CN_MAP = {
    "Bid": "中标信息",
    "Equipment": "装备动态",
    "Market": "市场情报",
    "Project": "项目进展",
    "Regulation": "政策法规",
    "R&D": "科技研发",
    "Other": "其他",
    "Unknown": "未知",
    "None": "未知"
}

JUNK_TITLES_EXACT = {
    "重回主页", "董事会", "监事会", "股东大会", "首页", "主页",
    "Home", "Back to Home", "Login", "Sign in", "Register",
    "About Us", "Contact Us", "Site Map", "Privacy Policy",
    "Terms of Use", "Search", "Menu", "Navigation",
    "English", "Español", "Français", "Deutsch", "中文",
    "Skip to main content", "ENTER YOUR ADMIN USERNAME",
    "Back to Home", "Login", "Sign in", "Register", "Site Map", "Contact Us",
    "Search", "Menu", "Navigation", "Privacy Policy", "Terms of Use"
}

JUNK_KEYWORDS_PARTIAL = [
    "404 Not Found", "Page Not Found", "Access Denied",
    "Browser Update", "Enable JavaScript"
]

def normalize_category(value):
    """归一化分类名称"""
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
        "news": "Market",
        "新闻": "Market",
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

def infer_category_from_text(text):
    """从文本内容推断分类"""
    if not text:
        return None
    lower = str(text).lower()
    for keywords, category in KEYWORD_CATEGORY_MAP:
        if any(k in lower for k in keywords):
            return category
    return None

def text_contains_any(text, keywords):
    """检查文本是否包含任意关键词"""
    if not text:
        return False
    lower = str(text).lower()
    return any(k in lower for k in keywords)

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

__all__ = [
    "DEFAULT_CATEGORY",
    "ALLOWED_CATEGORIES",
    "KEYWORD_CATEGORY_MAP",
    "CATEGORY_CN_MAP",
    "normalize_category",
    "infer_category_from_text",
    "text_contains_any",
    "normalize_event_text",
    "build_event_signature",
    "extract_regulation_core",
    "consolidate_regulation_events",
    "JUNK_TITLES_EXACT",
    "JUNK_KEYWORDS_PARTIAL"
]
