# backend/analysis/industry_trends.py
"""行业趋势分析模块 - 从新闻数据中提取船型、规模、技术、体量分布，并生成AI洞察报告"""

import re
import os
import sys
import json
from typing import Dict, List, Optional
from collections import Counter, defaultdict
from datetime import datetime

# 船型关键词映射
SHIP_TYPE_KEYWORDS = {
    'TSHD': ['tshd', 'trailing suction hopper', '耙吸挖泥船', '耙吸'],
    'CSD': ['csd', 'cutter suction', '绞吸挖泥船', '绞吸'],
    'Backhoe': ['backhoe', '反铲挖泥船'],
    'Grab': ['grab', '抓斗挖泥船'],
    'Auger': ['auger', '螺旋挖泥船'],
    '其他': [],
}

# 技术趋势关键词
TECH_KEYWORDS = {
    '智能化': ['ai ', 'artificial intelligence', '智能', 'autonomous', '自动化'],
    '绿色化': ['green', 'eco', '零排放', 'electric'],
    '大型化': ['largest', 'biggest', '超大型', '最大'],
    '数字化': ['digital', '数字化'],
}

# 船型体量关键词（舱容）
VOLUME_KEYWORDS = {
    '小型(<5000m³)': [r'\b[1-4]0{3,4}\s*m³', r'舱容\s*[1-4]0{3,4}'],
    '中型(5000-15000m³)': [r'\b[5-9]\d{3}|1[0-4]\d{4}\s*m³'],
    '大型(>15000m³)': [r'\b(?:1[5-9]\d{4}|[2-9]\d{5,})\s*m³', r'超大型'],
}

# AI报告缓存文件路径（延迟初始化）
_AI_REPORT_PATH = None


def extract_ship_types(text: str) -> List[str]:
    """从文本中提取船型"""
    text_lower = text.lower()
    found = [st for st, kws in SHIP_TYPE_KEYWORDS.items()
             if st != '其他' and any(k in text_lower for k in kws)]
    return found if found else ['其他']


def extract_scale(text: str) -> str:
    """提取项目规模。金额单位为'亿元'，阈值正确对比"""
    text_lower = text.lower()
    if any(k in text_lower for k in ['mega', '特大型', '超大型']):
        return '大型项目'
    if any(k in text_lower for k in ['mid-size', '中型']):
        return '中型项目'

    m = re.search(r'(\d+(?:\.\d+)?)\s*(亿元|亿美元|million|billion)', text, re.I)
    if m:
        amount = float(m.group(1))
        unit = m.group(2).lower()
        if unit == '亿美元':
            amount *= 7.2
        elif unit == 'million':
            amount = amount * 100 / 10000  # 100万美元 = 0.01亿美元
        elif unit == 'billion':
            amount *= 10
        if amount >= 10:
            return '大型项目'
        elif amount >= 1:
            return '中型项目'
        else:
            return '小型项目'

    m = re.search(r'(\d+(?:\.\d+)?)\s*万方', text)
    if m:
        volume_wan = float(m.group(1))
        if volume_wan >= 300:
            return '大型项目'
        elif volume_wan >= 50:
            return '中型项目'
        else:
            return '小型项目'
    return '未指定'


def extract_tech_trends(text: str) -> List[str]:
    """提取技术趋势"""
    text_lower = text.lower()
    return [t for t, kws in TECH_KEYWORDS.items() if any(k in text_lower for k in kws)]


def extract_volume_class(text: str) -> str:
    """提取船型体量等级"""
    for level, patterns in VOLUME_KEYWORDS.items():
        if any(re.search(p, text) for p in patterns):
            return level
    return '未指定'


