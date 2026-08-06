# backend/analysis/company_analysis.py
"""公司运营分析模块 - 从新闻中提取公司项目、金额数据，区分新签/在建"""

import re
import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# 全球主要疏浚公司关键词映射（排除中交CCCC）
COMPANY_KEYWORDS = {
    'DEME': ['deme'],
    'Van Oord': ['van oord'],
    'Boskalis': ['boskalis'],
    'Jan De Nul': ['jan de nul'],
    'Royal IHC': ['royal ihc'],
    'Great Lakes': ['great lakes', 'gldd'],
    'Weeks Marine': ['weeks marine'],
    'Manson': ['manson'],
    'Dutra Group': ['dutra group'],
    'Norfolk Dredging': ['norfolk dredging'],
    'Orion Marine': ['orion marine'],
    'NMDC': ['nmdc'],
    'Curtin Maritime': ['curtin maritime'],
}

# 汇率配置（按发布年份）
EXCHANGE_RATES = {'2025': 7.15, '2026': 7.20, 'default': 7.20}

# 项目类型关键词
PROJECT_TYPE_KEYWORDS = {
    '填海': ['填海', 'reclamation', 'land reclamation'],
    '维护疏浚': ['维护疏浚', 'maintenance dredging'],
    '航道疏浚': ['航道疏浚', 'channel dredging', 'capital dredging', '航道拓宽'],
    '海滩补沙': ['海滩补沙', 'beach nourishment', 'beach restoration', 'renourishment'],
    '港池疏浚': ['港池疏浚', 'basin'],
}

# 行业基准单价（元/m³）
UNIT_PRICES = {
    '维护疏浚': {'low': 30, 'mid': 60, 'high': 120},
    '航道疏浚': {'low': 50, 'mid': 100, 'high': 200},
    '填海': {'low': 40, 'mid': 80, 'high': 150},
    '海滩补沙': {'low': 50, 'mid': 100, 'high': 180},
    '港池疏浚': {'low': 40, 'mid': 80, 'high': 160},
    '未知类型': {'low': 40, 'mid': 80, 'high': 150},
}

# 地区调整系数
REGION_FACTOR = {
    '美国': 1.2, '欧洲': 1.3, '中东': 1.1, '东南亚': 0.8,
    '南美': 0.9, '非洲': 0.7, '中国': 0.6, '其他': 1.0,
}

# 新签(Bid)与在建(Project)分类
NEW_CONTRACT_CATEGORIES = {'Bid'}
ONGOING_CATEGORIES = {'Project'}


@dataclass
class ProjectData:
    """项目数据结构"""
    company: str
    title: str
    category: str
    amount_cny: Optional[float] = None  # 万元人民币
    volume: Optional[float] = None      # 立方米
    proj_type: str = '未知类型'
    region: str = '其他'
    is_estimated: bool = False
    article_id: Optional[int] = None
    article_url: Optional[str] = None
    pub_date: Optional[str] = None

    @property
    def is_new_contract(self) -> bool:
        """是否为新签项目（Bid类）"""
        return self.category in NEW_CONTRACT_CATEGORIES


def get_exchange_rate(pub_date: Optional[str] = None) -> float:
    """根据发布时间获取汇率"""
    if pub_date:
        return EXCHANGE_RATES.get(str(pub_date)[:4], EXCHANGE_RATES['default'])
    return EXCHANGE_RATES['default']


def extract_company(text: str) -> Optional[str]:
    """从文本中提取公司名（中交CCCC默认排除）"""
    text_lower = text.lower()
    for company, keywords in COMPANY_KEYWORDS.items():
        if any(k.lower() in text_lower for k in keywords):
            return company
    return None


def extract_amount_cny(text: str, pub_date: Optional[str] = None) -> Tuple[Optional[float], str]:
    """提取金额，统一返回万元人民币及原始货币类型"""
    rate = get_exchange_rate(pub_date)

    m = re.search(r'(\d+(?:\.\d+)?)\s*亿元', text)
    if m:
        return float(m.group(1)) * 10000, 'CNY'

    m = re.search(r'(\d+(?:\.\d+)?)\s*万元', text)
    if m:
        return float(m.group(1)), 'CNY'

    # $ 美元 million: 12.9M = 1290万美元
    m = re.search(r'\$\s*(\d+(?:\.\d+)?)\s*(?:M{1,2}|million)', text, re.I)
    if m:
        usd_millions = float(m.group(1))
        return usd_millions * 100 * rate, 'USD'

    m = re.search(r'\$\s*(\d+(?:\.\d+)?)\s*billion', text, re.I)
    if m:
        usd_billions = float(m.group(1))
        return usd_billions * 100000 * rate, 'USD'

    m = re.search(r'(\d+(?:\.\d+)?)\s*亿美元', text)
    if m:
        return float(m.group(1)) * 10000 * rate, 'USD'

    m = re.search(r'(\d+(?:\.\d+)?)\s*万美元', text)
    if m:
        return float(m.group(1)) * rate, 'USD'

    return None, 'unknown'


