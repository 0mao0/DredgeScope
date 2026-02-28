import os
import requests
from datetime import datetime
import sys
import reverse_geocoder as rg
import pycountry
import pycountry_convert as pc

# Ensure backend is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
import config

_geo_initialized = False

def _ensure_geo_loaded():
    """确保地理编码数据已加载（只加载一次）"""
    global _geo_initialized
    if not _geo_initialized:
        print("[Status] 加载地理数据...")
        rg.search((0, 0), mode=1)  # 预加载地理数据
        _geo_initialized = True

def fetch_all_fleet_positions():
    """从 Fleet API 获取所有船舶位置"""
    try:
        resp = requests.get(config.FLEET_API_URL, timeout=30)
        if resp.status_code != 200:
            print(f"[API] 请求失败: {resp.status_code}")
            return {}
        
        data = resp.json()
        if data.get("result") != "ok":
            print(f"[API] 返回错误: {data}")
            return {}
            
        ship_map = {}
        for item in data.get("list", []):
            mmsi = item.get("mmsi")
            if mmsi:
                ship_map[str(mmsi)] = item
        return ship_map
    except Exception as e:
        print(f"[API] 获取数据异常: {e}")
        return {}

def get_continent_name(country_code):
    try:
        if not country_code: return 'Unknown'
        continent_code = pc.country_alpha2_to_continent_code(country_code)
        continents = {
            'NA': 'North America',
            'SA': 'South America', 
            'AS': 'Asia',
            'OC': 'Oceania',
            'AF': 'Africa',
            'EU': 'Europe',
            'AN': 'Antarctica'
        }
        return continents.get(continent_code, 'Unknown')
    except:
        return 'Unknown'

def update_ship_statuses():
    """批量更新船舶状态"""
    print("[Status] 开始更新船舶位置信息...")
    
    # 1. 获取最新位置数据
    fleet_data = fetch_all_fleet_positions()
    if not fleet_data:
        print("[Status] 未获取到船舶位置数据")
        return

    conn = database.sqlite3.connect(database.DB_PATH, timeout=30)
    c = conn.cursor()
    
    # 2. 获取数据库中需要更新的船舶 (Get name as well)
    c.execute("SELECT mmsi, name FROM ships WHERE mmsi IS NOT NULL AND mmsi != ''")
    db_ships = c.fetchall()
    
    updated_count = 0
    
    # 预加载地理数据（只加载一次）
    _ensure_geo_loaded()

    for (mmsi, ship_name_db) in db_ships:
        mmsi = str(mmsi)
        ship_info = fleet_data.get(mmsi)
        
        if ship_info:
            try:
                lat = float(ship_info.get("lat", 0))
                lng = float(ship_info.get("lon", 0))
                
                # 如果经纬度为 0，跳过更新位置（避免显示在 0,0 坐标）
                if abs(lat) < 0.01 and abs(lng) < 0.01:
                    continue
                    
                speed = float(ship_info.get("speed", 0))
                heading = float(ship_info.get("heading", 0))
                status_raw = ship_info.get("status", "Unknown")
                update_time = ship_info.get("updatetime")
                
                # Get vessel name from API or DB
                vessel_name = ship_info.get("shipname") or ship_info.get("name") or ship_name_db
                
                # 地理反向编码
                country_name = ""
                continent = ""
                province = ""
                city = ""
                
                if lat != 0 and lng != 0:
                    try:
                        results = rg.search((lat, lng), mode=1)
                        if results:
                            info = results[0]
                            cc = info.get('cc', '')
                            province = info.get('admin1', '')
                            city = info.get('name', '')
                            
                            if cc:
                                c_obj = pycountry.countries.get(alpha_2=cc)
                                country_name = c_obj.name if c_obj else cc
                                continent = get_continent_name(cc)
                    except Exception as geo_e:
                        print(f"[Status] Geo Error for {mmsi}: {geo_e}")

                # 更新 ships 表 (Do NOT update status here, let analysis do it)
                # But we might want to update status_raw if we had such column.
                # Since we don't, we just update location/time/speed/heading.
                c.execute("""
                    UPDATE ships 
                    SET location = ?, 
                        updated_at = ?,
                        country = ?,
                        continent = ?,
                        province = ?,
                        city = ?,
                        speed = ?,
                        heading = ?
                    WHERE mmsi = ?
                """, (f"{lat}, {lng}", datetime.now().isoformat(), 
                      country_name, continent, province, city, speed, heading, mmsi))
                
                # 记录轨迹
                database.add_ship_track(
                    mmsi=mmsi,
                    lat=lat,
                    lng=lng,
                    speed=speed,
                    heading=heading,
                    status_raw=status_raw,
                    timestamp=update_time or datetime.now().isoformat(),
                    vessel_name=vessel_name
                )

                updated_count += 1
            except Exception as e:
                print(f"[Status] 更新船舶 {mmsi} 失败: {e}")
                
    conn.commit()
    conn.close()
    print(f"[Status] 更新完成，共更新 {updated_count} 艘船舶")


if __name__ == "__main__":
    update_ship_statuses()