def analyze_trends(articles: List[Dict], time_range: str = 'monthly') -> List[Dict]:
    """按月/季/年分析行业趋势，返回字典列表"""
    time_groups = defaultdict(list)
    for article in articles:
        pub_date = article.get('pub_date', '') or ''
        if not pub_date:
            continue
        if time_range == 'monthly':
            period = pub_date[:7]
        elif time_range == 'quarterly':
            period = f"{pub_date[:4]}-Q{(int(pub_date[5:7]) - 1) // 3 + 1}"
        else:
            period = pub_date[:4]
        time_groups[period].append(article)

    trends = []
    for period in sorted(time_groups):
        scale_counter = Counter()
        ship_counter = Counter()
        tech_counter = Counter()
        volume_class_counter = Counter()
        total_projects = 0
        total_amount = 0.0
        total_volume = 0.0

        for article in time_groups[period]:
            if article.get('category') not in ('Project', 'Bid'):
                continue
            total_projects += 1
            full_text = (article.get('full_text_cn', '') or '')[:3000]
            text = f"{article.get('title', '')} {article.get('summary_cn', '')} {full_text}"

            scale_counter[extract_scale(text)] += 1
            for st in extract_ship_types(text):
                ship_counter[st] += 1
            for tech in extract_tech_trends(text):
                tech_counter[tech] += 1
            volume_class_counter[extract_volume_class(text)] += 1

            from analysis.company_analysis import extract_amount_cny, extract_volume
            amt, _ = extract_amount_cny(text, pub_date)
            if amt:
                total_amount += amt
            vol = extract_volume(text)
            if vol:
                total_volume += vol

        trends.append({
            'period': period,
            'scale_trend': dict(scale_counter),
            'ship_type_trend': dict(ship_counter),
            'tech_trend': dict(tech_counter),
            'volume_class_trend': dict(volume_class_counter),
            'total_projects': total_projects,
            'total_amount': total_amount,
            'total_volume': total_volume,
        })
    return trends


def get_ship_type_analysis(articles: List[Dict]) -> Dict:
    """分析船型使用情况"""
    data = defaultdict(lambda: {'count': 0, 'companies': set(), 'projects': []})
    for article in articles:
        text = f"{article.get('title', '')} {article.get('summary_cn', '')}"
        for st in extract_ship_types(text):
            if st == '其他':
                continue
            data[st]['count'] += 1
            data[st]['projects'].append(text[:50])
            from analysis.company_analysis import extract_company
            company = extract_company(text)
            if company:
                data[st]['companies'].add(company)
    return {
        st: {'count': v['count'], 'companies': sorted(v['companies']), 'projects': v['projects'][:10]}
        for st, v in data.items()
    }


def get_scale_distribution(articles: List[Dict]) -> Dict[str, int]:
    """项目规模分布"""
    counter = Counter()
    for article in articles:
        if article.get('category') not in ('Project', 'Bid'):
            continue
        text = f"{article.get('title', '')} {article.get('summary_cn', '')}"
        counter[extract_scale(text)] += 1
    return dict(counter)


def get_tech_trends(articles: List[Dict]) -> Dict[str, int]:
    """技术趋势分布"""
    counter = Counter()
    for article in articles:
        text = f"{article.get('title', '')} {article.get('summary_cn', '')}"
        for tech in extract_tech_trends(text):
            counter[tech] += 1
    return dict(counter)


# ------------------- AI 趋势报告（Qwen3.6-35B-A3B-FP8） -------------------


def _get_ai_report_path() -> str:
    """获取AI报告缓存文件路径"""
    global _AI_REPORT_PATH
    if _AI_REPORT_PATH is None:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        import config
        _AI_REPORT_PATH = os.path.join(config.DATA_DIR, 'ai_trend_report.json')
    return _AI_REPORT_PATH


def _read_ai_report_cache() -> Optional[Dict]:
    """读取AI报告缓存"""
    path = _get_ai_report_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    return None


def _write_ai_report_cache(report: Dict) -> None:
    """写入AI报告缓存"""
    path = _get_ai_report_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Trends] 缓存写入失败: {e}")


