import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import database

def import_ships_from_csv(csv_path):
    """从 CSV 导入船舶数据到数据库"""
    df = pd.read_csv(csv_path, encoding='gbk')
    
    ships = []
    for _, row in df.iterrows():
        ship = {
            'name': row['船名'] if pd.notna(row['船名']) else '',
            'type': row['船舶类型'] if pd.notna(row['船舶类型']) else '',
            'company': row['公司'] if pd.notna(row['公司']) else '',
            'region': row['区域'] if pd.notna(row['区域']) else '',
            'location': row['位置'] if pd.notna(row['位置']) else '',
            'imo': str(row['IMO']) if pd.notna(row['IMO']) else '',
            'mmsi': str(row['MMSI']) if pd.notna(row['MMSI']) else '',
            'status': row['目前状态'] if pd.notna(row['目前状态']) else '',
            'remarks': row['备注'] if pd.notna(row['备注']) else '',
        }
        ships.append(ship)
    
    database.upsert_ships(ships)
    print(f"[导入完成] 共导入 {len(ships)} 艘船舶")

if __name__ == '__main__':
    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ships.csv')
    import_ships_from_csv(csv_path)