def extract_volume(text: str) -> Optional[float]:
    """提取方量（立方米）"""
    text_clean = text.replace(',', '')

    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:万方|万立方米)', text_clean)
    if m:
        return float(m.group(1)) * 10000

    m = re.search(r'(\d+(?:\.\d+)?)\s*million\s*m³', text_clean, re.I)
    if m:
        return float(m.group(1)) * 1000000

    m = re.search(r'(\d+(?:\.\d+)?)\s*million\s*cubic\s*meters', text_clean, re.I)
    if m:
        return float(m.group(1)) * 1000000

    m = re.search(r'(\d+(?:\.\d+)?)\s*立方米', text_clean)
    if m:
        return float(m.group(1))

    m = re.search(r'(\d+(?:\.\d+)?)\s*m³', text_clean)
    if m and float(m.group(1)) > 10000:
        return float(m.group(1))

    return None


def extract_project_type(text: str) -> str:
    """提取项目类型"""
    for proj_type, keywords in PROJECT_TYPE_KEYWORDS.items():
        if any(k in text.lower() for k in keywords):
            return proj_type
    return '未知类型'


def extract_region(text: str) -> str:
    """提取地区"""
    text_lower = text.lower()
    if any(k in text_lower for k in ['usace', 'united states', 'america', 'california', 'florida']):
        return '美国'
    elif any(k in text_lower for k in ['netherlands', 'belgium', 'germany', 'france', 'europe']):
        return '欧洲'
    elif any(k in text_lower for k in ['saudi', 'uae', 'qatar', 'dubai', 'middle east']):
        return '中东'
    elif any(k in text_lower for k in ['vietnam', 'thailand', 'indonesia', 'malaysia']):
        return '东南亚'
    elif any(k in text_lower for k in ['brazil', 'argentina', 'latin america']):
        return '南美'
    elif any(k in text_lower for k in ['nigeria', 'ghana', 'kenya', 'africa']):
        return '非洲'
    return '其他'


def estimate_amount_from_volume(volume: float, proj_type: str, region: str) -> Tuple[float, float, float]:
    """根据方量估算金额（低、中、高），返回万元人民币"""
    prices = UNIT_PRICES.get(proj_type, UNIT_PRICES['未知类型'])
    region_factor = REGION_FACTOR.get(region, 1.0)
    est_low = volume * prices['low'] * region_factor / 10000
    est_mid = volume * prices['mid'] * region_factor / 10000
    est_high = volume * prices['high'] * region_factor / 10000
    return est_low, est_mid, est_high


def _title_fingerprint(title: str) -> str:
    """提取标题指纹用于同项目去重。去除新闻前缀后取核心词。

    Args:
        title: 文章标题

    Returns:
        指纹字符串，空标题返回空串
    """
    if not title:
        return ''
    text = title.strip()
    # 去除常见新闻前缀
    for prefix in ('BREAKING NEWS', 'EXCLUSIVE', 'PHOTO OF THE DAY', 'VIDEO', 'UPDATE', 'NEW', 'HOT'):
        text = re.sub(rf'^{prefix}\s*[:：\-–]?\s*', '', text, flags=re.I)
    # 小写、去标点，仅保留字母数字与中文
    text = re.sub(r'[^a-z0-9\u4e00-\u9fff ]', ' ', text.lower())
    words = [w for w in text.split() if w]
    return ' '.join(words[:8])


