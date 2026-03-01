import sqlite3
import json
import os
from datetime import datetime
import config
from static.constants import (
    DEFAULT_CATEGORY,
    ALLOWED_CATEGORIES,
    KEYWORD_CATEGORY_MAP,
    normalize_category,
    infer_category_from_text,
    text_contains_any,
    normalize_event_text,
    build_event_signature
)

DB_PATH = os.path.join(config.DATA_DIR, 'dredge_intel.db')
TRACK_DB_PATH = os.path.join(config.DATA_DIR, 'ship_tracks.db')

def enrich_event_category(item):
    category = normalize_category(item.get("category"))
    details = item.get("details") or {}
    candidate_values = []
    for key in ["event_type", "type", "eventType", "description", "trend", "technology_name", "regulation_name", "project_status", "company", "institution", "vessel_name"]:
        val = details.get(key)
        if val:
            candidate_values.append(str(val))
    for key in ["project_name", "location", "contractor", "client", "amount", "currency", "article_title", "summary_cn", "title_cn"]:
        val = item.get(key)
        if val:
            candidate_values.append(str(val))
    text_blob = " ".join(candidate_values)
    inferred = infer_category_from_text(text_blob)
    if inferred and inferred in ALLOWED_CATEGORIES:
        item["category"] = inferred
    else:
        item["category"] = category if category in ALLOWED_CATEGORIES else DEFAULT_CATEGORY
    lower = text_blob.lower()
    bid_keywords = KEYWORD_CATEGORY_MAP[0][0]
    market_keywords = KEYWORD_CATEGORY_MAP[2][0]
    project_keywords = KEYWORD_CATEGORY_MAP[3][0]
    regulation_keywords = KEYWORD_CATEGORY_MAP[4][0]
    has_bid = text_contains_any(lower, bid_keywords)
    has_market = text_contains_any(lower, market_keywords)
    has_project = text_contains_any(lower, project_keywords)
    has_regulation = text_contains_any(lower, regulation_keywords)
    if item["category"] == "Bid" and not has_bid and has_market:
        item["category"] = "Market"
    if item["category"] == "Project" and has_regulation and not has_project:
        item["category"] = "Regulation"
    return item

def pick_primary_category(article_data, events_data):
    category = normalize_category(article_data.get("category") if isinstance(article_data, dict) else None)
    if category in ALLOWED_CATEGORIES:
        return category
    priority = ["Bid", "Project", "Equipment", "Regulation", "R&D", "Market", "Other"]
    found = set()
    for evt in events_data or []:
        if not isinstance(evt, dict):
            continue
        evt_cat = normalize_category(evt.get("category"))
        if not evt_cat:
            evt_type = evt.get("event_type") or evt.get("type") or evt.get("eventType")
            evt_cat = normalize_category(evt_type)
        if evt_cat in ALLOWED_CATEGORIES:
            found.add(evt_cat)
    for key in priority:
        if key in found:
            return key
    return None

