import sqlite3
import os
import sys

# Add backend directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, 'backend')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import config

DB_PATH = os.path.join(config.DATA_DIR, 'dredge_intel.db')

def add_is_retained_column():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Check if is_retained column exists
    try:
        c.execute("SELECT is_retained FROM articles LIMIT 1")
        print("Column 'is_retained' already exists.")
    except sqlite3.OperationalError:
        print("Column 'is_retained' missing. Adding it...")
        try:
            c.execute("ALTER TABLE articles ADD COLUMN is_retained INTEGER DEFAULT 0")
            print("Successfully added 'is_retained' column.")
        except Exception as e:
            print(f"Failed to add column: {e}")
            
    conn.commit()
    conn.close()

if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        add_is_retained_column()
    else:
        print(f"Database not found at {DB_PATH}")
