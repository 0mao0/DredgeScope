import asyncio
import json
import acquisition.info_acquisition as info_acquisition
import acquisition.wechat_acquisition as wechat_acquisition
import analysis.info_analysis as info_analysis
import reporting.report_generation as report_generation
import config
import os
import time
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from playwright.async_api import async_playwright

import database
from static.constants import JUNK_TITLES_EXACT, JUNK_KEYWORDS_PARTIAL


def is_tracking_param(param_key):
    """判断URL参数是否为追踪参数"""
    if not param_key:
        return False
    key = str(param_key).lower()
    if key.startswith("utm_"):
        return True
    return key in {
        "gclid",
        "fbclid",
        "igshid",
        "mc_cid",
        "mc_eid",
        "mkt_tok",
        "spm",
        "ref",
        "referrer",
        "from",
        "share"
    }

def normalize_article_url(url):
    """规范化文章URL，移除追踪参数和片段"""
    if not url:
        return url
    try:
        parts = urlsplit(url)
        query_params = [
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not is_tracking_param(k)
        ]
        normalized_query = urlencode(query_params, doseq=True)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, normalized_query, ""))
    except Exception:
        return url

def is_valid_article(item):
    """
    第一层粗筛：仅过滤绝对确定的垃圾（如Login页、404页）
    返回 (是否有效, 过滤原因)
    """
    title = item.get('title', '').strip()
    link = item.get('link', '').strip()
    
    # 1. 基础非空检查
    if not title or not link:
        return False, "标题或链接为空"
    
    # 2. 长度检查 (极短的通常是导航)
    if len(title) < 3: 
        return False, "标题太短(可能为导航)"
        
    # 3. 精确匹配绝对垃圾标题
    if title in JUNK_TITLES_EXACT:
        return False, f"命中垃圾标题({title})"
        
    # 4. 包含匹配系统错误信息
    for kw in JUNK_KEYWORDS_PARTIAL:
        if kw.lower() in title.lower():
            return False, f"命中系统错误关键词({kw})"
            
    # 5. 特殊模式检查
    title_lower = title.lower()
    if title_lower.startswith("back to") and len(title) < 20: # 只有短的"Back to..."才是导航
        return False, "导航类链接(Back to)"
    if "javascript" in link.lower():
        return False, "JavaScript伪链接"
        
    return True, "通过粗筛"

def get_scheduler_log_path():
    """获取调度日志文件路径"""
    return os.path.join(config.DATA_DIR, "scheduler.log")

