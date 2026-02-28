import asyncio
import json
import acquisition.info_acquisition as info_acquisition
import acquisition.wechat_acquisition as wechat_acquisition
import analysis.info_analysis as info_analysis
import reporting.report_generation as report_generation
import config
import os
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

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
    return os.path.join(os.path.dirname(__file__), "scheduler", "scheduler.log")

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

def bool_to_cn(value):
    """布尔值转中文 是/否"""
    return "是" if bool(value) else "否"

def write_markdown_audit(rows):
    """输出调度审核Markdown清单"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = os.path.join(os.path.dirname(__file__), "scheduler", f"{ts}.md")
    header = [
        "| 序号 | 网站 | 新闻名称 | 发布时间 | 是否保留 | TextLLM识别成功 | VL识别成功 | 备注 | 新闻链接 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    lines = []
    for idx, r in enumerate(rows, 1):
        name = (r.get("title_cn") or r.get("title") or "").replace("|", " ")
        link = r.get("link") or ""
        site = r.get("site") or ""
        date_str = format_date(r.get("pub_date"))
        keep_str = "是" if r.get("keep") else "否"
        txt_ok = bool_to_cn(r.get("text_ok"))
        vl_ok = bool_to_cn(r.get("vl_ok"))
        remark = r.get("remark") or ""
        # 将链接放到最后，方便阅读
        line = f"| {idx} | {site} | {name} | {date_str} | {keep_str} | {txt_ok} | {vl_ok} | {remark} | {link} |"
        lines.append(line)
    content = "\n".join(header + lines) + "\n"
    try:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(content)
        write_scheduler_log(f"审核清单生成: {os.path.basename(md_path)}")
    except Exception:
        pass

async def main():
    print(f"=== 疏浚情报极简系统启动 ===")
    print(f"文本模型: {config.TEXT_MODEL}")
    print(f"视觉模型: {config.VL_MODEL}")

    write_scheduler_log("手动/单次运行 main.py 启动")
    sources_count = load_source_count()

    # 1. 获取信息
    print(">>> 阶段1: 获取信息...")
    raw_items = await info_acquisition.get_all_items()
    
    # 获取微信公众号文章 (fakeid 列表)
    wechat_biz_list = [
        {"name": "中交疏浚", "fakeid": "MzI1NzYwNTQ5Ng=="},
        {"name": "中交天航局", "fakeid": "MzA5NTU2NTYyNQ=="},
        {"name": "中交广航局", "fakeid": "MjM5MjM5NTAyMA=="},
        {"name": "中交上航局", "fakeid": "MzA3NjA5OTU5Mg=="}
    ]
    
    # 微信采集 (自动从 backend/data/wechat_session.json 加载持久化的凭证)
    # 如果 Session 失效，会自动回退到 RSSHub 方案
    wechat_items = wechat_acquisition.wechat_scraper.batch_get_articles(wechat_biz_list, count_per_biz=3)
    if wechat_items:
        print(f"成功获取 {len(wechat_items)} 条微信公众号新闻")
        raw_items.extend(wechat_items)

    print(f"共获取到 {len(raw_items)} 条潜在新闻")
    
    # 去重 & 质量过滤
    items = []
    skipped_count = 0
    duplicate_count = 0
    audit_rows = []
    pending_map = {}
    seen_links = set()
    
    for item in raw_items:
        normalized_link = normalize_article_url(item.get('link'))
        if normalized_link:
            item['link'] = normalized_link
            
        # 1. 质量过滤
        valid, reason = is_valid_article(item)
        if not valid:
            skipped_count += 1
            audit_rows.append({
                "site": item.get("source_name", ""),
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "pub_date": item.get("pub_date"),
                "keep": False,
                "text_ok": False,
                "vl_ok": False,
                "remark": reason
            })
            continue
            
        # 2. 本次任务内去重 & 数据库去重
        if item['link'] in seen_links:
            duplicate_count += 1
            audit_rows.append({
                "site": item.get("source_name", ""),
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "pub_date": item.get("pub_date"),
                "keep": False,
                "text_ok": False,
                "vl_ok": False,
                "remark": "重复链接(任务内)"
            })
            continue
        
        if database.is_article_exists(item['link']):
            duplicate_count += 1
            audit_rows.append({
                "site": item.get("source_name", ""),
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "pub_date": item.get("pub_date"),
                "keep": False,
                "text_ok": False,
                "vl_ok": False,
                "remark": "库中已存在"
            })
            continue
        
        seen_links.add(item['link'])
        
        # 3. 标记为待分析
        items.append(item)
        audit_rows.append({
            "site": item.get("source_name", ""),
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "pub_date": item.get("pub_date"),
            "keep": False,
            "text_ok": False,
            "vl_ok": False,
            "remark": "待分析"
        })
        pending_map[item['link']] = len(audit_rows) - 1
    
    print(f"过滤掉 {skipped_count} 条垃圾/无效信息")
    print(f"经去重后，剩余 {len(items)} 条新文章需处理")
    write_scheduler_log(
        f"采集统计: 源站点{sources_count} 潜在消息{len(raw_items)} 过滤无效{skipped_count} 去重过滤{duplicate_count} 入库候选{len(items)}"
    )

    if not items:
        print("无新文章，任务结束。")
        try:
            write_markdown_audit(audit_rows)
        except Exception:
            pass
        write_scheduler_log("采集完成: 无新文章入库")
        return

    # 2. 分析信息 (文本 + 视觉)
    print(">>> 阶段2: 智能分析...")
    results = await info_analysis.process_items(items)
    total_events = 0
    for r in results or []:
        events = r.get("events") if isinstance(r, dict) else None
        if events:
            total_events += len(events)
        link_key = r.get("url") if isinstance(r, dict) else None
        if link_key and link_key in pending_map:
            idx = pending_map[link_key]
            is_junk = r.get("is_junk", False)
            if not is_junk:
                audit_rows[idx]["keep"] = True
                audit_rows[idx]["title_cn"] = r.get("title_cn") or audit_rows[idx].get("title")
                audit_rows[idx]["text_ok"] = bool(r.get("title_cn") or r.get("summary_cn") or r.get("full_text_cn"))
                audit_rows[idx]["vl_ok"] = bool(r.get("screenshot_path"))
                audit_rows[idx]["remark"] = "保留"
            else:
                audit_rows[idx]["remark"] = f"AI判定无关: {r.get('junk_reason', '非疏浚主题')}"
    
    for link_key, idx in pending_map.items():
        if audit_rows[idx]["remark"] == "待分析":
            audit_rows[idx]["remark"] = "分析未通过(可能提取失败)"

    # 3. 生成报告 & 存储
    print(">>> 阶段3: 生成报告...")
    report_generation.save_history(results)
    report_generation.generate_report(results)
    try:
        write_markdown_audit(audit_rows)
    except Exception:
        pass
    write_scheduler_log(f"分析完成: 文章{len(results)} 事件{total_events}")
    

if __name__ == "__main__":
    asyncio.run(main())
