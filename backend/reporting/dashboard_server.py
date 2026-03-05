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
# Use config.ROOT_DIR to ensure correct path
STATIC_DIR = os.path.join(config.ROOT_DIR, 'backend', 'static')
print(f"[Dashboard] Mounting /static to {STATIC_DIR}")
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
    start: str = Query(None, description="Start time ISO format"),
    end: str = Query(None, description="End time ISO format"),
    is_retained: int = Query(1, description="Retained filter (1 for retained, 0 for discarded, None for all)")
):
    """获取指定时间范围内的文章 (默认只返回 is_retained=1 的)"""
    try:
        # Use provided times or default to last 24 hours
        if not start or not end:
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=1)
            start = start_dt.isoformat()
            end = end_dt.isoformat()
            
        articles = database.get_articles_by_time_range_strict(start, end, is_retained=is_retained)
        return {"events": articles}
    except Exception as e:
        print(f"Error in get_events: {e}")
        return {"events": [], "error": str(e)}

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
        SELECT date(a.created_at) as d, count(*) as c
        FROM articles a
        WHERE a.created_at >= ? 
          AND (a.is_hidden = 0 OR a.is_hidden IS NULL)
          AND (a.valid = 1 OR a.valid IS NULL)
        GROUP BY date(a.created_at)
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
    
    articles = database.get_articles_by_time_range(start_time, end_time)
    
    # 1. Category Pie Chart
    # Use enriched category
    categories = []
    for a in articles:
        cat = a.get('category')
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
    
    for a in articles:
        d_str = a.get('pub_date') or a.get('created_at')
        if not d_str: continue
        try:
            # Handle potential ISO format with T or space
            clean_date = str(d_str).replace('T', ' ').split('.')[0]
            d_obj = datetime.strptime(clean_date[:10], "%Y-%m-%d")
            date_key = d_obj.strftime("%Y-%m-%d")
            cat = a.get('category')
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
    for a in articles:
        s = a.get('source_name')
        if not s or s == 'None':
            # Fallback to source_type if name missing
            s = a.get('source_type', 'Unknown')
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
    
    latest_track_map = {}
    try:
        conn = sqlite3.connect(database.TRACK_DB_PATH)
        c = conn.cursor()
        c.execute(
            """
            SELECT t.mmsi, t.lat, t.lng
            FROM ship_tracks t
            JOIN (
                SELECT mmsi, MAX(timestamp) AS max_ts
                FROM ship_tracks
                GROUP BY mmsi
            ) latest
            ON t.mmsi = latest.mmsi AND t.timestamp = latest.max_ts
            """
        )
        for row in c.fetchall():
            latest_track_map[str(row[0])] = (row[1], row[2])
    except Exception:
        latest_track_map = {}
    finally:
        try:
            conn.close()
        except Exception:
            pass

    for ship in ships:
        mmsi = str(ship.get('mmsi', '')).strip()
        if mmsi and any(ch.isdigit() for ch in mmsi):
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
        if lat is None or lng is None:
            track_point = latest_track_map.get(mmsi)
            if track_point:
                try:
                    lat_val = float(track_point[0])
                    lng_val = float(track_point[1])
                    if abs(lat_val) > 0.01 or abs(lng_val) > 0.01:
                        lat = lat_val
                        lng = lng_val
                except Exception:
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
    is_retained: int = Query(None, description="Retained filter (1 for retained, 0 for discarded)"),
    page: int = Query(1, description="Page number"),
    page_size: int = Query(50, description="Page size")
):
    conn = sqlite3.connect(database.DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

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

    if is_retained is not None:
        where.append("a.is_retained = ?")
        params.append(is_retained)

    if category:
        where.append("a.category = ?")
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
        SELECT COUNT(a.id)
        FROM articles a
        WHERE {where_sql}
    """
    c.execute(count_query, params)
    total = c.fetchone()[0] or 0

    offset = max(page - 1, 0) * page_size
    data_query = f"""
        SELECT 
            a.id, a.title, a.title_cn, a.pub_date, a.source_type, a.source_name,
            a.summary_cn, a.full_text_cn, a.content, a.screenshot_path, a.url, a.created_at,
            a.valid, a.category
        FROM articles a
        WHERE {where_sql}
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
             
        category_val = item.get("category")
        item["categories"] = [category_val] if category_val else []
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
        SELECT id, title, title_cn, url, pub_date, summary_cn, full_text_cn, content, source_type, source_name, screenshot_path, vl_desc, created_at, valid, category
        FROM articles
        WHERE id = ?
    """, (article_id,))
    article_row = c.fetchone()
    if not article_row:
        conn.close()
        return {"article": None, "events": []}
    conn.close()

    article_data = dict(article_row)
    if article_data.get('created_at'):
        article_data['created_at'] = str(article_data['created_at']).split('.')[0]
    if article_data.get('pub_date'):
        article_data['pub_date'] = str(article_data['pub_date']).split('.')[0]
    category_val = article_data.get("category")
    return {"article": article_data, "events": [], "categories": [category_val] if category_val else []}

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
    scheduler_dir = os.path.join(config.DATA_DIR, "scheduler")
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
            
            # Read stats from file content
            file_path = os.path.join(scheduler_dir, f)
            searched_count = 0
            inserted_count = 0
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as file:
                    lines = file.readlines()
                    # Skip header (2 lines) and iterate
                    for line in lines[2:]:
                        if not line.strip(): continue
                        searched_count += 1
                        parts = line.split("|")
                        # Column 5 is "是否保留" (index 5 because of leading empty string from split)
                        if len(parts) > 5 and "是" in parts[5]:
                            inserted_count += 1
            
            runs.append({
                "id": f,
                "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "short_ts": dt.strftime("%m-%d %H:%M"),
                "summary": f"(搜{searched_count}条，入{inserted_count}条)"
            })
        except:
            continue
            
    return {"runs": runs}

@app.get("/api/scheduler/run/{filename}")
async def get_scheduler_run_detail(filename: str):
    """获取指定调度任务运行详情"""
    scheduler_dir = os.path.join(config.DATA_DIR, "scheduler")
    file_path = os.path.join(scheduler_dir, filename)
    
    if not os.path.exists(file_path):
        return {"content": "文件不存在"}
        
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    return {"content": content}

if __name__ == "__main__":
    # 允许外部访问
    uvicorn.run(app, host="0.0.0.0", port=8000)
