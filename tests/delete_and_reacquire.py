import sqlite3
import os
import sys
from datetime import datetime
import asyncio

# 添加 backend 到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, '../backend')
sys.path.append(backend_dir)

import database
import config
import scheduler

# 目标 URL (来自之前的查询)
TARGET_URL = "https://www.dredgingtoday.com/2026/02/27/deme-maintains-strong-activity-overseas-in-2025/"

def delete_article(url):
    print(f"尝试删除文章: {url}")
    conn = sqlite3.connect(database.DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM articles WHERE url = ?", (url,))
    changes = conn.total_changes
    conn.commit()
    conn.close()
    return True

def check_article_exists(url):
    conn = sqlite3.connect(database.DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, created_at FROM articles WHERE url = ?", (url,))
    row = c.fetchone()
    conn.close()
    if row:
        print(f"文章存在: ID={row[0]}, Created={row[2]}")
        return True
    else:
        print("文章不存在。")
        return False

def run():
    print("=== 验证采集重新入库功能 ===")
    
    # 1. 确认文章存在
    if not check_article_exists(TARGET_URL):
        print("警告: 目标文章不存在，无法进行删除验证。将尝试直接运行采集。")
    else:
        # 2. 删除文章
        delete_article(TARGET_URL)
        if check_article_exists(TARGET_URL):
            print("错误: 删除失败！")
            return

    # 3. 运行采集任务
    print("\n运行采集任务 (使用 sources_test.json)...")
    
    # 临时替换 sources.json
    original_sources = config.SOURCES_FILE
    config.SOURCES_FILE = os.path.join(current_dir, 'static', 'sources_test.json')
    print(f"Sources: {config.SOURCES_FILE}")
    
    try:
        scheduler.job_fetch()
    except Exception as e:
        print(f"采集任务失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        config.SOURCES_FILE = original_sources

    # 4. 再次检查文章是否存在
    print("\n检查文章是否重新入库...")
    if check_article_exists(TARGET_URL):
        print("验证成功: 文章已被重新采集并入库！")
    else:
        print("验证失败: 文章未被重新采集。可能原因：RSS源中已移除该文章，或网络问题，或被过滤逻辑拦截。")

if __name__ == "__main__":
    run()
