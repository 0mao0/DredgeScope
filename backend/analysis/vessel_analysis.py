import database
from datetime import datetime
import numpy as np

def determine_status(tracks):
    """
    根据历史轨迹判定船舶状态
    tracks: list of dict, fields: speed, heading, timestamp, etc.
    return: status_string (e.g. 'Dredging', 'Moored', 'Underway')
    """
    if not tracks:
        return "Unknown"
    
    # 取最近的几个点进行分析 (用户要求最近24小时，约24个点)
    recent_tracks = tracks[:24] 
    
    speeds = [t['speed'] for t in recent_tracks if t['speed'] is not None]
    
    if not speeds:
        return "Unknown"
    
    avg_speed = sum(speeds) / len(speeds)
    
    # 获取最新的 raw status
    latest_status_raw = recent_tracks[0].get('status_raw', '')
    
    # 规则设定
    
    # 0. 优先判断 AIS 明确状态
    # "Restricted maneuverability" (操作能力受限) 或 "Engaged in fishing" (正在捕鱼) 
    # 对于疏浚船来说，这通常意味着正在施工（因为疏浚作业时操纵受限）
    if "Restricted maneuverability" in latest_status_raw or \
       "操作能力受限" in latest_status_raw or \
       "Engaged in fishing" in latest_status_raw or \
       "正在捕鱼" in latest_status_raw:
        # 即使显示捕鱼，对于疏浚船也判定为施工（可能是AIS设置错误或借用状态）
        if avg_speed > 0.1: # 只要不是完全静止
            return "Dredging"
    
    # 1. 锚泊/停泊: 速度极低 (< 0.5 kn)
    if avg_speed < 0.5:
        return "Moored"
    
    # 2. 施工 (Dredging): 速度较慢 (0.5 - 3 kn) 且在移动
    # 疏浚通常需要保持一定的航向稳定性，或者在该区域往复
    elif 0.5 <= avg_speed <= 4.0:
        # 进一步区分：如果是慢速航行(进港) vs 疏浚
        # 疏浚船在施工时通常速度非常稳定
        return "Dredging"
        
    # 3. 调遣/航行 (Underway): 速度较快 (> 3-4 kn)
    else:
        return "Underway"

def analyze_and_update_all_ships():
    """
    分析所有船舶的轨迹并更新状态
    """
    ships = database.get_all_ships()
    updated_count = 0
    
    for ship in ships:
        mmsi = ship['mmsi']
        if not mmsi:
            continue
            
        # 获取历史轨迹 (取最近100条以确保覆盖24小时)
        tracks = database.get_ship_tracks(mmsi, limit=100)
        
        if not tracks:
            continue
            
        new_status = determine_status(tracks)
        current_status = ship['status']
        
        # 如果状态发生变化，或者原状态为空，则更新
        if new_status != "Unknown" and new_status != current_status:
            # 更新状态
            # 注意：这里我们不仅更新状态，还可以更新位置信息（取最新轨迹点）
            latest_track = tracks[0]
            location_str = f"{latest_track['lat']:.4f}, {latest_track['lng']:.4f}"
            
            # 简单的区域判断 (Region) - 暂时留空或保留原值
            region = ship['region'] 
            
            database.update_ship_status(
                mmsi, 
                new_status, 
                datetime.now().isoformat(),
                location_str,
                region
            )
            updated_count += 1
            print(f"[Analysis] Updated {ship['name']} ({mmsi}) -> {new_status}")
            
    return updated_count