def analyze_articles(articles: List[Dict]) -> Dict[str, List[ProjectData]]:
    """分析文章列表，提取公司项目数据。只处理 Bid/Project 类（新签/在建）。

    同项目多源报道按标题指纹去重：同一公司内指纹相同只保留一篇。
    """
    company_projects = {company: [] for company in COMPANY_KEYWORDS}
    seen_fingerprints = {company: set() for company in COMPANY_KEYWORDS}

    for article in articles:
        # 只分析新签/在建类文章
        category = article.get('category', '')
        if category not in NEW_CONTRACT_CATEGORIES | ONGOING_CATEGORIES:
            continue

        # 结合标题、中文摘要、全文翻译提取信息
        title = article.get('title', '') or ''
        summary = article.get('summary_cn', '') or ''
        full_text = article.get('full_text_cn', '') or ''
        text = f"{title} {summary} {full_text[:3000]}"

        company = extract_company(text)
        if not company:
            continue

        # 同项目去重：同一公司内标题指纹相同视为同一项目
        fp = _title_fingerprint(title)
        if fp and fp in seen_fingerprints[company]:
            continue
        if fp:
            seen_fingerprints[company].add(fp)

        amount_cny, _ = extract_amount_cny(text, article.get('pub_date'))
        volume = extract_volume(text)
        proj_type = extract_project_type(text)
        region = extract_region(text)

        is_estimated = False
        if volume and not amount_cny:
            _, est_mid, _ = estimate_amount_from_volume(volume, proj_type, region)
            amount_cny = est_mid
            is_estimated = True

        company_projects[company].append(ProjectData(
            company=company,
            title=title[:120],
            category=category,
            amount_cny=amount_cny,
            volume=volume,
            proj_type=proj_type,
            region=region,
            is_estimated=is_estimated,
            article_id=article.get('id'),
            article_url=article.get('url'),
            pub_date=article.get('pub_date'),
        ))

    return company_projects


async def deduplicate_with_llm(company_projects: Dict[str, List[ProjectData]],
                               max_per_company: int = 40) -> Dict[str, Dict[int, str]]:
    """使用LLM对项目做实体识别聚类，识别同项目多源报道。

    Args:
        company_projects: analyze_articles 输出的项目字典
        max_per_company: 每家公司最多送入LLM的文章数（按发布时间倒序取最新）

    Returns:
        {company: {article_id: canonical_project_name}}，失败公司返回空dict
    """
    import os
    import sys
    import json
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    import config
    from openai import AsyncOpenAI

    if not config.TEXT_LLM_API_KEY:
        return {}

    client = AsyncOpenAI(api_key=config.TEXT_LLM_API_KEY, base_url=config.TEXT_LLM_API_BASE)
    result: Dict[str, Dict[int, str]] = {}

    for company, projects in company_projects.items():
        if not projects:
            continue
        # 按发布时间倒序取最近N篇，控制token
        sorted_projects = sorted(projects, key=lambda p: p.pub_date or '', reverse=True)
        items = []
        for p in sorted_projects[:max_per_company]:
            if p.article_id is None:
                continue
            items.append({
                'id': p.article_id,
                'title': p.title,
                'summary': '',
            })
        if not items:
            continue

        prompt = f"""你是疏浚行业情报分析师。以下是{company}公司相关的新闻报道列表，同一项目常被多家媒体或分阶段多次报道。

请识别属于同一项目的报道，并为每个项目给出规范名称（英文短语，如 "Port of Santos dredging"）。

注意：
- 同一项目的不同阶段报道（中标、开工、进展）视为同一项目
- 无关内容（财报、人事变动、战略合作、行业会议）不要归入任何项目

【报道列表】
{items}

输出JSON（仅此内容）：
{{"projects": [{{"name": "项目规范名", "article_ids": [id...]}}]}}"""

        try:
            is_qwen = "qwen3" in config.TEXT_MODEL.lower()
            kwargs = {"model": config.TEXT_MODEL, "messages": [{"role": "user", "content": prompt}]}
            if is_qwen:
                kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
            else:
                kwargs["response_format"] = {"type": "json_object"}
            resp = await client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            data = json.loads(content)
            company_map = {}
            for proj in data.get('projects', []):
                name = proj.get('name', '').strip()
                for aid in proj.get('article_ids', []):
                    try:
                        company_map[int(aid)] = name
                    except (TypeError, ValueError):
                        continue
            result[company] = company_map
        except Exception as e:
            print(f"[LLM去重] {company} 失败: {e}")
            continue
    return result


def apply_entity_dedup(company_projects: Dict[str, List[ProjectData]],
                       entity_map: Dict[str, Dict[int, str]]) -> Dict[str, List[ProjectData]]:
    """按LLM实体映射聚合去重。同实体保留最新文章为代表，金额/方量取组内最大值。

    Args:
        company_projects: 项目字典
        entity_map: deduplicate_with_llm 返回的映射

    Returns:
        去重后的项目字典
    """
    result = {}
    for company, projects in company_projects.items():
        mapping = entity_map.get(company, {})
        if not mapping:
            result[company] = projects
            continue

        groups = {}
        for p in projects:
            name = mapping.get(p.article_id)
            # 无实体映射的文章按自身id单独成组，不合并
            key = name if name else f"__raw__{p.article_id}"
            groups.setdefault(key, []).append(p)

        deduped = []
        for key, group in groups.items():
            # 取最新一篇作为代表
            rep = max(group, key=lambda p: p.pub_date or '')
            # 金额/方量取组内最大值（重复报道可能只有部分含数据）
            amounts = [p.amount_cny for p in group if p.amount_cny]
            volumes = [p.volume for p in group if p.volume]
            if amounts:
                rep.amount_cny = max(amounts)
            if volumes:
                rep.volume = max(volumes)
            deduped.append(rep)
        result[company] = deduped
    return result


