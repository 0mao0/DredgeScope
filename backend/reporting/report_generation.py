import base64
from datetime import datetime
import config
import database
from static.constants import (
    DEFAULT_CATEGORY,
    ALLOWED_CATEGORIES,
    normalize_category
)

def save_history(results):
    """保存历史数据 (仅 SQLite)"""
    for r in results:
        article_category = normalize_category(r.get('category')) or DEFAULT_CATEGORY
        if article_category not in ALLOWED_CATEGORIES:
            article_category = DEFAULT_CATEGORY
        r["category"] = article_category
        database.save_article(r)
    print(f"数据已保存到数据库: {database.DB_PATH}")

def generate_report(results):
    """生成 Markdown 报告"""
    # ... (rest of the function remains same, but maybe I should update it to render category-specific fields)
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    md_lines = [f"# 🌏 全球疏浚情报速览 ({now_str})", ""]
    
    md_lines.append("## 📊 分析概况")
    md_lines.append(f"- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md_lines.append(f"- **总文章数**: {len(results)} 篇")
    md_lines.append(f"- **AI 模型**: {config.TEXT_MODEL} (文本) + {config.VL_MODEL} (视觉)")
    md_lines.append("")

    # 按分类聚合
    categories_map = {
        "Market": "📈 市场动态 (Market Dynamics)",
        "Bid": "💰 中标信息 (Bid Information)",
        "Project": "🏗️ 项目信息 (Project Status)",
        "Equipment": "🛠️ 设备修造 (Equipment & Shipbuilding)",
        "R&D": "🔬 科技研发 (R&D)",
        "Regulation": "⚖️ 技术法规 (Regulation)"
    }
    
    grouped_articles = {k: [] for k in categories_map.keys()}
    for r in results:
        article_category = normalize_category(r.get('category')) or DEFAULT_CATEGORY
        if article_category not in ALLOWED_CATEGORIES:
            article_category = DEFAULT_CATEGORY
        if article_category not in grouped_articles:
            article_category = DEFAULT_CATEGORY
        grouped_articles[article_category].append(r)

    for cat_key, cat_name in categories_map.items():
        items = grouped_articles[cat_key]
        if not items: continue
        
        md_lines.append(f"## {cat_name}")
        for article in items:
            t_cn = article.get('title_cn')
            t_orig = article.get('title') or ""
            display_title = t_cn or t_orig
            if t_cn and t_cn != t_orig:
                display_title = f"[译] {display_title}"
            url = article.get('url', '')
            md_lines.append(f"### [{display_title}]({url})")
            md_lines.append(f"- **摘要**: {article.get('summary_cn', '暂无摘要')}")
            vl_desc = article.get('image_desc', '')
            if vl_desc and vl_desc != "无视觉分析" and "视觉补充" not in article.get('summary_cn', ''):
                md_lines.append(f"- **👀 视觉补充**: {vl_desc}")
            md_lines.append("")

    # 增加详细日志区域
    md_lines.append("---")
    md_lines.append("## 🔍 详细分析日志")
    for r in results:
        md_lines.append(f"### {r['title']}")
        if 'analysis_log' in r:
            for step in r['analysis_log']:
                md_lines.append(f"- {step}")
        else:
            md_lines.append("- 无日志信息")
            
    # 写文件
    with open(config.REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(md_lines))
        
    print(f"报告已生成: {config.REPORT_FILE}")
