import sqlite3
import os
import sys

# 添加 backend 到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, '../backend')
sys.path.append(backend_dir)

import database

def run():
    print("=== 检查采集结果 ===")
    conn = sqlite3.connect(database.DB_PATH)
    c = conn.cursor()
    
    sources_to_check = ["中国水运报", "DredgeWire", "Dredging Today", "MarineLog", "IADC"]
    
    for source in sources_to_check:
        print(f"\n查询来源: {source}")
        #模糊匹配 source_name
        c.execute("SELECT id, title, source_name, created_at, category, summary_cn FROM articles WHERE source_name LIKE ? ORDER BY created_at DESC LIMIT 5", (f"%{source}%",))
        rows = c.fetchall()
        
        if not rows:
            print(f"  无数据。")
        else:
            for row in rows:
                print(f"  ID: {row[0]}")
                print(f"  Title: {row[1]}")
                print(f"  Source: {row[2]}")
                print(f"  Created: {row[3]}")
                print(f"  Category: {row[4]}")
                print(f"  Summary (前50字): {row[5][:50] if row[5] else '无'}")
                print("-" * 20)

    # 检查所有今天的文章数量
    print("\n=== 今日入库统计 ===")
    c.execute("SELECT source_name, COUNT(*) FROM articles WHERE created_at > date('now', 'start of day') GROUP BY source_name")
    rows = c.fetchall()
    for row in rows:
        print(f"{row[0]}: {row[1]}")

    conn.close()

if __name__ == "__main__":
    run()
