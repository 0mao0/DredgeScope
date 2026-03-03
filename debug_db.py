import sqlite3
import os
import sys

DB_PATH = r'backend/data/dredge_intel.db'

def run_query(query, params=()):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Error running query '{query}': {e}")
        return []

def print_rows(rows):
    if not rows:
        print("No results.")
        return
    keys = rows[0].keys()
    print(" | ".join(keys))
    for row in rows:
        print(" | ".join(str(row[k]) for k in keys))

print("--- Total Articles ---")
rows = run_query("SELECT COUNT(*) as count FROM articles")
print_rows(rows)

print("\n--- Retained Articles ---")
rows = run_query("SELECT COUNT(*) as count FROM articles WHERE is_retained=1")
print_rows(rows)

print("\n--- Invalid/Suspicious Articles (MailChimp, Correcting) ---")
rows = run_query("SELECT id, title, is_retained, valid, source_name, created_at FROM articles WHERE title LIKE '%MailChimp%' OR title LIKE '%Correcting the Record%'")
print_rows(rows)

print("\n--- Specific Article '鸿浚' ---")
rows = run_query("SELECT id, title, pub_date, is_retained, valid, vl_desc, created_at FROM articles WHERE title LIKE '%鸿浚%'")
print_rows(rows)

print("\n--- Recent 10 Articles ---")
rows = run_query("SELECT id, title, is_retained, valid, created_at FROM articles ORDER BY created_at DESC LIMIT 10")
print_rows(rows)