def init_track_db():
    """初始化轨迹数据库"""
    conn = sqlite3.connect(TRACK_DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ships'")
    ships_exists = c.fetchone() is not None
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ship_infos'")
    ship_infos_exists = c.fetchone() is not None
    if ships_exists and not ship_infos_exists:
        c.execute("ALTER TABLE ships RENAME TO ship_infos")
    c.execute('''CREATE TABLE IF NOT EXISTS ship_tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mmsi TEXT,
        vessel_name TEXT,
        lat REAL,
        lng REAL,
        speed REAL,
        heading REAL,
        status_raw TEXT,
        timestamp TEXT,
        created_at TEXT
    )''')
    # 创建索引以加速查询
    c.execute("CREATE INDEX IF NOT EXISTS idx_tracks_mmsi_time ON ship_tracks(mmsi, timestamp)")
    
    # 检查并添加 vessel_name 列 (针对已有数据库)
    try:
        c.execute("SELECT vessel_name FROM ship_tracks LIMIT 1")
    except sqlite3.OperationalError:
        print("[DB] 检测到 ship_tracks 表缺失 vessel_name 列，正在添加...")
        try:
            c.execute("ALTER TABLE ship_tracks ADD COLUMN vessel_name TEXT")
            print("[DB] 已成功添加 vessel_name 列")
        except Exception as e:
            print(f"[DB] 添加 vessel_name 列失败: {e}")

    c.execute('''CREATE TABLE IF NOT EXISTS ship_infos (
        id INTEGER PRIMARY KEY, -- Removed AUTOINCREMENT to allow explicit ID insertion
        imo TEXT, -- Removed UNIQUE constraint due to duplicates in CSV
        mmsi TEXT,
        name TEXT,
        company TEXT,
        type TEXT,
        capacity_1 TEXT,
        capacity_2 TEXT,
        region TEXT,
        location TEXT,
        status TEXT,
        status_date TEXT,
        remarks TEXT,
        updated_at TEXT,
        country TEXT,
        continent TEXT,
        province TEXT,
        city TEXT,
        speed REAL,
        heading REAL
    )''')

    conn.commit()
    conn.close()
    print(f"[DB] 轨迹数据库已初始化: {TRACK_DB_PATH}")

def init_db():
    """初始化数据库表结构"""
    # 1. 初始化轨迹库
    init_track_db()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. 文章表 (Articles) - 存储原始抓取信息
    c.execute('''CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE,
        title TEXT,
        title_cn TEXT,
        pub_date TEXT,
        source_type TEXT,
        source_name TEXT,
        summary_cn TEXT,
        full_text_cn TEXT,
        content TEXT,
        screenshot_path TEXT,
        is_significant BOOLEAN,
        vl_desc TEXT,
        category TEXT,
        is_hidden INTEGER DEFAULT 0,
        valid INTEGER DEFAULT 1,
        created_at TEXT
    )''')
    
    # 检查并添加缺失的 title_cn 列 (针对已有数据库)
    try:
        c.execute("SELECT title_cn FROM articles LIMIT 1")
    except sqlite3.OperationalError:
        print("[DB] 检测到 articles 表缺失 title_cn 列，正在添加...")
        try:
            c.execute("ALTER TABLE articles ADD COLUMN title_cn TEXT")
            print("[DB] 已成功添加 title_cn 列")
        except Exception as e:
            print(f"[DB] 添加 title_cn 列失败: {e}")

    # 检查并添加缺失的 is_hidden 列 (针对已有数据库)
    try:
        c.execute("SELECT is_hidden FROM articles LIMIT 1")
    except sqlite3.OperationalError:
        print("[DB] 检测到 articles 表缺失 is_hidden 列，正在添加...")
        try:
            c.execute("ALTER TABLE articles ADD COLUMN is_hidden INTEGER DEFAULT 0")
            print("[DB] 已成功添加 is_hidden 列")
        except Exception as e:
            print(f"[DB] 添加 is_hidden 列失败: {e}")

    try:
        c.execute("SELECT source_name FROM articles LIMIT 1")
    except sqlite3.OperationalError:
        print("[DB] 检测到 articles 表缺失 source_name 列，正在添加...")
        try:
            c.execute("ALTER TABLE articles ADD COLUMN source_name TEXT")
            print("[DB] 已成功添加 source_name 列")
        except Exception as e:
            print(f"[DB] 添加 source_name 列失败: {e}")

    try:
        c.execute("SELECT valid FROM articles LIMIT 1")
    except sqlite3.OperationalError:
        print("[DB] 检测到 articles 表缺失 valid 列，正在添加...")
        try:
            c.execute("ALTER TABLE articles ADD COLUMN valid INTEGER DEFAULT 1")
            print("[DB] 已成功添加 valid 列")
        except Exception as e:
            print(f"[DB] 添加 valid 列失败: {e}")

    try:
        c.execute("SELECT category FROM articles LIMIT 1")
    except sqlite3.OperationalError:
        print("[DB] 检测到 articles 表缺失 category 列，正在添加...")
        try:
            c.execute("ALTER TABLE articles ADD COLUMN category TEXT")
            print("[DB] 已成功添加 category 列")
        except Exception as e:
            print(f"[DB] 添加 category 列失败: {e}")

    try:
        c.execute("SELECT full_text_cn FROM articles LIMIT 1")
    except sqlite3.OperationalError:
        print("[DB] 检测到 articles 表缺失 full_text_cn 列，正在添加...")
        try:
            c.execute("ALTER TABLE articles ADD COLUMN full_text_cn TEXT")
            print("[DB] 已成功添加 full_text_cn 列")
        except Exception as e:
            print(f"[DB] 添加 full_text_cn 列失败: {e}")

    try:
        c.execute("SELECT content FROM articles LIMIT 1")
    except sqlite3.OperationalError:
        print("[DB] 检测到 articles 表缺失 content 列，正在添加...")
        try:
            c.execute("ALTER TABLE articles ADD COLUMN content TEXT")
            print("[DB] 已成功添加 content 列")
        except Exception as e:
            print(f"[DB] 添加 content 列失败: {e}")

    try:
        c.execute("""
            UPDATE articles
            SET category = (
                SELECT e.category
                FROM events e
                WHERE e.article_id = articles.id
                ORDER BY CASE e.category
                    WHEN 'Bid' THEN 1
                    WHEN 'Project' THEN 2
                    WHEN 'Equipment' THEN 3
                    WHEN 'Regulation' THEN 4
                    WHEN 'R&D' THEN 5
                    WHEN 'Market' THEN 6
                    WHEN 'Other' THEN 7
                    ELSE 99
                END
                LIMIT 1
            )
            WHERE (category IS NULL OR category = '')
              AND EXISTS (SELECT 1 FROM events e2 WHERE e2.article_id = articles.id)
        """)
    except Exception as e:
        print(f"[DB] 回填 category 列失败: {e}")

    # 2. 事件分组表 (Event Groups)
    c.execute('''CREATE TABLE IF NOT EXISTS event_groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        signature TEXT UNIQUE,
        category TEXT,
        project_name TEXT,
        location TEXT,
        contractor TEXT,
        client TEXT,
        details_json TEXT,
        first_seen_at TEXT,
        last_seen_at TEXT
    )''')

    # 3. 事件表 (Events)
    c.execute('''CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER,
        event_group_id INTEGER,
        event_signature TEXT,
        event_time TEXT,
        category TEXT, 
        project_name TEXT,
        location TEXT,
        amount TEXT,
        currency TEXT,
        contractor TEXT,
        client TEXT,
        details_json TEXT, 
        created_at TEXT,
        FOREIGN KEY(article_id) REFERENCES articles(id),
        FOREIGN KEY(event_group_id) REFERENCES event_groups(id)
    )''')

    try:
        c.execute("SELECT event_group_id FROM events LIMIT 1")
    except sqlite3.OperationalError:
        print("[DB] 检测到 events 表缺失 event_group_id 列，正在添加...")
        try:
            c.execute("ALTER TABLE events ADD COLUMN event_group_id INTEGER")
            print("[DB] 已成功添加 event_group_id 列")
        except Exception as e:
            print(f"[DB] 添加 event_group_id 列失败: {e}")

    try:
        c.execute("SELECT event_signature FROM events LIMIT 1")
    except sqlite3.OperationalError:
        print("[DB] 检测到 events 表缺失 event_signature 列，正在添加...")
        try:
            c.execute("ALTER TABLE events ADD COLUMN event_signature TEXT")
            print("[DB] 已成功添加 event_signature 列")
        except Exception as e:
            print(f"[DB] 添加 event_signature 列失败: {e}")

    try:
        c.execute("SELECT event_time FROM events LIMIT 1")
    except sqlite3.OperationalError:
        print("[DB] 检测到 events 表缺失 event_time 列，正在添加...")
        try:
            c.execute("ALTER TABLE events ADD COLUMN event_time TEXT")
            print("[DB] 已成功添加 event_time 列")
        except Exception as e:
            print(f"[DB] 添加 event_time 列失败: {e}")
    
    conn.commit()
    conn.close()
    print(f"[DB] 数据库已初始化: {DB_PATH}")

def add_ship_track(mmsi, lat, lng, speed, heading, status_raw, timestamp, vessel_name=None):
    """添加船舶轨迹点"""
    conn = sqlite3.connect(TRACK_DB_PATH, timeout=10) # 连接轨迹库
    c = conn.cursor()
    try:
        # 1. 插入新记录
        c.execute('''INSERT INTO ship_tracks 
            (mmsi, lat, lng, speed, heading, status_raw, timestamp, created_at, vessel_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (mmsi, lat, lng, speed, heading, status_raw, timestamp, datetime.now().isoformat(), vessel_name)
        )
        
        # 2. 清理旧记录 (保留最近 5000 条, 确保足够覆盖30天)
        # 稳健的方法：保留最新的 5000 条
        c.execute('''
            DELETE FROM ship_tracks 
            WHERE id NOT IN (
                SELECT id FROM ship_tracks 
                WHERE mmsi = ? 
                ORDER BY timestamp DESC 
                LIMIT 5000
            ) AND mmsi = ?
        ''', (mmsi, mmsi))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB] 添加轨迹失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_ship_tracks(mmsi, days=3):
    """获取船舶历史轨迹"""
    from datetime import timedelta
    conn = sqlite3.connect(TRACK_DB_PATH)
    c = conn.cursor()
    
    start_time = (datetime.now() - timedelta(days=days)).isoformat()
    
    try:
        c.execute('''
            SELECT lat, lng, speed, heading, timestamp, created_at
            FROM ship_tracks 
            WHERE mmsi = ? AND timestamp > ?
            ORDER BY timestamp ASC
        ''', (mmsi, start_time))
        
        tracks = []
        for row in c.fetchall():
            tracks.append({
                "lat": row[0],
                "lng": row[1],
                "speed": row[2],
                "heading": row[3],
                "timestamp": row[4],
                "created_at": row[5]
            })
        return tracks
    except Exception as e:
        print(f"[DB] 获取轨迹失败: {e}")
        return []
    finally:
        conn.close()

def upsert_ships(ships):
    """批量插入或更新船舶记录"""
    if not ships:
        return 0
    conn = sqlite3.connect(TRACK_DB_PATH) # 迁移至 TRACK_DB_PATH
    c = conn.cursor()
    now = datetime.now().isoformat()
    updated = 0
    try:
        for ship in ships:
            c.execute(
                """
                INSERT INTO ship_infos (
                    id, imo, mmsi, name, company, type,
                    capacity_1, capacity_2, region, location,
                    status, status_date, remarks, updated_at,
                    country, continent, province, city,
                    speed, heading
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET -- Use ID as primary conflict key if provided
                    imo=excluded.imo,
                    mmsi=excluded.mmsi,
                    name=excluded.name,
                    company=excluded.company,
                    type=excluded.type,
                    capacity_1=excluded.capacity_1,
                    capacity_2=excluded.capacity_2,
                    region=excluded.region,
                    location=excluded.location,
                    status=excluded.status,
                    status_date=excluded.status_date,
                    remarks=excluded.remarks,
                    updated_at=excluded.updated_at,
                    country=excluded.country,
                    continent=excluded.continent,
                    province=excluded.province,
                    city=excluded.city
                """,
                (
                    ship.get("id"), # Explicit ID
                    ship.get("imo"),
                    ship.get("mmsi"),
                    ship.get("name"),
                    ship.get("company"),
                    ship.get("type"),
                    ship.get("capacity_1"),
                    ship.get("capacity_2"),
                    ship.get("region"),
                    ship.get("location"),
                    ship.get("status"),
                    ship.get("status_date"),
                    ship.get("remarks"),
                    now,
                    ship.get("country"),
                    ship.get("continent"),
                    ship.get("province"),
                    ship.get("city"),
                    ship.get("speed"),
                    ship.get("heading")
                ),
            )
            updated += 1
        conn.commit()
        return updated
    except Exception as e:
        print(f"[DB] ships upsert 失败: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()

def update_ship_status(mmsi, status, status_date, location, region, country=None, continent=None, province=None, city=None, speed=None, heading=None):
    """更新单船状态信息"""
    conn = sqlite3.connect(TRACK_DB_PATH) # 迁移至 TRACK_DB_PATH
    c = conn.cursor()
    try:
        c.execute(
            """
            UPDATE ship_infos
            SET status = ?, status_date = ?, location = ?, region = ?, updated_at = ?,
                country = COALESCE(?, country),
                continent = COALESCE(?, continent),
                province = COALESCE(?, province),
                city = COALESCE(?, city),
                speed = COALESCE(?, speed),
                heading = COALESCE(?, heading)
            WHERE mmsi = ?
            """,
            (status, status_date, location, region, datetime.now().isoformat(), 
             country, continent, province, city, speed, heading, mmsi),
        )
        conn.commit()
        return c.rowcount
    except Exception as e:
        print(f"[DB] 更新船舶状态失败: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()

def get_or_create_event_group(conn, signature, evt, category, details_json, event_time):
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("SELECT id, first_seen_at FROM event_groups WHERE signature = ?", (signature,))
    row = c.fetchone()
    if row:
        group_id = row[0]
        c.execute(
            '''
            UPDATE event_groups
            SET category = ?, project_name = ?, location = ?, contractor = ?, client = ?, details_json = ?, last_seen_at = ?
            WHERE id = ?
            ''',
            (
                category,
                evt.get("project_name", ""),
                evt.get("location", ""),
                evt.get("contractor", ""),
                evt.get("client", ""),
                details_json,
                now,
                group_id
            )
        )
        return group_id
    c.execute(
        '''
        INSERT INTO event_groups
        (signature, category, project_name, location, contractor, client, details_json, first_seen_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            signature,
            category,
            evt.get("project_name", ""),
            evt.get("location", ""),
            evt.get("contractor", ""),
            evt.get("client", ""),
            details_json,
            event_time or now,
            now
        )
    )
    return c.lastrowid

def save_article_and_events(article_data, events_data):
    """保存文章和关联事件"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        primary_category = pick_primary_category(article_data, events_data)
        # 1. 插入或忽略文章 (避免重复)
        # 注意：如果文章已存在，我们跳过插入，但可能需要检查是否需要更新（目前简化为跳过）
        c.execute("SELECT id FROM articles WHERE url = ?", (article_data['url'],))
        row = c.fetchone()
        
        if row:
            article_id = row[0]
            c.execute(
                '''
                UPDATE articles
                SET
                    title = COALESCE(NULLIF(?, ''), title),
                    title_cn = COALESCE(NULLIF(?, ''), title_cn),
                    pub_date = COALESCE(NULLIF(?, ''), pub_date),
                    source_type = COALESCE(NULLIF(?, ''), source_type),
                    source_name = COALESCE(NULLIF(?, ''), source_name),
                    summary_cn = COALESCE(NULLIF(?, ''), summary_cn),
                    full_text_cn = COALESCE(NULLIF(?, ''), full_text_cn),
                    content = COALESCE(NULLIF(?, ''), content),
                    screenshot_path = COALESCE(NULLIF(?, ''), screenshot_path),
                    is_significant = COALESCE(?, is_significant),
                    vl_desc = COALESCE(NULLIF(?, ''), vl_desc),
                    category = COALESCE(NULLIF(?, ''), category),
                    valid = COALESCE(?, valid),
                    is_hidden = COALESCE(?, is_hidden)
                WHERE id = ?
                ''',
                (
                    article_data.get('title', ''),
                    article_data.get('title_cn', ''),
                    article_data.get('pub_date', ''),
                    article_data.get('source_type', ''),
                    article_data.get('source_name', ''),
                    article_data.get('summary_cn', ''),
                    article_data.get('full_text_cn', ''),
                    article_data.get('content', ''),
                    article_data.get('screenshot_path', ''),
                    article_data.get('significant', None),
                    article_data.get('image_desc', ''),
                    primary_category or '',
                    article_data.get('valid', None),
                    article_data.get('is_hidden', None),
                    article_id
                )
            )
        else:
            # Check for staleness before insertion
            is_hidden = 0
            # 使用传入的 valid，如果未提供则默认为 1
            valid = article_data.get('valid', 1)
            
            STALE_THRESHOLD_DAYS = 30
            try:
                # Assuming created_at is roughly now
                c_date = datetime.now()
                p_date_str = article_data.get('pub_date')
                if p_date_str:
                     p_date_clean = str(p_date_str).strip()
                     p_date = None
                     if 'T' in p_date_clean:
                         p_date = datetime.fromisoformat(p_date_clean)
                     elif ' ' in p_date_clean and ':' in p_date_clean:
                         p_date = datetime.fromisoformat(p_date_clean.replace(' ', 'T'))
                     else:
                         try:
                             p_date = datetime.strptime(p_date_clean, "%Y-%m-%d")
                         except:
                             pass
                     
                     if p_date and (c_date.date() - p_date.date()).days > STALE_THRESHOLD_DAYS:
                         is_hidden = 1
                         valid = 0
            except:
                pass

            c.execute('''INSERT INTO articles 
                (url, title, title_cn, pub_date, source_type, source_name, summary_cn, full_text_cn, content, screenshot_path, is_significant, vl_desc, category, is_hidden, valid, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    article_data['url'],
                    article_data['title'],
                    article_data.get('title_cn', ''),
                    article_data['pub_date'],
                    article_data.get('source_type', 'unknown'),
                    article_data.get('source_name', ''),
                    article_data.get('summary_cn', ''),
                    article_data.get('full_text_cn', ''),
                    article_data.get('content', ''),
                    article_data.get('screenshot_path', ''),
                    article_data.get('significant', False),
                    article_data.get('image_desc', ''),
                    primary_category,
                    is_hidden,
                    valid,
                    datetime.now().isoformat()
                )
            )
            article_id = c.lastrowid
            
        # 2. 插入事件
        # 如果是新文章，且没有事件数据，但标记为 Other 类别，则创建一个默认事件
        if not row:
            # 如果没有事件，但有指定的 category (如 Other)
            if not events_data and article_data.get('category') == 'Other':
                events_data = [{
                    "category": "Other",
                    "description": article_data.get('summary_cn', '垃圾信息/非新闻页面')
                }]

            seen_signatures = set()
            for evt in events_data:
                # 防御性编程：如果 evt 是字符串（解析错误导致），尝试解析或跳过
                if isinstance(evt, str):
                    try:
                        evt = json.loads(evt)
                    except:
                        print(f"[DB] 跳过无效的事件数据格式: {evt[:50]}...")
                        continue
                        
                if not isinstance(evt, dict):
                     continue

                category = normalize_category(evt.get("category"))
                if not category:
                    evt_type = evt.get("event_type") or evt.get("type") or evt.get("eventType")
                    category = normalize_category(evt_type)
                if not category:
                    candidate_values = []
                    for key in ["project_name", "location", "contract_value", "currency", "contractor", "client", "event_type", "type", "description"]:
                        val = evt.get(key)
                        if val:
                            candidate_values.append(str(val))
                    category = infer_category_from_text(" ".join(candidate_values))
                
                if not category:
                    category = DEFAULT_CATEGORY
                if category not in ALLOWED_CATEGORIES:
                    category = DEFAULT_CATEGORY

                # 提取通用字段
                details = {k: v for k, v in evt.items()}
                amount_value = evt.get("amount") or evt.get("contract_value") or ""
                if amount_value and not details.get("amount"):
                    details["amount"] = amount_value
                details_json = json.dumps(details, ensure_ascii=False, sort_keys=True)
                event_time = evt.get("time") or evt.get("publish_time") or evt.get("pub_time") or article_data.get("pub_date") or ""
                signature = build_event_signature({
                    "category": category,
                    "project_name": evt.get("project_name", ""),
                    "location": evt.get("location", ""),
                    "amount": evt.get("amount") or evt.get("contract_value", ""),
                    "currency": evt.get("currency", ""),
                    "contractor": evt.get("contractor", ""),
                    "client": evt.get("client", ""),
                    "time": event_time,
                    "content": evt.get("content") or evt.get("description") or "",
                    "details_json": details_json
                })
                if not signature:
                    fallback_parts = [
                        evt.get("project_name"),
                        evt.get("location"),
                        evt.get("contractor"),
                        evt.get("client"),
                        evt.get("content") or evt.get("description"),
                        article_data.get("title"),
                        article_data.get("summary_cn")
                    ]
                    normalized_parts = [normalize_event_text(p) for p in fallback_parts if p]
                    signature = "|".join([p for p in normalized_parts if p])
                if not signature:
                    signature = f"empty|{category}"
                if signature in seen_signatures:
                    continue
                seen_signatures.add(signature)

                event_group_id = get_or_create_event_group(conn, signature, evt, category, details_json, event_time)

                c.execute('''INSERT INTO events 
                    (article_id, event_group_id, event_signature, event_time, category, project_name, location, amount, currency, contractor, client, details_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        article_id,
                        event_group_id,
                        signature,
                        event_time,
                        category,
                        evt.get('project_name', ''),
                        evt.get('location', ''),
                        amount_value,
                        evt.get('currency', ''),
                        evt.get('contractor', ''),
                        evt.get('client', ''),
                        details_json,
                        datetime.now().isoformat()
                    )
                )
        
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB] 保存失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def add_ship_simple(name, mmsi):
    """添加新船舶（仅名称和MMSI）"""
    conn = sqlite3.connect(TRACK_DB_PATH) # 迁移至 TRACK_DB_PATH
    c = conn.cursor()
    try:
        c.execute("INSERT INTO ship_infos (name, mmsi, updated_at) VALUES (?, ?, ?)",
                  (name, mmsi, datetime.now().isoformat()))
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB] 添加船舶失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_recent_events(limit=50):
    """获取最近的事件用于生成报告"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    query = '''
        SELECT e.*, a.title as article_title, a.title_cn, a.url as article_url, a.summary_cn, a.screenshot_path, a.is_significant, a.vl_desc, a.full_text_cn, e.details_json
        FROM events e
        JOIN articles a ON e.article_id = a.id
        ORDER BY e.created_at DESC
        LIMIT ?
    '''
    c.execute(query, (limit,))
    rows = c.fetchall()
    conn.close()
    
    results = []
    seen_by_article = {}
    for row in rows:
        item = dict(row)
        if item['details_json']:
            item['details'] = json.loads(item['details_json'])
        else:
            item['details'] = {}
        item = enrich_event_category(item)
        signature = build_event_signature(item)
        if not signature:
            signature = f"empty|{item.get('category', '')}"
        article_id = item.get("article_id")
        if article_id is not None:
            seen = seen_by_article.setdefault(article_id, set())
            if signature in seen:
                continue
            seen.add(signature)
        results.append(item)
    return results

def is_article_exists(url):
    """检查文章是否已存在"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM articles WHERE url = ?", (url,))
    row = c.fetchone()
    conn.close()
    return row is not None

def save_raw_articles(items):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    inserted = 0
    try:
        for item in items or []:
            url = item.get("link") or item.get("url")
            if not url:
                continue
            c.execute("SELECT id FROM articles WHERE url = ?", (url,))
            if c.fetchone():
                continue
            pub_date = item.get("pub_date") or item.get("date") or ""
            content = item.get("content") or item.get("summary_raw") or item.get("digest") or ""
            screenshot_path = item.get("screenshot_path") or ""
            c.execute('''INSERT INTO articles 
                (url, title, pub_date, source_type, source_name, summary_cn, full_text_cn, content, screenshot_path, created_at, valid)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    url,
                    item.get("title", ""),
                    str(pub_date),
                    item.get("source_type", "unknown"),
                    item.get("source_name", ""),
                    "",
                    "",
                    content,
                    screenshot_path,
                    datetime.now().isoformat(),
                    1
                )
            )
            inserted += 1
        conn.commit()
    except Exception as e:
        print(f"[DB] 保存原始文章失败: {e}")
        conn.rollback()
    finally:
        conn.close()
    return inserted

