import json
import base64
from datetime import datetime
import config
import database
from static.constants import (
    DEFAULT_CATEGORY,
    ALLOWED_CATEGORIES,
    KEYWORD_CATEGORY_MAP,
    normalize_category,
    normalize_event_text,
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

def save_history(results):
    """保存历史数据 (仅 SQLite)"""
    
    # 1. 保存到 SQLite
    for r in results:
        article_category = normalize_category(r.get('category')) or DEFAULT_CATEGORY
        if article_category not in ALLOWED_CATEGORIES:
            article_category = DEFAULT_CATEGORY
        events = normalize_events(r.get('events', []), article_category)
        # 如果没有 events，构造一个默认的
        if not events:
            events = [{
                "category": article_category,
                "project_name": r['title'],
                "location": "未提取",
                "contract_value": "未提取"
            }]
        
        database.save_article_and_events(r, events)
        
    print(f"数据已保存到数据库: {database.DB_PATH}")

    # 2. JSONL 已废弃
    # history.jsonl is no longer needed as we use SQLite.

def generate_report(results):
    """生成 Markdown 报告"""
    # ... (rest of the function remains same, but maybe I should update it to render category-specific fields)
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    md_lines = [f"# 🌏 全球疏浚情报速览 ({now_str})", ""]
    
    md_lines.append("## 📊 分析概况")
    md_lines.append(f"- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md_lines.append(f"- **总文章数**: {len(results)} 篇")
    md_lines.append(f"- **AI 模型**: {config.TEXT_MODEL} (文本) + {config.VL_MODEL} (视觉)")
    
    # 重新计算 events count
    total_events = 0
    for r in results:
        total_events += len(r.get('events', [])) or 1
        
    md_lines.append(f"- **提取事件数**: {total_events} 个")
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
    
    # 收集所有事件
    grouped_events = {k: [] for k in categories_map.keys()}
    
    for r in results:
        article_category = normalize_category(r.get('category')) or DEFAULT_CATEGORY
        if article_category not in ALLOWED_CATEGORIES:
            article_category = DEFAULT_CATEGORY
        events = normalize_events(r.get('events', []), article_category)
        if not events:
             events = [{
                 "project_name": r['title'],
                 "category": article_category,
                 "location": "未提取",
                 "contract_value": "未提取"
             }]

        for evt in events:
            # 再次防御，如果 events 里面混入了字符串
            if isinstance(evt, str):
                continue
                
            cat = normalize_category(evt.get('category')) or article_category or DEFAULT_CATEGORY
            if cat not in grouped_events:
                cat = DEFAULT_CATEGORY
            
            evt_wrapper = {
                "event_data": evt,
                "source_article": r
            }
            grouped_events[cat].append(evt_wrapper)

    for cat_key, cat_name in categories_map.items():
        items = grouped_events[cat_key]
        if not items: continue
        
        md_lines.append(f"## {cat_name}")
        
        # 二级聚合：在每个分类下，按文章聚合事件
        # 结构：Category -> Article -> Events
        articles_in_cat = {}
        for item in items:
            art_url = item['source_article']['url']
            if art_url not in articles_in_cat:
                articles_in_cat[art_url] = {
                    "article": item['source_article'],
                    "events": []
                }
            # 去重：检查该事件是否已经添加过 (简单比较 json string)
            evt_str = json.dumps(item['event_data'], sort_keys=True)
            existing_evts = [json.dumps(e, sort_keys=True) for e in articles_in_cat[art_url]['events']]
            if evt_str not in existing_evts:
                 articles_in_cat[art_url]['events'].append(item['event_data'])

        for art_url, art_data in articles_in_cat.items():
            article = art_data['article']
            events = art_data['events']
            
            # 1. 显示文章标题 (只显示一次)
            t_cn = article.get('title_cn')
            t_orig = article['title']
            display_title = t_orig
            if t_cn:
                display_title = t_cn
                if t_cn != t_orig:
                     display_title = f"[译] {display_title}"
            
            url = article['url']
            md_lines.append(f"### [{display_title}]({url})")
            
            # 2. 显示文章摘要和视觉补充 (只显示一次)
            md_lines.append(f"- **摘要**: {article.get('summary_cn', '暂无摘要')}")
            
            vl_desc = article.get('image_desc', '')
            if vl_desc and vl_desc != "无视觉分析" and "视觉补充" not in article.get('summary_cn', ''):
                 md_lines.append(f"- **👀 视觉补充**: {vl_desc}")

            # 3. 列出该分类下的所有事件详情
            for evt in events:
                # 构造详细信息行
                info_lines = []
                
                # 如果有特定的项目名称且不等于文章标题，显示项目名
                p_name = evt.get('project_name')
                if p_name and p_name not in ["无", "None", "N/A", "未提及", "无特定项目名称", article['title'], article.get('title_cn')]:
                     info_lines.append(f"🏷️ **项目**: {p_name}")

                # --- 1. 通用字段 ---
                loc = evt.get('location')
                src_country = evt.get('source_country')
                loc_str = ""
                if loc and loc not in ["未提取", "无"]: loc_str = f"{loc}"
                if src_country and src_country not in ["未提取", "无"]:
                    loc_str += f" (源: {src_country})" if loc_str else f"源: {src_country}"
                if loc_str: info_lines.append(f"📍 **地点**: {loc_str}")

                amt = evt.get('contract_value')
                curr = evt.get('currency')
                if amt and amt not in ["未提取", "无", "无具体提及", "未披露"]: 
                    amt_str = f"{amt}"
                    if curr and curr not in ["无", "None"]: amt_str += f" ({curr})"
                    info_lines.append(f"💰 **金额**: {amt_str}")

                # --- 2. 分类特定字段渲染 ---
                if cat_key == 'Market':
                    comp = evt.get('company_name')
                    trend = evt.get('trend')
                    if comp: info_lines.append(f"🏢 **公司**: {comp}")
                    if trend: info_lines.append(f"📈 **趋势**: {trend}")
                    
                elif cat_key == 'Bid':
                    contractor = evt.get('contractor')
                    client = evt.get('client')
                    dur = evt.get('project_duration')
                    if contractor: info_lines.append(f"👷 **承包商**: {contractor}")
                    if client: info_lines.append(f"🏢 **业主**: {client}")
                    if dur: info_lines.append(f"⏱️ **工期**: {dur}")

                elif cat_key == 'Project':
                    status = evt.get('project_status')
                    pct = evt.get('completion_percentage')
                    contractor = evt.get('contractor')
                    if status: info_lines.append(f"📊 **状态**: {status}")
                    if pct: info_lines.append(f"✅ **进度**: {pct}")
                    if contractor: info_lines.append(f"👷 **承包商**: {contractor}")

                elif cat_key == 'VesselDist':
                    vname = evt.get('vessel_name')
                    dest = evt.get('destination')
                    eta = evt.get('eta')
                    if vname: info_lines.append(f"🚢 **船名**: {vname}")
                    if dest: info_lines.append(f"📍 **前往**: {dest}")
                    if eta: info_lines.append(f"🕒 **ETA**: {eta}")

                elif cat_key == 'Equipment':
                    vname = evt.get('vessel_name')
                    vtype = evt.get('vessel_type')
                    yard = evt.get('shipyard')
                    cap = evt.get('capacity')
                    if vname: info_lines.append(f"🚢 **船名**: {vname}")
                    if vtype: info_lines.append(f"🔧 **类型**: {vtype}")
                    if yard: info_lines.append(f"🏭 **船厂**: {yard}")
                    if cap: info_lines.append(f"� **参数**: {cap}")

                elif cat_key == 'R&D':
                    tech = evt.get('technology_name')
                    inst = evt.get('institution')
                    if tech: info_lines.append(f"🔬 **技术**: {tech}")
                    if inst: info_lines.append(f"🏫 **机构**: {inst}")

                elif cat_key == 'Regulation':
                    reg = evt.get('regulation_name')
                    ctry = evt.get('country')
                    eff = evt.get('effective_date')
                    if reg: info_lines.append(f"📜 **法规**: {reg}")
                    if ctry: info_lines.append(f"🌍 **国家**: {ctry}")
                    if eff: info_lines.append(f"📅 **生效**: {eff}")

                # 输出信息行 (作为子列表项)
                if info_lines:
                    md_lines.append("- " + " | ".join(info_lines))
            
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
