import pandas as pd
import sys
import os
import math

# Ensure backend is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import database

def clean_float_str(val):
    if pd.isna(val):
        return None
    try:
        return str(int(float(val)))
    except:
        return str(val).strip()

def import_ships():
    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ships.csv')
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found")
        return

    try:
        df = pd.read_csv(csv_path, encoding='gbk')
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    ships_to_insert = []
    
    for _, row in df.iterrows():
        mmsi = clean_float_str(row.get('MMSI'))
        imo = clean_float_str(row.get('IMO'))
        name = str(row.get('船名', '')).strip()
        
        if not name or name == 'nan':
            continue

        ship = {
            "mmsi": mmsi,
            "imo": imo,
            "name": name,
            "company": str(row.get('公司', '')).strip(),
            "type": str(row.get('船舶类型', '')).strip(),
            "region": str(row.get('区域', '')).strip(),
            # "location": str(row.get('位置', '')).strip(), # CSV location is text, not lat,lng
            "country": str(row.get('位置', '')).strip(), # Store text location in country for now
            "status": str(row.get('目前状态', '')).strip(),
            "status_date": str(row.get('日期', '')).strip(),
            "remarks": str(row.get('备注', '')).strip() if not pd.isna(row.get('备注')) else ""
        }
        
        # Handle nan strings
        for k, v in ship.items():
            if v == 'nan':
                ship[k] = ""
                
        ships_to_insert.append(ship)

    print(f"Found {len(ships_to_insert)} ships in CSV.")
    
    # Batch upsert
    count = database.upsert_ships(ships_to_insert)
    print(f"Successfully upserted {count} ships.")

if __name__ == "__main__":
    import_ships()