def get_articles_by_urls(urls):
    if not urls:
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    placeholders = ",".join(["?"] * len(urls))
    query = f'''
        SELECT id, title, url, pub_date, summary_cn, full_text_cn, content, screenshot_path, vl_desc, source_type, source_name, valid
        FROM articles
        WHERE url IN ({placeholders})
    '''
    c.execute(query, urls)
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_events_by_time_range(start_time, end_time):
    """获取指定时间范围内的事件"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    query = '''
        SELECT e.*, a.title as article_title, a.title_cn, a.url as article_url, a.screenshot_path, a.is_significant, a.summary_cn, a.vl_desc, a.pub_date, a.source_type, a.source_name, a.full_text_cn, e.details_json
        FROM events e
        JOIN articles a ON e.article_id = a.id
        WHERE (e.created_at BETWEEN ? AND ?) 
          AND (a.is_hidden = 0 OR a.is_hidden IS NULL)
          AND (a.valid = 1 OR a.valid IS NULL)
        ORDER BY e.created_at DESC
    '''
    c.execute(query, (start_time, end_time))
    rows = c.fetchall()
    conn.close()
    
    results = []
    seen_by_article = {}
    for row in rows:
        item = dict(row)
        if item['details_json']:
            item['details'] = json.loads(item['details_json'])
        else:
            item['details'] = {}
        item = enrich_event_category(item)
        pub_date_str = item.get("pub_date")
        created_at_str = item.get("created_at")
        ref_date = None
        if pub_date_str:
            try:
                pub_clean = str(pub_date_str).strip()
                if 'T' in pub_clean:
                    ref_date = datetime.fromisoformat(pub_clean)
                elif ' ' in pub_clean and ':' in pub_clean:
                    ref_date = datetime.fromisoformat(pub_clean.replace(' ', 'T'))
                else:
                    ref_date = datetime.strptime(pub_clean, "%Y-%m-%d")
            except:
                ref_date = None
        if not ref_date and created_at_str:
            try:
                created_clean = str(created_at_str).split('.')[0]
                if 'T' in created_clean:
                    ref_date = datetime.fromisoformat(created_clean)
                elif ' ' in created_clean and ':' in created_clean:
                    ref_date = datetime.fromisoformat(created_clean.replace(' ', 'T'))
                else:
                    ref_date = datetime.strptime(created_clean, "%Y-%m-%d")
            except:
                ref_date = None
        if ref_date:
            if (datetime.now().date() - ref_date.date()).days > 30:
                continue
        signature = build_event_signature(item)
        if not signature:
            signature = f"empty|{item.get('category', '')}"
        article_id = item.get("article_id")
        if article_id is not None:
            seen = seen_by_article.setdefault(article_id, set())
            if signature in seen:
                continue
            seen.add(signature)
        results.append(item)
    return results

def get_events_by_time_range_strict(start_time, end_time):
    """仅按时间窗口获取有效且未隐藏的事件"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    query = '''
        SELECT e.*, a.title as article_title, a.title_cn, a.url as article_url, a.screenshot_path, a.is_significant, a.summary_cn, a.vl_desc, a.pub_date, a.source_type, a.source_name, a.full_text_cn, e.details_json
        FROM events e
        JOIN articles a ON e.article_id = a.id
        WHERE (e.created_at BETWEEN ? AND ?) 
          AND (a.is_hidden = 0 OR a.is_hidden IS NULL)
          AND (a.valid = 1 OR a.valid IS NULL)
        ORDER BY e.created_at DESC
    '''
    c.execute(query, (start_time, end_time))
    rows = c.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        item = dict(row)
        if item['details_json']:
            item['details'] = json.loads(item['details_json'])
        else:
            item['details'] = {}
        item = enrich_event_category(item)
        results.append(item)
    return results

def get_articles_by_time_range_strict(start_time, end_time):
    """仅按时间窗口获取有效且未隐藏的文章"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    query = '''
        SELECT 
            a.id, a.title, a.title_cn, a.url, a.pub_date, a.summary_cn, a.full_text_cn, a.content, 
            a.screenshot_path, a.vl_desc, a.created_at, a.source_type, a.source_name, a.valid,
            GROUP_CONCAT(DISTINCT e.category) as categories
        FROM articles a
        LEFT JOIN events e ON e.article_id = a.id
        WHERE (a.created_at BETWEEN ? AND ?)
          AND (a.is_hidden = 0 OR a.is_hidden IS NULL)
          AND (a.valid = 1 OR a.valid IS NULL)
        GROUP BY a.id
        ORDER BY a.created_at DESC
    '''
    c.execute(query, (start_time, end_time))
    rows = c.fetchall()
    conn.close()
    results = []
    for row in rows:
        item = dict(row)
        cats = item.get("categories") or ""
        item["categories"] = [c for c in cats.split(",") if c] if cats else []
        results.append(item)
    return results

# 初始化
init_db()

def get_all_ships():
    """获取所有船舶信息"""
    conn = sqlite3.connect(TRACK_DB_PATH) # 迁移至 TRACK_DB_PATH
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM ship_infos")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_ship_mmsi(ship_id, mmsi):
    """更新船舶MMSI"""
    conn = sqlite3.connect(TRACK_DB_PATH) # 迁移至 TRACK_DB_PATH
    c = conn.cursor()
    try:
        c.execute("UPDATE ship_infos SET mmsi = ?, updated_at = ? WHERE id = ?", (mmsi, datetime.now().isoformat(), ship_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB] 更新MMSI失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