async def get_project_entities_cached(company_projects: Dict[str, List[ProjectData]],
                                      force: bool = False) -> Dict[str, Dict[int, str]]:
    """读取或增量生成项目实体映射缓存。

    已有缓存时只对新增文章做LLM识别并合并，避免每次爬取全量重新聚类。
    缓存结构: {"generated_at", "entities": {company: {aid: name}}, "covered_ids": [...]}

    Args:
        company_projects: analyze_articles 输出的项目字典
        force: 是否强制全量重新生成

    Returns:
        {company: {article_id: canonical_project_name}}
    """
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    import config
    cache_path = os.path.join(config.DATA_DIR, 'project_entities.json')

    # 读缓存
    entities: Dict[str, Dict[int, str]] = {}
    covered_ids = set()
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cached = json.load(f)
            # JSON key 均为字符串，需转回 int
            entities = {
                company: {int(k): v for k, v in mapping.items()}
                for company, mapping in cached.get('entities', {}).items()
            }
            covered_ids = {int(x) for x in cached.get('covered_ids', [])}
        except Exception:
            pass

    if force:
        # 全量重新生成
        entities = await deduplicate_with_llm(company_projects)
        for mapping in entities.values():
            covered_ids.update(mapping.keys())
    else:
        # 找出新增文章（未覆盖的article_id）
        all_ids = {p.article_id for ps in company_projects.values() for p in ps if p.article_id}
        new_ids = all_ids - covered_ids
        if not new_ids:
            return entities

        # 仅对"新增≥2篇"的公司调LLM聚类（单篇无重复可去）
        new_projects = {
            company: [p for p in ps if p.article_id in new_ids]
            for company, ps in company_projects.items()
            if sum(1 for p in ps if p.article_id in new_ids) >= 2
        }
        if new_projects:
            new_entities = await deduplicate_with_llm(new_projects)
            for company, mapping in new_entities.items():
                entities.setdefault(company, {}).update(mapping)
        # 送过LLM的文章（无论是否生成映射）都记为已覆盖，避免重复处理
        covered_ids.update(new_ids)

    # 写入缓存（含增量更新时间）
    try:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump({
                'generated_at': datetime.now().isoformat(),
                'entities': entities,
                'covered_ids': sorted(covered_ids),
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[实体缓存] 写入失败: {e}")

    return entities


def get_company_statistics(company_projects: Dict[str, List[ProjectData]]) -> List[Dict]:
    """生成公司统计数据，区分新签与在建"""
    stats = []

    for company, projects in company_projects.items():
        if not projects:
            continue

        new_contracts = [p for p in projects if p.is_new_contract]
        ongoing_projects = [p for p in projects if not p.is_new_contract]

        def _sum_amount(items):
            return sum(p.amount_cny for p in items if p.amount_cny)

        stats.append({
            'company': company,
            'project_count': len(projects),
            # 新签
            'new_contract_count': len(new_contracts),
            'new_contract_amount': _sum_amount(new_contracts),
            # 在建
            'ongoing_count': len(ongoing_projects),
            'ongoing_amount': _sum_amount(ongoing_projects),
            # 合计
            'total_amount': _sum_amount(projects),
            'total_volume': sum(p.volume for p in projects if p.volume),
            'estimated_count': sum(1 for p in projects if p.is_estimated),
            'projects': [
                {
                    'title': p.title,
                    'category': p.category,
                    'is_new_contract': p.is_new_contract,
                    'amount_cny': p.amount_cny,
                    'volume': p.volume,
                    'proj_type': p.proj_type,
                    'region': p.region,
                    'is_estimated': p.is_estimated,
                    'article_id': p.article_id,
                    'article_url': p.article_url,
                    'pub_date': p.pub_date,
                }
                for p in projects
            ],
        })

    # 按项目总数排序
    stats.sort(key=lambda x: x['project_count'], reverse=True)
    return stats
