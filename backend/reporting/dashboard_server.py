from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
import os
import sys
import sqlite3
import json
from datetime import datetime, timedelta
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database
import config

app = FastAPI()

# Mount assets
app.mount("/assets", StaticFiles(directory=config.ASSETS_DIR), name="assets")

# Mount static (for map data etc)
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open(os.path.join(config.TEMPLATES_DIR, "dashboard.html"), "r", encoding="utf-8") as f:
        return f.read()

@app.get("/vessel_map.html", response_class=HTMLResponse)
async def vessel_map():
    with open(os.path.join(config.TEMPLATES_DIR, "vessel_map.html"), "r", encoding="utf-8") as f:
        return f.read()

@app.get("/history.html", response_class=HTMLResponse)
async def history_page():
    with open(os.path.join(config.TEMPLATES_DIR, "history.html"), "r", encoding="utf-8") as f:
        return f.read()

@app.get("/statistics.html", response_class=HTMLResponse)
async def statistics_page():
    with open(os.path.join(config.TEMPLATES_DIR, "statistics.html"), "r", encoding="utf-8") as f:
        return f.read()

import traceback

@app.get("/api/events")
async def get_events(
    date: str = Query(None, description="Date in YYYY-MM-DD"),
    mode: str = Query(None, description="Mode: 'recent' for last 24h"),
    start: str = Query(None, description="Start datetime ISO"),
    end: str = Query(None, description="End datetime ISO")
):
    """获取事件，支持按日期、最近24小时或自定义时间范围"""
    try:
        def parse_event_datetime(value):
            if not value:
                return None, False
            text = str(value).strip()
            if not text:
                return None, False
            try:
                if "T" in text:
                    return datetime.fromisoformat(text), False
                if " " in text and ":" in text:
                    return datetime.fromisoformat(text.replace(" ", "T")), False
                return datetime.strptime(text, "%Y-%m-%d"), True
            except Exception:
                return None, False

        if mode == 'recent':
            now = datetime.now()
            hour = now.hour
            label_prefix = f"{now.month}月{now.day}日"
            if hour <= 8:
                start_dt = (now - timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
                end_dt = now.replace(hour=8, minute=0, second=0, microsecond=0)
                date_label = f"{label_prefix}早报"
            else:
                # User feedback: 晚报 (日报) should be today 08:00 - 18:00
                start_dt = now.replace(hour=8, minute=0, second=0, microsecond=0)
                end_dt = now.replace(hour=18, minute=0, second=0, microsecond=0)
                date_label = f"{label_prefix}晚报"
            start_time = start_dt.isoformat()
            end_time = end_dt.isoformat()
        elif start and end:
            start_time = start
            end_time = end
            date_label = f"{start[:10]} ~ {end[:10]}"
        else:
            if not date:
                date = datetime.now().strftime("%Y-%m-%d")
                start_time = f"{date}T00:00:00"
                end_time = f"{date}T23:59:59"
                date_label = date
            else:
                start_time = f"{date}T00:00:00"
                end_time = f"{date}T23:59:59"
                date_label = date
        
        events = database.get_events_by_time_range(start_time, end_time)
        
        # --- Stale News Filter (Added to fix "Old News" issue) ---
        # 无论何种模式，都过滤掉 "发现时已严重过时" 的新闻 (比如今天抓取到了 2024 年的新闻)
        # 阈值设为 90 天 (3个月)
        STALE_THRESHOLD_DAYS = 30
        fresh_events = []
        for e in events:
            try:
                # 1. 获取 created_at (抓取/入库时间)
                c_date_str = e.get('created_at')
                if not c_date_str:
                    fresh_events.append(e)
                    continue
                if 'T' in str(c_date_str):
                    c_date = datetime.fromisoformat(str(c_date_str))
                else:
                    c_date = datetime.fromisoformat(str(c_date_str).replace(' ', 'T'))

                # 2. 获取 pub_date (发布时间)
                p_date_str = e.get('pub_date')
                if not p_date_str:
                    fresh_events.append(e)
                    continue
                
                # 清洗 pub_date
                p_date_clean = str(p_date_str).strip()
                p_date = None
                
                # 尝试解析多种格式
                if 'T' in p_date_clean:
                    p_date = datetime.fromisoformat(p_date_clean)
                elif ' ' in p_date_clean and ':' in p_date_clean:
                    p_date = datetime.fromisoformat(p_date_clean.replace(' ', 'T'))
                else:
                    # 尝试 YYYY-MM-DD
                    try:
                        p_date = datetime.strptime(p_date_clean, "%Y-%m-%d")
                    except:
                        pass
                
                if p_date:
                    # 计算 "陈旧度": 抓取时间 - 发布时间
                    # 注意：如果 p_date 没有时区信息而 c_date 有，或者反之，直接相减可能报错
                    # 简单起见，比较 date() 部分
                    age_days = (c_date.date() - p_date.date()).days
                    if age_days > STALE_THRESHOLD_DAYS:
                        # 这是一个 "迟到的旧新闻"，过滤掉
                        continue
                
                fresh_events.append(e)
            except Exception as ex:
                # 解析出错则保留 (Safe fallback)
                fresh_events.append(e)
        
        events = fresh_events
        
        # Format dates for frontend display (remove microseconds)
        for e in events:
            if e.get('created_at'):
                e['created_at'] = str(e['created_at']).split('.')[0]
            if e.get('pub_date'):
                e['pub_date'] = str(e['pub_date']).split('.')[0]
                
        # -------------------------------------------------------

        # Filter by pub_date if in recent mode (User request: "How am I seeing 2023 news?")
        if mode == 'recent':
            filtered_events = []
            for e in events:
                pub_dt, date_only = parse_event_datetime(e.get('pub_date'))
                if not pub_dt:
                    pub_dt, date_only = parse_event_datetime(e.get('created_at'))
                if not pub_dt:
                    continue
                if date_only:
                    if pub_dt.date() < start_dt.date() or pub_dt.date() > end_dt.date():
                        continue
                else:
                    if pub_dt < start_dt or pub_dt > end_dt:
                        continue
                filtered_events.append(e)
            events = filtered_events

        def normalize_title(text):
            if not text:
                return ""
            t = str(text).lower()
            stopwords = [
                "集团", "公司", "股份", "有限", "有限公司",
                "达成", "签订", "签署", "修改", "修订", "协议",
                "合作", "宣布", "公告"
            ]
            for w in stopwords:
                t = t.replace(w, "")
            t = "".join(ch for ch in t if ch.isalnum() or '\u4e00' <= ch <= '\u9fff')
            return t

        deduped_events = []
        seen_market = set()
        for e in events:
            if e.get("category") == "Market":
                title_key = normalize_title(e.get("title_cn") or e.get("article_title") or e.get("summary_cn"))
                if not title_key:
                    title_key = e.get("article_url") or e.get("article_id")
                if title_key and title_key in seen_market:
                    continue
                if title_key:
                    seen_market.add(title_key)
            deduped_events.append(e)
        events = deduped_events

        article_ids = {e.get("article_id") for e in events if e.get("article_id") is not None}
        article_count = len(article_ids)
        # 转换为前端友好的格式
        return {
            "date": date_label,
            "count": article_count,
            "article_count": article_count,
            "event_count": len(events),
            "events": events
        }
    except Exception as e:
        print(f"Error getting events: {e}")
        traceback.print_exc()
        return {
            "date": date if date else datetime.now().strftime("%Y-%m-%d"),
            "count": 0,
            "events": []
        }

@app.get("/api/stats")
async def get_stats(days: int = 7):
    """获取最近 N 天的统计数据"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # 每天的数据
    daily_stats = []
    
    conn = sqlite3.connect(database.DB_PATH)
    c = conn.cursor()
    
    # 按天统计
    query = '''
        SELECT date(e.created_at) as d, count(DISTINCT e.article_id) as c
        FROM events e
        JOIN articles a ON e.article_id = a.id
        WHERE e.created_at >= ? 
          AND (a.is_hidden = 0 OR a.is_hidden IS NULL)
          AND (a.valid = 1 OR a.valid IS NULL)
        GROUP BY date(e.created_at)
        ORDER BY d ASC
    '''
    c.execute(query, (start_date.isoformat(),))
    rows = c.fetchall()
    
    # Get total historical count
    c.execute("SELECT count(*) FROM articles a WHERE (a.is_hidden = 0 OR a.is_hidden IS NULL) AND (a.valid = 1 OR a.valid IS NULL)")
    total_count = c.fetchone()[0]
    
    conn.close()
    
    return {
        "stats": [{"date": r[0], "count": r[1]} for r in rows],
        "total_history": total_count
    }

CATEGORY_CN_MAP = {
    "Bid": "中标信息",
    "Equipment": "装备动态",
    "Market": "市场情报",
    "Project": "项目进展",
    "Regulation": "政策法规",
    "R&D": "科技研发",
    "Unknown": "未知",
    "None": "未知"
}

@app.get("/api/statistics")
async def get_statistics(
    start: str = Query(None, description="Start date YYYY-MM-DD"),
    end: str = Query(None, description="End date YYYY-MM-DD")
):
    if not start:
        start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not end:
        end = datetime.now().strftime("%Y-%m-%d")
        
    start_time = f"{start}T00:00:00"
    end_time = f"{end}T23:59:59"
    
    events = database.get_events_by_time_range(start_time, end_time)
    
    # 1. Category Pie Chart
    # Use enriched category
    categories = []
    for e in events:
        cat = e.get('category')
        if not cat or cat == 'None':
            cat = 'Unknown'
        categories.append(cat)
        
    cat_counts = Counter(categories)
    # Convert keys to Chinese for display
    pie_labels = [CATEGORY_CN_MAP.get(k, k) for k in cat_counts.keys()]
    pie_values = list(cat_counts.values())
    
    # 2. Trend Line Chart (Category over time)
    trend_data = defaultdict(lambda: defaultdict(int))
    all_dates = set()
    
    for e in events:
        # Use pub_date if available, else created_at
        d_str = e.get('pub_date') or e.get('created_at')
        if not d_str: continue
        try:
            # Handle potential ISO format with T or space
            clean_date = str(d_str).replace('T', ' ').split('.')[0]
            d_obj = datetime.strptime(clean_date[:10], "%Y-%m-%d")
            date_key = d_obj.strftime("%Y-%m-%d")
            
            cat = e.get('category')
            if not cat or cat == 'None': cat = 'Unknown'
            
            trend_data[cat][date_key] += 1
            all_dates.add(date_key)
        except Exception as ex:
            # print(f"Date parse error: {d_str} {ex}")
            continue
            
    sorted_dates = sorted(list(all_dates))
    sorted_categories = sorted(list(cat_counts.keys()))
    # Map sorted categories to Chinese for the frontend legend
    sorted_categories_cn = [CATEGORY_CN_MAP.get(k, k) for k in sorted_categories]
    
    # Convert defaultdict to regular dict for JSON serialization
    # Structure: { "Bid": {"2024-01-01": 10, ...}, ... }
    # We need to send data that matches sorted_categories
    trend_datasets = []
    for cat in sorted_categories:
        data_points = []
        for d in sorted_dates:
            data_points.append(trend_data[cat][d])
        trend_datasets.append({
            "label": CATEGORY_CN_MAP.get(cat, cat),
            "data": data_points
        })
    
    # 3. Source Bar Chart
    sources = []
    for e in events:
        s = e.get('source_name')
        if not s or s == 'None':
            # Fallback to source_type if name missing
            s = e.get('source_type', 'Unknown')
        sources.append(s)
        
    source_counts = Counter(sources)
    # Sort by count desc
    sorted_sources = source_counts.most_common(20) # Top 20
    bar_labels = [s[0] for s in sorted_sources]
    bar_values = [s[1] for s in sorted_sources]
    
    return {
        "category_stats": {
            "labels": pie_labels,
            "values": pie_values
        },
        "trend_stats": {
            "categories": sorted_categories_cn, # Use Chinese names
            "dates": sorted_dates,
            "datasets": trend_datasets # Pre-formatted datasets
        },
        "source_stats": {
            "labels": bar_labels,
            "values": bar_values
        }
    }

@app.get("/api/ship_tracks")
async def get_ship_tracks(mmsi: str, days: int = 3):
    """获取指定船舶的历史轨迹 (默认3天)"""
    tracks = database.get_ship_tracks(mmsi, days=days)
    return tracks

@app.get("/api/ships")
async def get_ships():
    """获取所有船舶位置和状态 (返回所有船舶，tracked 为 24 小时内活跃数)"""
    ships = database.get_all_ships()
    total_count = len(ships)
    # 修正 tracked 逻辑：仅统计有 MMSI 的船舶 (即被监控的船舶)
    tracked_count = 0
    active_count = 0
    all_ships = []
    
    # 定义“活跃”阈值：24 小时
    now = datetime.now()
    threshold = now - timedelta(hours=24)
    
    for ship in ships:
        mmsi = str(ship.get('mmsi', '')).strip()
        if mmsi:
            tracked_count += 1
            
        # 1. 标记是否活跃
        is_active = False
        updated_at_str = ship.get('updated_at')
        if updated_at_str:
            try:
                updated_at = datetime.fromisoformat(updated_at_str)
                if updated_at >= threshold:
                    is_active = True
            except:
                pass
        
        if is_active:
            active_count += 1
            
        # 2. 处理位置坐标
        lat = None
        lng = None
        if ship.get('location') and ',' in str(ship.get('location')):
            try:
                lat_str, lng_str = str(ship['location']).split(',')
                lat_val = float(lat_str.strip())
                lng_val = float(lng_str.strip())
                
                # 过滤掉 0, 0 坐标
                if abs(lat_val) > 0.01 or abs(lng_val) > 0.01:
                    lat = lat_val
                    lng = lng_val
            except:
                pass
        
        ship['lat'] = lat
        ship['lng'] = lng
        ship['is_active'] = is_active
        
        all_ships.append(ship)
                
    visible_count = sum(1 for s in all_ships if s.get('lat') is not None)
    
    return {
        "ships": all_ships, 
        "total": total_count, 
        "tracked": tracked_count, 
        "active": active_count,
        "visible": visible_count,
        "note": "tracked=MMSI configured count, active=updated < 24h"
    }

@app.get("/api/articles")
async def get_articles(
    date: str = Query(None, description="Date in YYYY-MM-DD"),
    start: str = Query(None, description="Start datetime ISO"),
    end: str = Query(None, description="End datetime ISO"),
    keyword: str = Query(None, description="Keyword search"),
    category: str = Query(None, description="Event category"),
    source_type: str = Query(None, description="Source type"),
    source_name: str = Query(None, description="Source name"),
    valid: int = Query(None, description="Validity filter (1 for valid, 0 for invalid)"),
    page: int = Query(1, description="Page number"),
    page_size: int = Query(50, description="Page size")
):
    conn = sqlite3.connect(database.DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    join_sql = "LEFT JOIN events e ON e.article_id = a.id"
    where = [
        "(a.is_hidden = 0 OR a.is_hidden IS NULL)"
    ]
    params = []

    if valid is not None:
        where.append("a.valid = ?")
        params.append(valid)
    else:
        # Default behavior: show valid articles if not specified
        # But for History page, we might want to see everything or respect the default
        # Actually, the user asked for a filter, so we should allow showing everything if valid is None
        # But usually we want to exclude junk by default unless explicitly asked.
        # Let's stick to the filter logic.
        pass

    if category:
        join_sql = "JOIN events e ON e.article_id = a.id"
        where.append("e.category = ?")
        params.append(category)

    if date:
        where.append("date(substr(a.created_at, 1, 10)) = date(?)")
        params.append(date)
    elif start and end:
        where.append("date(substr(a.created_at, 1, 10)) BETWEEN date(?) AND date(?)")
        params.extend([start, end])

    if keyword:
        like = f"%{keyword}%"
        where.append("(a.title LIKE ? OR a.title_cn LIKE ? OR a.summary_cn LIKE ?)")
        params.extend([like, like, like])

    if source_type:
        where.append("a.source_type = ?")
        params.append(source_type)

    if source_name:
        where.append("a.source_name = ?")
        params.append(source_name)

    where_sql = " AND ".join(where) if where else "1=1"
    count_query = f"""
        SELECT COUNT(DISTINCT a.id)
        FROM articles a
        {join_sql}
        WHERE {where_sql}
    """
    c.execute(count_query, params)
    total = c.fetchone()[0] or 0

    offset = max(page - 1, 0) * page_size
    data_query = f"""
        SELECT 
            a.id, a.title, a.title_cn, a.pub_date, a.source_type, a.source_name,
            a.summary_cn, a.full_text_cn, a.content, a.screenshot_path, a.url, a.created_at,
            a.valid,
            GROUP_CONCAT(DISTINCT e.category) as categories
        FROM articles a
        {join_sql}
        WHERE {where_sql}
        GROUP BY a.id
        ORDER BY a.created_at DESC, a.pub_date DESC
        LIMIT ? OFFSET ?
    """
    c.execute(data_query, params + [page_size, offset])
    rows = c.fetchall()
    conn.close()

    items = []
    for row in rows:
        item = dict(row)
        
        # Format dates
        if item.get('created_at'):
             item['created_at'] = str(item['created_at']).split('.')[0]
        if item.get('pub_date'):
             item['pub_date'] = str(item['pub_date']).split('.')[0]
             
        cats = item.get("categories") or ""
        item["categories"] = [c for c in cats.split(",") if c] if cats else []
        items.append(item)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items
    }

@app.get("/api/article/{article_id}")
async def get_article_detail(article_id: int):
    conn = sqlite3.connect(database.DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT id, title, title_cn, url, pub_date, summary_cn, full_text_cn, content, source_type, source_name, screenshot_path, vl_desc, created_at, valid
        FROM articles
        WHERE id = ?
    """, (article_id,))
    article_row = c.fetchone()
    if not article_row:
        conn.close()
        return {"article": None, "events": []}

    c.execute("""
        SELECT e.*, a.title as article_title, a.title_cn, a.url as article_url, a.screenshot_path, a.summary_cn, a.full_text_cn, a.content, a.vl_desc, a.pub_date, a.source_type, a.source_name, e.details_json
        FROM events e
        JOIN articles a ON e.article_id = a.id
        WHERE e.article_id = ?
        ORDER BY e.created_at DESC
    """, (article_id,))
    rows = c.fetchall()
    conn.close()

    article_data = dict(article_row)
    if article_data.get('created_at'):
        article_data['created_at'] = str(article_data['created_at']).split('.')[0]
    if article_data.get('pub_date'):
        article_data['pub_date'] = str(article_data['pub_date']).split('.')[0]

    events = []
    categories = set()
    seen_signatures = set()
    for row in rows:
        item = dict(row)
        if item.get('details_json'):
            item['details'] = json.loads(item['details_json'])
        else:
            item['details'] = {}
        if item.get('category'):
            categories.add(item['category'])
        signature = database.build_event_signature(item)
        if not signature:
            signature = f"empty|{item.get('category', '')}"
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        events.append(item)

    return {"article": dict(article_row), "events": events, "categories": list(categories)}

