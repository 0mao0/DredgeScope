
import sqlite3
import os
from datetime import datetime

db_path = os.path.join("backend", "data", "dredge_intel.db")

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check ships table structure
    cursor.execute("PRAGMA table_info(ships)")
    columns = [info[1] for info in cursor.fetchall()]
    print(f"Columns: {columns}")
    
    if 'timestamp' in columns:
        cursor.execute("SELECT mmsi, ship_name, timestamp FROM ships ORDER BY timestamp DESC LIMIT 5")
        rows = cursor.fetchall()
        print("\nTop 5 most recently updated ships:")
        for row in rows:
            print(f"MMSI: {row[0]}, Name: {row[1]}, Time: {row[2]}")
    else:
        print("Timestamp column not found in ships table.")
        
    conn.close()

except Exception as e:
    print(f"Error: {e}")