def write_scheduler_log(message):
    """写入调度日志内容"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}\n"
    try:
        with open(get_scheduler_log_path(), "a", encoding="utf-8") as f:
            f.write(log_msg)
    except Exception:
        pass

def load_source_count():
    """读取采集源数量"""
    try:
        with open(config.SOURCES_FILE, "r", encoding="utf-8") as f:
            sources = json.load(f)
        return len(sources)
    except Exception:
        return 0

def format_date(value):
    """格式化日期为YYYY-MM-DD"""
    if not value:
        return ""
    try:
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        text = str(value).strip()
        if "T" in text:
            return text.split("T")[0]
        if " " in text and ":" in text:
            return text.split(" ")[0]
        if len(text) >= 10:
            return text[:10]
        return text
    except Exception:
        return ""

def parse_pub_datetime(value):
    """解析发布时间为 datetime"""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        if "," in text and ":" in text and any(x in text for x in ["GMT", "+", "-"]):
            return parsedate_to_datetime(text)
    except Exception:
        pass
    try:
        if "T" in text:
            return datetime.fromisoformat(text)
        if " " in text and ":" in text:
            return datetime.fromisoformat(text.replace(" ", "T"))
        if len(text) >= 10:
            return datetime.strptime(text[:10], "%Y-%m-%d")
    except Exception:
        return None
    return None

def bool_to_cn(value):
    """布尔值转中文 是/否"""
    return "是" if bool(value) else "否"

def write_markdown_audit(rows):
    """输出调度审核Markdown清单"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    scheduler_dir = os.path.join(config.DATA_DIR, "scheduler")
    os.makedirs(scheduler_dir, exist_ok=True)
    md_path = os.path.join(scheduler_dir, f"{ts}.md")
    header = [
        "| 序号 | 网站 | 新闻名称 | 发布时间 | 是否保留 | TextLLM识别成功 | VL识别成功 | 数据来源 | 备注 | 新闻链接 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    lines = []
    source_map = {
        "rss": "RSS",
        "web": "Web",
        "wechat": "公众号",
        "rsshub": "公众号",
        "official": "公众号"
    }
    for idx, r in enumerate(rows, 1):
        name = (r.get("title_cn") or r.get("title") or "").replace("|", " ").replace("\n", " ").replace("\r", "")
        link = (r.get("link") or "").replace("|", "%7C").replace("\n", "").replace("\r", "")
        site = (r.get("site") or "").replace("|", " ").replace("\n", " ").replace("\r", "")
        date_str = format_date(r.get("pub_date"))
        keep_str = "是" if r.get("keep") else "否"
        txt_ok = bool_to_cn(r.get("text_ok"))
        vl_ok = bool_to_cn(r.get("vl_ok"))
        source_raw = (r.get("source_type") or "").lower()
        source_label = source_map.get(source_raw, "Web")
        # 修复: 彻底清理备注字段中的换行符和管道符，防止Markdown表格错乱
        remark = (r.get("remark") or "").replace("|", " ").replace("\n", " ").replace("\r", " ")
        line = f"| {idx} | {site} | {name} | {date_str} | {keep_str} | {txt_ok} | {vl_ok} | {source_label} | {remark} | {link} |"
        lines.append(line)
    content = "\n".join(header + lines) + "\n"
    try:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(content)
        write_scheduler_log(f"审核清单生成: {os.path.basename(md_path)}")
    except Exception:
        pass

async def main():
    # 初始化数据库
    database.init_db()

    start_time = time.time()
    print(f"=== 疏浚情报极简系统启动 ===")
    print(f"文本模型: {config.TEXT_MODEL}")
    print(f"视觉模型: {config.VL_MODEL}")

    write_scheduler_log("手动/单次运行 main.py 启动")
    sources_count = load_source_count()

    # 1. 获取信息
    t1_start = time.time()
    print(">>> 阶段1: 获取信息...")
    raw_items = await info_acquisition.get_all_items()
    
    # 获取微信公众号文章 (fakeid 列表)
    wechat_biz_list = []
    
    # 从 SOURCES_FILE 加载微信公众号配置
    try:
        with open(config.SOURCES_FILE, "r", encoding="utf-8") as f:
            file_sources = json.load(f)
            for src in file_sources:
                if src.get("type") == "wechat" and src.get("fakeid"):
                    # 避免重复添加 (通过 fakeid 判断)
                    existing_fakeids = [b.get("fakeid") for b in wechat_biz_list]
                    if src.get("fakeid") not in existing_fakeids:
                        wechat_biz_list.append({
                            "name": src.get("name"),
                            "fakeid": src.get("fakeid")
                        })
                        print(f"已加载微信源: {src.get('name')}")
    except Exception as e:
        print(f"加载微信源失败: {e}")
    
    # 微信采集 (自动从 backend/data/wechat_session.json 加载持久化的凭证)
    # 如果 Session 失效，会自动回退到 RSSHub 方案
    wechat_items = wechat_acquisition.wechat_scraper.batch_get_articles(wechat_biz_list, count_per_biz=10)
    if wechat_items:
        print(f"成功获取 {len(wechat_items)} 条微信公众号新闻")
        raw_items.extend(wechat_items)

    print(f"共获取到 {len(raw_items)} 条潜在新闻")
    t1_end = time.time()
    
    # --- 改动：预先规范化所有 URL ---
    # 在入库前进行规范化，确保去重逻辑生效 (避免 http/https, trailing slash, params 导致的重复)
    for item in raw_items:
        normalized_link = normalize_article_url(item.get('link'))
        if normalized_link:
            item['link'] = normalized_link

    # --- 改动：采集阶段立即入库 (不重复) ---
    print(f"正在保存原始数据到数据库...")
    total_scanned, new_ids = database.save_raw_articles(raw_items)
    new_inserted_count = len(new_ids)
    print(f"入库完成: 扫描 {total_scanned} 条, 实际新增 {new_inserted_count} 条")
    
    # 去重 & 状态更新 (更新数据库中的 valid/remark 状态)
    items = [] # 这里的 items 仅用于记录本次处理的有效条目(内存中)，用于后续流程参考(如统计)
               # 实际流程将转向从数据库读取
    
    skipped_count = 0
    duplicate_count = 0
    outdated_count = 0
    processed_count = 0 # 已存在且已处理的数量
    audit_rows = []
    pending_map = {}
    pub_date_map = {}
    seen_links = set()

    for item in raw_items:

        # 基础数据补全
        if not item.get("pub_date") and item.get("date"):
            item["pub_date"] = item.get("date")
        if not item.get("source_name") and item.get("source"):
            item["source_name"] = item.get("source")
        if not item.get("source_type") and item.get("source"):
            item["source_type"] = "wechat"
        normalized_link = normalize_article_url(item.get('link'))
        if normalized_link:
            item['link'] = normalized_link

        # 准备更新到数据库的字段
        db_update = {
            "url": item.get('link'),
            "source_name": item.get("source_name"),
            "source_type": item.get("source_type"),
            "pub_date": item.get("pub_date"),
            # 默认保持 valid=1 (由 save_raw_articles 设置), 除非下面显式改为 0
        }

        # 1. 基础非空检查
        if not item.get("title") or not item.get("link"):
            skipped_count += 1
            audit_rows.append({
                "site": item.get("source_name", ""),
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "pub_date": item.get("pub_date"),
                "source_type": item.get("source_type"),
                "keep": False,
                "remark": "标题或链接为空"
            })
            # 标记为无效
            db_update["valid"] = 0
            db_update["remark"] = "标题或链接为空"
            database.save_article(db_update)
            continue

        # 2. 本次任务内去重
        if item['link'] in seen_links:
            duplicate_count += 1
            audit_rows.append({
                "site": item.get("source_name", ""),
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "pub_date": item.get("pub_date"),
                "source_type": item.get("source_type"),
                "keep": False,
                "remark": "重复链接(任务内)"
            })
            continue
        
        seen_links.add(item['link'])
        pub_date_map[item['link']] = item.get("pub_date")

        # 3. 数据库已存在检查 (避免重复处理已完成的文章)
        # 如果文章已存在且已分析完成（或被废弃），则跳过后续更新
        if database.is_article_processed(item['link']):
            processed_count += 1
            audit_rows.append({
                "site": item.get("source_name", ""),
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "pub_date": item.get("pub_date"),
                "source_type": item.get("source_type"),
                "keep": False, # 这里的 keep 仅用于 audit 表格显示，实际状态在库里
                "remark": "已存在且已处理"
            })
            continue

        # 4. 处理采集阶段过滤的条目（入库但标记为无效）
        if item.get("filtered_reason"):
            item["valid"] = 0
            item["is_hidden"] = 1
            item["remark"] = f"采集阶段过滤: {item.get('filtered_reason')}"
            
            db_update["valid"] = 0
            db_update["is_hidden"] = 1
            db_update["remark"] = item["remark"]
            database.save_article(db_update)
            
            audit_rows.append({
                "site": item.get("source_name", ""),
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "pub_date": item.get("pub_date"),
                "source_type": item.get("source_type"),
                "keep": False,
                "remark": item["remark"]
            })
            continue

        # 5. 发布时间拦截（5天）
        pub_dt = parse_pub_datetime(item.get("pub_date"))
        
        # 对于Web/Official源，如果缺少时间，允许通过（等待后续enrich补充）
        # 对于RSS/WeChat，通常已有时间，若缺则直接丢弃
        allow_missing_date = item.get("source_type") in ["web", "official", "rsshub"]
        
        if not pub_dt:
            if not allow_missing_date:
                outdated_count += 1
                db_update["valid"] = 0
                db_update["remark"] = "发布时间缺失"
                database.save_article(db_update)
                
                audit_rows.append({
                    "site": item.get("source_name", ""),
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "pub_date": item.get("pub_date"),
                    "source_type": item.get("source_type"),
                    "keep": False,
                    "remark": "发布时间缺失"
                })
                continue
            # else: pass through, valid remains 1 (default)
        elif datetime.now() - pub_dt > timedelta(days=5):
            outdated_count += 1
            db_update["valid"] = 0
            db_update["remark"] = "发布时间早于5天(已入库)"
            database.save_article(db_update)
            
            audit_rows.append({
                "site": item.get("source_name", ""),
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "pub_date": item.get("pub_date"),
                "source_type": item.get("source_type"),
                "keep": False,
                "remark": "发布时间早于5天(已入库)"
            })
            continue

        # 有效条目，确保数据库更新（主要是 source_name/type/pub_date 可能有变化）
        # 并且确保 valid=1 (虽然默认是1，但显式更新更好)
        db_update["valid"] = 1
        # 清空可能的旧 remark (如之前被标为无效) -> 暂时不清除，保留历史 remark 也许更好？
        # 不，如果是新的一轮采集发现有效，应该清除旧的错误 remark
        # 但 save_article 使用 COALESCE(NULLIF(?, ''), remark)，传入 '' 会被 NULLIF 变 NULL，然后保持原值
        # 所以无法清除 remark。除非修改 save_article 或传入特殊值。
        # 暂时忽略清除 remark 的需求。
        database.save_article(db_update)

        # 加入 audit 待分析
        audit_rows.append({
            "site": item.get("source_name", ""),
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "pub_date": item.get("pub_date"),
            "source_type": item.get("source_type"),
            "keep": False,
            "remark": "待分析"
        })
        pending_map[item['link']] = len(audit_rows) - 1
    
    print(f"过滤掉 {skipped_count} 条垃圾/无效信息")
    print(f"跳过 {processed_count} 条已处理信息")
    print(f"超期入库 {outdated_count} 条")
    write_scheduler_log(
        f"采集统计: 源站点{sources_count} 潜在消息{len(raw_items)} 新增入库{new_inserted_count} 跳过已处理{processed_count} 过滤无效{skipped_count} 超期入库{outdated_count}"
    )

    # --- 改动：从数据库获取需要补充采集的条目 ---
    t2_start = time.time()
    # 逻辑：valid=1 且 (无内容 或 无截图) 且 5天内
    # 仅处理本次新增的条目，避免重复处理旧数据
    items_to_enrich = database.get_items_for_enrichment(ids=new_ids)
    
    if items_to_enrich:
        print(f"正在对 {len(items_to_enrich)} 条条目进行补充采集(从数据库读取)...")
        try:
            async with async_playwright() as p:
                browser = await info_acquisition.launch_chromium(p)
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    locale="zh-CN",
                    ignore_https_errors=True
                )
                await info_acquisition.enrich_web_items(context, items_to_enrich)
                await browser.close()
                
                # 补充采集后，更新回数据库，并再次检查时间
                for item in items_to_enrich:
                    # 检查时间：如果之前没时间，现在有了，需要检查是否过期
                    # 注意：enrich_web_items 会修改 item["pub_date"]
                    pub_dt = parse_pub_datetime(item.get("pub_date"))
                    
                    # 再次检查：如果没有时间，不再自动补充为当前时间！(响应用户需求)
                    if not pub_dt:
                        # 仍然无时间，标记为无效
                        item["valid"] = 0
                        item["remark"] = (item.get("remark") or "") + " (补充采集仍无时间)"
                    elif datetime.now() - pub_dt > timedelta(days=5):
                        item["valid"] = 0
                        item["remark"] = "补充采集后判定过期"
                    
                    # 保存更新 (content, screenshot, pub_date, valid, remark)
                    database.save_article(item)
                    
        except Exception as e:
            print(f"补充采集失败: {e}")
    t2_end = time.time()

    # --- 改动：从数据库获取需要分析的条目 ---
    # 逻辑：valid=1 且 有内容 且 尚未分析(summary_cn为空)
    # 注意：上面的补充采集可能把一些 valid=1 变成了 valid=0，所以这里只会取 valid=1 的
    
    # 这里的 items 变量不再使用，全靠数据库
    # database.save_raw_articles(items) # 已移除，前面已保存

    # 2. 分析信息 (文本 + 视觉)
    t3_start = time.time()
    print(">>> 阶段2: 智能分析(从数据库读取)...")
    
    # 仅分析本次新增的条目
    analysis_items = database.get_items_for_analysis(ids=new_ids)
    
    if analysis_items:

        print(f"读取到 {len(analysis_items)} 条待分析文章")
        results = await info_analysis.process_items_from_db(analysis_items)
    else:
        print("无有效文章需分析。")
        results = []
        
    t3_end = time.time()
    
    # --- 统计分析结果 ---
    llm_success = 0
    llm_failed = 0
    vlm_success = 0
    vlm_failed = 0
    junk_count = 0
    kept_count = 0
    
    if results:
        for r in results:
            if isinstance(r, dict):
                # LLM/Text 分析情况
                if r.get("full_text_cn") or r.get("summary_cn"):
                    llm_success += 1
                else:
                    llm_failed += 1
                
                # VLM 分析情况 (如果有截图)
                if r.get("screenshot_path"):
                    if r.get("image_desc"):
                        vlm_success += 1
                    else:
                        vlm_failed += 1
                
                # 有效性
                if r.get("is_junk"):
                    junk_count += 1
                else:
                    kept_count += 1

    cutoff_dt = datetime.now() - timedelta(days=5)
    kept_results = []
    for r in results or []:
        link_key = r.get("url") if isinstance(r, dict) else None
        if isinstance(r, dict):
            original_pub = parse_pub_datetime(pub_date_map.get(link_key)) if link_key else None
            if not original_pub or original_pub < cutoff_dt:
                if link_key and link_key in pending_map:
                    idx = pending_map[link_key]
                    audit_rows[idx]["remark"] = "发布时间早于5天"
                
                # 同步更新数据库状态
                if r.get("is_retained", 0) == 1:
                    r["is_retained"] = 0
                    r["remark"] = "发布时间早于5天"
                    database.save_article(r)
                
                continue
            # 优先使用分析结果中的时间，如果没有则回退到 map
            if not r.get("pub_date") and link_key in pub_date_map:
                r["pub_date"] = pub_date_map.get(link_key)
            
            kept_results.append(r)
        
        if link_key and link_key in pending_map:
            idx = pending_map[link_key]
            # 使用 is_retained 作为最终判定标准，与数据库保持一致
            is_retained = r.get("is_retained", 0)
            
            if is_retained == 1:
                audit_rows[idx]["keep"] = True
                audit_rows[idx]["title_cn"] = r.get("title_cn") or audit_rows[idx].get("title")
                audit_rows[idx]["text_ok"] = bool(r.get("title_cn") or r.get("summary_cn") or r.get("full_text_cn"))
                audit_rows[idx]["vl_ok"] = bool(r.get("screenshot_path"))
                audit_rows[idx]["remark"] = "保留"
            else:
                if r.get("is_junk"):
                     audit_rows[idx]["remark"] = f"AI判定无关: {r.get('junk_reason', '非疏浚主题')}"
                elif not r.get("valid", 1):
                     audit_rows[idx]["remark"] = "无效数据 (valid=0)"
                else:
                     audit_rows[idx]["remark"] = "未保留 (is_retained=0)"
    
    for link_key, idx in pending_map.items():
        if audit_rows[idx]["remark"] == "待分析":
            audit_rows[idx]["remark"] = "分析未通过(可能提取失败)"

    # 3. 存储
    print(">>> 阶段3: 结果已同步至数据库")
    # report_generation.save_history(kept_results) # 移除：info_analysis 已实时保存
    try:
        write_markdown_audit(audit_rows)
    except Exception:
        pass
    write_scheduler_log(f"分析完成: 文章{len(kept_results)}")
    
    end_time = time.time()
    
    # --- 生成最终分析报告 ---
    total_time = end_time - start_time
    time_info = t1_end - t1_start
    time_enrich = t2_end - t2_start
    time_analysis = t3_end - t3_start
    
    pct_info = (time_info / total_time * 100) if total_time > 0 else 0
    pct_enrich = (time_enrich / total_time * 100) if total_time > 0 else 0
    pct_analysis = (time_analysis / total_time * 100) if total_time > 0 else 0

    log_content = []
    log_content.append("\n" + "="*50)
    log_content.append("               任务分析报告")
    log_content.append("="*50)
    log_content.append("(1) 总体统计分析")
    log_content.append(f"{'指标':<10}{'数量':<8}{'说明'}")
    log_content.append(f"{'扫描链接':<10}{len(raw_items):<8}扫描到的所有潜在链接")
    log_content.append(f"{'新增入库':<10}{new_inserted_count:<8}本次实际新增的文章数")
    log_content.append(f"{'跳过处理':<10}{processed_count:<8}数据库已存在且分析完成的文章")
    log_content.append(f"{'有效分析':<10}{len(analysis_items):<8}经过筛选、发布在5天内且内容完整的文章")
    log_content.append(f"{'最终保留':<10}{kept_count:<8}经过 AI 分析后判定为“相关”的文章")
    log_content.append(f"{'判定无关':<10}{junk_count:<8}被 AI 判定为垃圾/无关的文章")
    
    total_llm = llm_success + llm_failed
    llm_rate = (llm_success / total_llm * 100) if total_llm > 0 else 0
    
    total_vlm = vlm_success + vlm_failed
    vlm_rate = (vlm_success / total_vlm * 100) if total_vlm > 0 else 0
    
    log_content.append(f"{'LLM (文本)':<10}成功 {llm_success:<5}成功生成摘要/翻译 (成功率 {llm_rate:.0f}%)")
    log_content.append(f"{'VLM (视觉)':<10}成功 {vlm_success:<5}成功生成图片描述 (成功率 {vlm_rate:.0f}%)")
    
    log_content.append("\n(2) 耗时统计")
    log_content.append(f"总耗时 : {total_time:.2f} 秒 (约 {total_time/60:.1f} 分钟)")
    log_content.append(f"{'环节':<10}{'耗时':<12}{'占比':<8}{'备注'}")
    log_content.append(f"{'信息获取':<10}{time_info:.2f} 秒    {pct_info:.0f}%     扫描 RSS 和网页列表页")
    log_content.append(f"{'补充采集':<10}{time_enrich:.2f} 秒    {pct_enrich:.0f}%     最耗时。使用 Playwright 逐个打开网页抓取正文和截图")
    log_content.append(f"{'智能分析':<10}{time_analysis:.2f} 秒    {pct_analysis:.0f}%      调用大模型进行分析")
    log_content.append("="*50 + "\n")
    
    final_log = "\n".join(log_content)
    print(final_log)
    write_scheduler_log(final_log)

if __name__ == "__main__":
    import time  # Ensure time is available if not imported globally
    asyncio.run(main())
