import sqlite3
import os
import sys
import re
from datetime import datetime

# 添加 backend 目录到 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, 'backend')
sys.path.insert(0, backend_dir)

# Try to import config to get DB_PATH, fallback if fails
try:
    import config
    if hasattr(config, 'DB_PATH'):
        DB_PATH = config.DB_PATH
    else:
         DB_PATH = os.path.join(config.DATA_DIR, 'dredge_intel.db')
except (ImportError, AttributeError):
    # Fallback path if config import fails (e.g. run from root)
    DB_PATH = os.path.join(backend_dir, 'data', 'dredge_intel.db')

def clean_database():
    print(f"Connecting to database at {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print(f"Error: Database file not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 1. 定义垃圾词 (扩展列表)
    junk_patterns = [
        "skip to", "back to", "return to", "go to",
        "home", "homepage", "frontpage", "main menu",
        "previous", "next", "read more", "learn more",
        "cookie", "accept", "agree", "privacy policy",
        "terms of", "contact us", "about us",
        "sitemap", "accessibility", "subscribe",
        "board of directors", "management team", "executive team",
        "investor relations", "financial reports",
        "career", "job", "vacancy", "vacancies",
        "mailchimp", "email service", "correcting the record",
        "unsubscribe", "view in browser", "update your preferences",
        "serviced by mailchimp", "browser view", "forward this email"
    ]

    # 2. 获取所有 valid=1 的文章
    # 同时获取 is_retained 为 NULL 的文章，因为我们需要初始化它
    c.execute("SELECT id, title, title_cn, summary_cn, content, is_retained FROM articles WHERE valid = 1")
    rows = c.fetchall()
    
    print(f"Checking {len(rows)} valid articles for junk content...")
    
    junk_count = 0
    retained_count = 0
    
    for row in rows:
        article_id = row['id']
        title = (row['title'] or "").lower()
        title_cn = (row['title_cn'] or "").lower()
        summary = (row['summary_cn'] or "").lower()
        content = (row['content'] or "").lower()
        
        is_junk = False
        reason = ""
        
        # 检查标题和摘要 (英文)
        for pattern in junk_patterns:
            if pattern in title or pattern in summary or pattern in content[:200]: # Check start of content too
                is_junk = True
                reason = f"Matched junk pattern: {pattern}"
                break
        
        # 额外检查：内容过短且包含特定词
        if not is_junk and len(content) < 100 and ("mailchimp" in content or "subscribe" in content):
             is_junk = True
             reason = "Content too short and contains mailchimp/subscribe"

        if is_junk:
            print(f"Marking article {article_id} as invalid: {title[:30]}... Reason: {reason}")
            c.execute("UPDATE articles SET valid = 0, is_retained = 0, is_hidden = 1 WHERE id = ?", (article_id,))
            junk_count += 1
        else:
            # 如果不是垃圾，强制设为 is_retained = 1 (如果之前不是 1)
            # 这样前端才能看到数据
            if row['is_retained'] != 1:
                c.execute("UPDATE articles SET is_retained = 1 WHERE id = ?", (article_id,))
                retained_count += 1

    conn.commit()
    print(f"Finished cleaning. Marked {junk_count} articles as junk. Set {retained_count} articles as retained.")
    
    # 3. 检查“鸿浚”新闻并尝试修复日期
    print("\nChecking for '鸿浚' news...")
    c.execute("SELECT id, title, title_cn, pub_date, created_at, content FROM articles WHERE title LIKE '%鸿浚%' OR title_cn LIKE '%鸿浚%'")
    hongjun_rows = c.fetchall()
    
    for row in hongjun_rows:
        print(f"Found '鸿浚' article: ID={row['id']}, Title={row['title_cn'] or row['title']}, Date={row['pub_date']}")
        
        content = row['content'] or ""
        # 匹配 202x年x月x日 或 x月x日
        # 针对 "1月份" 这种模糊描述，可能无法精确匹配，但可以尝试
        date_match = re.search(r'(\d{4}年)?(\d{1,2})月(\d{1,2})日', content)
        
        new_date = None
        if date_match:
            year_grp = date_match.group(1)
            month_grp = date_match.group(2)
            day_grp = date_match.group(3)
            
            year = year_grp.replace('年', '') if year_grp else str(datetime.now().year)
            # 如果是 1 月，可能是跨年，但这里先假设当年
            
            try:
                new_date = f"{year}-{int(month_grp):02d}-{int(day_grp):02d}"
                print(f"  -> Extracted date from content: {new_date}")
            except ValueError:
                pass
        
        if not new_date:
             # 尝试匹配 "1月" 这种
             month_match = re.search(r'(\d{1,2})月', content)
             if month_match:
                 month = int(month_match.group(1))
                 if month == 1: # 特例处理鸿浚 1月份交付
                     new_date = "2026-01-15" # 假设一个中间日期，或者查找更精确的
                     print(f"  -> Inferred date (Jan): {new_date}")

        if new_date and new_date != row['pub_date']:
            print(f"  -> Updating date to {new_date}")
            c.execute("UPDATE articles SET pub_date = ? WHERE id = ?", (new_date, row['id']))
            conn.commit()

    conn.close()

if __name__ == "__main__":
    clean_database()