@app.get("/api/sources")
async def get_sources():
    sources_path = os.path.abspath(config.SOURCES_FILE)
    if not os.path.exists(sources_path):
        return {"sources": []}
    with open(sources_path, "r", encoding="utf-8") as f:
        sources = json.load(f)
    return {"sources": sources}

@app.get("/api/scheduler/runs")
async def get_scheduler_runs():
    """获取历史调度任务运行结果列表"""
    scheduler_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scheduler")
    if not os.path.exists(scheduler_dir):
        return {"runs": []}
    
    files = [f for f in os.listdir(scheduler_dir) if f.endswith(".md")]
    files.sort(reverse=True)
    
    runs = []
    for f in files:
        # Parse timestamp from filename: YYYYMMDD_HHMMSS.md
        try:
            ts_str = f.split(".")[0]
            dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
            runs.append({
                "id": f,
                "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "short_ts": dt.strftime("%m-%d %H:%M")
            })
        except:
            continue
            
    return {"runs": runs}

@app.get("/api/scheduler/run/{filename}")
async def get_scheduler_run_detail(filename: str):
    """获取指定调度任务运行详情"""
    scheduler_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scheduler")
    file_path = os.path.join(scheduler_dir, filename)
    
    if not os.path.exists(file_path):
        return {"content": "文件不存在"}
        
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    return {"content": content}

if __name__ == "__main__":
    # 允许外部访问
    uvicorn.run(app, host="0.0.0.0", port=8000)