async def get_ai_trend_report(force: bool = False) -> Dict:
    """获取AI行业趋势报告。24小时内复用缓存，过期重新生成。

    Args:
        force: 是否强制重新生成

    Returns:
        AI报告字典，包含 summary/scale_trend/rd_trend/ship_trend/volume_trend/insights
    """
    # 缓存检查：默认24小时复用
    existing = _read_ai_report_cache()
    if not force and existing and existing.get('generated_at'):
        last = datetime.fromisoformat(existing['generated_at'])
        if (datetime.now() - last).total_seconds() < 86400:
            return existing

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    import config
    import database
    from openai import AsyncOpenAI

    if not config.TEXT_LLM_API_KEY:
        return {'summary': '未配置TEXT_LLM_API_KEY', 'insights': [], 'generated_at': datetime.now().isoformat()}

    articles = database.get_articles_for_analysis()
    trends = analyze_trends(articles, 'monthly')
    ship_types = get_ship_type_analysis(articles)

    # 判断各月份是否完整（该月最后一天是否已过）
    import calendar
    today = datetime.now()
    def _is_complete_month(period: str) -> bool:
        """判断月份是否已完整结束"""
        try:
            year, month = int(period[:4]), int(period[5:7])
            last_day = calendar.monthrange(year, month)[1]
            return today >= datetime(year, month, last_day)
        except Exception:
            return True

    # 构造供LLM分析的最近6个月汇总
    trend_summary = []
    for t in trends[-6:]:
        trend_summary.append({
            'period': t['period'],
            'complete_month': _is_complete_month(t['period']),
            'projects': t['total_projects'],
            'amount_wan': round(t['total_amount'], 0),
            'volume_wan': round(t['total_volume'] / 10000, 1),
            'scale': t['scale_trend'],
            'ship_types': t['ship_type_trend'],
            'tech': t['tech_trend'],
        })

    prompt = f"""你是全球疏浚行业高级分析师。请基于以下最近6个月的疏浚行业新闻统计数据，撰写一份行业趋势分析报告。

【当前日期】{today.strftime('%Y-%m-%d')}

【重要时间线规则】
- 数据中的"complete_month"字段表示该月是否为完整月份：true=该月已结束，false=该月仍在进行中（数据不完整）。
- 最新月份很可能是进行中月份，其项目数/金额天然偏低，绝不能作为趋势下降的依据。
- 分析趋势时必须基于完整月份之间的对比；进行中月份仅作参考，如需提及必须注明"X月为进行中月份，数据尚未完整统计"。
- 禁止出现"大幅减少/骤降/萎缩"等针对不完整月份的结论。

【月度统计数据】
{trend_summary}

【全期船型分布】
{ship_types}

请分析以下方面并输出JSON（不要输出任何其他内容）：
1. summary: 300字以内的整体行业洞察（产业规模、市场活跃度变化）
2. scale_trend: 150字以内的项目规模趋势分析（大型化还是分散化）
3. rd_trend: 150字以内的研发/技术趋势分析
4. ship_trend: 150字以内的船型结构变化趋势分析
5. volume_trend: 150字以内的船型体量（舱容）变化分析
6. insights: 3-5条关键洞察，每条不超过60字

返回格式:
{{
  "summary": "...",
  "scale_trend": "...",
  "rd_trend": "...",
  "ship_trend": "...",
  "volume_trend": "...",
  "insights": ["...", "..."]
}}"""

    client = AsyncOpenAI(api_key=config.TEXT_LLM_API_KEY, base_url=config.TEXT_LLM_API_BASE)
    try:
        # Qwen3.5/Qwen3.6 等推理模型关闭思考模式输出 JSON，与 info_analysis.py 一致
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

        report = json.loads(content)
        report['generated_at'] = datetime.now().isoformat()
        _write_ai_report_cache(report)
        return report
    except Exception as e:
        print(f"[Trends] AI报告生成失败: {e}")
        return {'summary': f'AI报告生成失败: {e}', 'insights': [], 'generated_at': datetime.now().isoformat()}
