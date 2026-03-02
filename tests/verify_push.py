import sqlite3
import os
import sys
from datetime import datetime

# 添加 backend 到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, '../backend')
sys.path.append(backend_dir)

import database
import config
import scheduler

def run():
    print("=== 验证推送功能 ===")
    
    # 1. 插入测试数据
    conn = sqlite3.connect(database.DB_PATH)
    c = conn.cursor()
    
    test_url = "http://test.com/news/1"
    now = datetime.now()
    
    print(f"插入测试数据: {test_url}, time: {now}")
    
    try:
        # 先删除旧的测试数据（如果存在）
        c.execute("DELETE FROM articles WHERE url = ?", (test_url,))
        
        # 插入新数据
        c.execute('''
            INSERT INTO articles (
                url, title, title_cn, pub_date, source_type, source_name, 
                summary_cn, full_text_cn, content, created_at, valid, is_hidden, category
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            test_url,
            "Test News Title",
            "测试新闻标题",
            now.strftime("%Y-%m-%d"),
            "test",
            "Test Source",
            "这是一条测试新闻摘要。",
            "这是一条测试新闻全文。",
            "Original Content",
            now.isoformat(),
            1,
            0,
            "Market"
        ))
        conn.commit()
        print("测试数据插入成功。")
        
    except Exception as e:
        print(f"插入测试数据失败: {e}")
        conn.close()
        return

    conn.close()

    # 2. 运行推送任务
    print("\n开始运行推送任务...")
    try:
        # 强制配置 Webhook URL 为一个无效地址或者 Mock，以免打扰真实用户
        # 但这里我想看日志输出，所以保留原配置。
        # 如果没有配置 Webhook，wecom_push.py 会打印错误并返回。
        if not config.WECOM_WEBHOOK_URL:
            print("警告: 未配置 WECOM_WEBHOOK_URL，推送将不会实际发送到企业微信。")
        
        scheduler.job_push()
        print("推送任务运行完成。")
        
    except Exception as e:
        print(f"推送任务运行失败: {e}")
        import traceback
        traceback.print_exc()

    # 3. 清理测试数据
    print("\n清理测试数据...")
    conn = sqlite3.connect(database.DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM articles WHERE url = ?", (test_url,))
    conn.commit()
    conn.close()
    print("清理完成。")

if __name__ == "__main__":
    run()
