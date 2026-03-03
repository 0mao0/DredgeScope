import sqlite3
import os
from datetime import datetime
import config
from static.constants import (
    DEFAULT_CATEGORY,
    ALLOWED_CATEGORIES,
    normalize_category,
    infer_category_from_text
)

DB_PATH = os.path.join(config.DATA_DIR, 'dredge_intel.db')
TRACK_DB_PATH = os.path.join(config.DATA_DIR, 'ship_tracks.db')

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

    # 检查并添加缺失的 is_retained 列 (针对已有数据库)
    try:
        c.execute("SELECT is_retained FROM articles LIMIT 1")
    except sqlite3.OperationalError:
        print("[DB] 检测到 articles 表缺失 is_retained 列，正在添加...")
        try:
            c.execute("ALTER TABLE articles ADD COLUMN is_retained INTEGER DEFAULT 0")
            print("[DB] 已成功添加 is_retained 列")
        except Exception as e:
            print(f"[DB] 添加 is_retained 列失败: {e}")

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

    c.execute("DROP TABLE IF EXISTS events")
    c.execute("DROP TABLE IF EXISTS event_groups")
    
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

def save_article(article_data):
    if not article_data:
        return False
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        url = article_data.get('url')
        if not url:
            return False
        c.execute("SELECT id FROM articles WHERE url = ?", (url,))
        row = c.fetchone()

        primary_category = normalize_category(article_data.get("category"))
        if not primary_category:
            primary_category = infer_category_from_text(" ".join([
                str(article_data.get("title", "")),
                str(article_data.get("title_cn", "")),
                str(article_data.get("summary_cn", "")),
                str(article_data.get("full_text_cn", ""))
            ]))
        if not primary_category or primary_category not in ALLOWED_CATEGORIES:
            primary_category = DEFAULT_CATEGORY
        primary_category = normalize_category(primary_category)

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
                    is_hidden = COALESCE(?, is_hidden),
                    is_retained = COALESCE(?, is_retained)
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
                    article_data.get('is_retained', None),
                    article_id
                )
            )
        else:
            is_hidden = 0
            valid = article_data.get('valid', 1)
            is_retained = article_data.get('is_retained', 0)
            STALE_THRESHOLD_DAYS = 30
            try:
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
                (url, title, title_cn, pub_date, source_type, source_name, summary_cn, full_text_cn, content, screenshot_path, is_significant, vl_desc, category, is_hidden, valid, is_retained, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
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
                    is_retained,
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
            
            valid = item.get("valid", 1)
            is_hidden = item.get("is_hidden", 0)
            
            # Check for stale content
            STALE_THRESHOLD_DAYS = 30
            try:
                if pub_date:
                    p_date_clean = str(pub_date).strip()
                    p_date = None
                    if 'T' in p_date_clean:
                         try:
                             p_date = datetime.fromisoformat(p_date_clean)
                         except:
                             pass
                    elif ' ' in p_date_clean and ':' in p_date_clean:
                         try:
                             p_date = datetime.fromisoformat(p_date_clean.replace(' ', 'T'))
                         except:
                             pass
                    else:
                         try:
                             p_date = datetime.strptime(p_date_clean, "%Y-%m-%d")
                         except:
                             pass
                    
                    if p_date and (datetime.now().date() - p_date.date()).days > STALE_THRESHOLD_DAYS:
                        is_hidden = 1
                        valid = 0
            except Exception as e:
                # print(f"Date parse error: {e}")
                pass

            c.execute('''INSERT INTO articles 
                (url, title, pub_date, source_type, source_name, summary_cn, full_text_cn, content, screenshot_path, created_at, valid, is_hidden)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
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
                    valid,
                    is_hidden
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

def get_articles_by_time_range(start_time, end_time):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    query = '''
        SELECT 
            id, title, title_cn, url, pub_date, summary_cn, full_text_cn, content,
            screenshot_path, vl_desc, created_at, source_type, source_name, valid, category
        FROM articles
        WHERE created_at BETWEEN ? AND ?
        ORDER BY created_at DESC
    '''
    c.execute(query, (start_time, end_time))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_articles_by_time_range_strict(start_time, end_time, is_retained=None):
    """仅按时间窗口获取有效且未隐藏的文章 (优先使用入库时间 created_at，确保日报包含最新抓取的内容)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # 逻辑修改：
    # 原逻辑优先使用 pub_date，导致补抓的旧闻被归档到过去，容易被用户漏看。
    # 现改为纯粹基于 created_at (入库时间)，确保“新发现”的新闻（即使是旧闻）也能出现在当前的日报中。
    
    query = '''
        SELECT 
            a.id, a.title, a.title_cn, a.url, a.pub_date, a.summary_cn, a.full_text_cn, a.content, 
            a.screenshot_path, a.vl_desc, a.created_at, a.source_type, a.source_name, a.valid,
            a.category, a.is_retained
        FROM articles a
        WHERE 
          a.created_at >= ? AND a.created_at <= ?
          AND (a.is_hidden = 0 OR a.is_hidden IS NULL)
          AND (a.valid = 1 OR a.valid IS NULL)
    '''
    params = [start_time, end_time]

    if is_retained is not None:
        query += ' AND a.is_retained = ?'
        params.append(is_retained)

    query += ' ORDER BY a.created_at DESC'

    c.execute(query, tuple(params))
    rows = c.fetchall()
    conn.close()
    results = []
    for row in rows:
        item = dict(row)
        category = item.get("category")
        item["categories"] = [category] if category else []
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
