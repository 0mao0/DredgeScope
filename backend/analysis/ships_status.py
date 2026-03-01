import math
import sqlite3
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import database

KNOTS_TO_MS = 0.514444


def parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    """解析时间字符串为 datetime"""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """计算两点之间的球面距离（米）"""
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def fetch_recent_tracks(conn: sqlite3.Connection, mmsi: str, days: int, limit: int) -> List[Dict]:
    """获取指定 MMSI 最近的轨迹点"""
    start_time = (datetime.now() - timedelta(days=days)).isoformat()
    c = conn.cursor()
    c.execute(
        """
        SELECT lat, lng, speed, heading, status_raw, timestamp
        FROM ship_tracks
        WHERE mmsi = ? AND timestamp >= ?
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (mmsi, start_time, limit),
    )
    rows = c.fetchall()
    tracks = []
    for row in rows:
        tracks.append(
            {
                "lat": row[0],
                "lng": row[1],
                "speed": row[2],
                "heading": row[3],
                "status_raw": row[4],
                "timestamp": row[5],
            }
        )
    return tracks


def compute_speed_series(tracks: List[Dict]) -> List[float]:
    """根据经纬度和时间计算速度序列（m/s）"""
    points = []
    for item in tracks:
        lat = item.get("lat")
        lng = item.get("lng")
        ts = parse_timestamp(item.get("timestamp"))
        if lat is None or lng is None or ts is None:
            continue
        points.append((ts, float(lat), float(lng)))
    points.sort(key=lambda x: x[0])
    speeds = []
    max_speed_ms = 15.0
    for i in range(1, len(points)):
        t1, lat1, lng1 = points[i - 1]
        t2, lat2, lng2 = points[i]
        dt = (t2 - t1).total_seconds()
        if dt <= 0:
            continue
        dist = haversine_meters(lat1, lng1, lat2, lng2)
        speed = dist / dt
        if 0 <= speed <= max_speed_ms:
            speeds.append(speed)
    return speeds


def get_recent_points(tracks: List[Dict], latest_time: datetime, window_hours: int) -> List[Tuple[datetime, float, float]]:
    """获取最近窗口内的轨迹点（时间、纬度、经度）"""
    if window_hours <= 0:
        return []
    window_start = latest_time - timedelta(hours=window_hours)
    points: List[Tuple[datetime, float, float]] = []
    for item in tracks:
        ts = parse_timestamp(item.get("timestamp"))
        lat = item.get("lat")
        lng = item.get("lng")
        if ts is None or lat is None or lng is None:
            continue
        if ts >= window_start:
            points.append((ts, float(lat), float(lng)))
    return points


def is_stationary(
    tracks: List[Dict],
    latest_time: datetime,
    window_hours: int = 3,
    drift_meters: float = 80.0,
    fallback_min_hours: int = 2
) -> bool:
    """判断最近窗口内是否明显移动"""
    points = get_recent_points(tracks, latest_time, window_hours)
    if len(points) >= 2:
        points.sort(key=lambda x: x[0])
        latest_point = points[-1]
        max_dist = 0.0
        for _, lat, lng in points:
            dist = haversine_meters(latest_point[1], latest_point[2], lat, lng)
            if dist > max_dist:
                max_dist = dist
        return max_dist <= drift_meters

    valid_points: List[Tuple[datetime, float, float]] = []
    for item in tracks:
        ts = parse_timestamp(item.get("timestamp"))
        lat = item.get("lat")
        lng = item.get("lng")
        if ts is None or lat is None or lng is None:
            continue
        valid_points.append((ts, float(lat), float(lng)))
    if len(valid_points) < 2:
        return False
    valid_points.sort(key=lambda x: x[0])
    latest_point = valid_points[-1]
    prev_point = valid_points[-2]
    dt_hours = (latest_point[0] - prev_point[0]).total_seconds() / 3600
    if dt_hours < fallback_min_hours:
        return False
    dist = haversine_meters(latest_point[1], latest_point[2], prev_point[1], prev_point[2])
    return dist <= drift_meters


def median_speed_ms(values: List[float]) -> Optional[float]:
    """计算速度序列的稳健中位数（m/s）"""
    if not values:
        return None
    recent = values[-24:] if len(values) > 24 else values
    return float(statistics.median(recent))


def fallback_speed_ms_from_track(tracks: List[Dict]) -> Optional[float]:
    """使用轨迹点 speed 字段作为备用速度（假定为节并转换为 m/s）"""
    speeds = []
    for item in tracks:
        value = item.get("speed")
        if value is None:
            continue
        try:
            speed_kn = float(value)
        except Exception:
            continue
        if speed_kn >= 0:
            speeds.append(speed_kn)
    if not speeds:
        return None
    return float(statistics.median(speeds)) * KNOTS_TO_MS


def classify_status(speed_ms: Optional[float]) -> str:
    """根据速度判定状态"""
    if speed_ms is None:
        return "offline"
    if speed_ms < 0.3:
        return "moored"
    if speed_ms <= 3.0:
        return "dredging"
    return "underway"


def analyze_tracks(tracks: List[Dict], offline_hours: int) -> Tuple[str, Optional[float], Optional[float], Optional[str], Optional[str]]:
    """分析轨迹点并输出状态、速度（节）、航向、位置与时间"""
    if not tracks:
        return "offline", None, None, None, None
    latest = None
    latest_time = None
    for item in tracks:
        ts = parse_timestamp(item.get("timestamp"))
        if ts and (latest_time is None or ts > latest_time):
            latest_time = ts
            latest = item
    if latest_time is None:
        return "offline", None, None, None, None
    if datetime.now() - latest_time > timedelta(hours=offline_hours):
        return "offline", None, latest.get("heading"), None, latest_time.isoformat()
    location = None
    if latest.get("lat") is not None and latest.get("lng") is not None:
        location = f"{float(latest.get('lat')):.6f}, {float(latest.get('lng')):.6f}"
    heading = latest.get("heading")
    if is_stationary(tracks, latest_time, window_hours=2, drift_meters=80.0, fallback_min_hours=2):
        return "moored", 0.0, heading, location, latest_time.isoformat()
    speed_series = compute_speed_series(tracks)
    speed_ms = median_speed_ms(speed_series)
    if speed_ms is None:
        speed_ms = fallback_speed_ms_from_track(tracks)
    status = classify_status(speed_ms)
    if status == "moored" and speed_ms is None:
        speed_ms = 0.0
    speed_kn = speed_ms / KNOTS_TO_MS if speed_ms is not None else None
    return status, speed_kn, heading, location, latest_time.isoformat()


def update_ships_status_from_tracks(days: int = 3, offline_hours: int = 2, limit: int = 2000) -> int:
    """根据 ship_tracks 更新 ships 的状态和速度"""
    database.init_track_db()
    ships = database.get_all_ships()
    updated = 0
    conn = sqlite3.connect(database.TRACK_DB_PATH)
    try:
        for ship in ships:
            mmsi = str(ship.get("mmsi") or "").strip()
            if not mmsi:
                continue
            tracks = fetch_recent_tracks(conn, mmsi, days, limit)
            status, speed_kn, heading, location, status_date = analyze_tracks(tracks, offline_hours)
            location_value = location or ship.get("location")
            status_date_value = status_date or datetime.now().isoformat()
            changed = database.update_ship_status(
                mmsi,
                status,
                status_date_value,
                location_value,
                ship.get("region"),
                speed=speed_kn,
                heading=heading,
            )
            if changed:
                updated += 1
    finally:
        conn.close()
    return updated


def main_entry() -> None:
    """命令行入口"""
    updated = update_ships_status_from_tracks()
    print(f"[ShipsStatus] 更新完成: {updated}")


if __name__ == "__main__":
    main_entry()
