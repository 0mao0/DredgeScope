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

__all__ = [
    "DEFAULT_CATEGORY",
    "ALLOWED_CATEGORIES",
    "KEYWORD_CATEGORY_MAP",
    "CATEGORY_CN_MAP",
    "normalize_category",
    "infer_category_from_text",
    "text_contains_any",
    "JUNK_TITLES_EXACT",
    "JUNK_KEYWORDS_PARTIAL"
]
