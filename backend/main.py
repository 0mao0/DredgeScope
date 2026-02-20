import asyncio
import acquisition.info_acquisition as info_acquisition
import analysis.info_analysis as info_analysis
import reporting.report_generation as report_generation
import config
import os
from datetime import datetime

import database

# 垃圾过滤关键词配置
JUNK_TITLES_EXACT = {
    "重回主页", "董事会", "监事会", "股东大会", "首页", "主页", 
    "Home", "Back to Home", "Login", "Sign in", "Register",
    "About Us", "Contact Us", "Site Map", "Privacy Policy",
    "Terms of Use", "Search", "Menu", "Navigation",
    "English", "Español", "Français", "Deutsch", "中文",
    "Skip to main content", "ENTER YOUR ADMIN USERNAME", 
    "Back to Home", "Login", "Sign in", "Register", "Site Map", "Contact Us",
    "Search", "Menu", "Navigation", "Privacy Policy", "Terms of Use"
}

# 移除激进的关键词过滤，防止误删正常新闻（如"董事会"可能是一条任命新闻）
# 仅保留极少数绝对的系统级错误提示
JUNK_KEYWORDS_PARTIAL = [
    "404 Not Found", "Page Not Found", "Access Denied",
    "Browser Update", "Enable JavaScript"
]

def is_valid_article(item):
    """
    第一层粗筛：仅过滤绝对确定的垃圾（如Login页、404页）
    不确定的内容（如'Board of Directors'）全部放行给AI层判断
    """
    title = item.get('title', '').strip()
    link = item.get('link', '').strip()
    
    # 1. 基础非空检查
    if not title or not link:
        return False
    
    # 2. 长度检查 (极短的通常是导航)
    if len(title) < 3: 
        return False
        
    # 3. 精确匹配绝对垃圾标题
    if title in JUNK_TITLES_EXACT:
        return False
        
    # 4. 包含匹配系统错误信息
    for kw in JUNK_KEYWORDS_PARTIAL:
        if kw.lower() in title.lower():
            return False
            
    # 5. 特殊模式检查
    title_lower = title.lower()
    if title_lower.startswith("back to") and len(title) < 20: # 只有短的"Back to..."才是导航
        return False
    if "javascript" in link.lower():
        return False
        
    return True

async def main():
    print(f"=== 疏浚情报极简系统启动 ===")
    print(f"文本模型: {config.TEXT_MODEL}")
    print(f"视觉模型: {config.VL_MODEL}")

    # 简单日志记录
    try:
        log_file = os.path.join(config.DATA_DIR, 'scheduler.log')
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 手动/单次运行 main.py 启动\n")
    except:
        pass

    # 1. 获取信息
    print(">>> 阶段1: 获取信息...")
    raw_items = await info_acquisition.get_all_items()
    print(f"共获取到 {len(raw_items)} 条潜在新闻")
    
    # 去重 & 质量过滤
    items = []
    skipped_count = 0
    for item in raw_items:
        # 质量过滤
        if not is_valid_article(item):
            skipped_count += 1
            continue
            
        # 去重
        if not database.is_article_exists(item['link']):
            items.append(item)
    
    print(f"过滤掉 {skipped_count} 条垃圾/无效信息")
    print(f"经去重后，剩余 {len(items)} 条新文章需处理")

    if not items:
        print("无新文章，任务结束。")
        return

    # 2. 分析信息 (文本 + 视觉)
    print(">>> 阶段2: 智能分析...")
    # 测试时取前 5 条，避免等待太久
    # results = await info_analysis.process_items(items[:5]) 
    results = await info_analysis.process_items(items)

    # 3. 生成报告 & 存储
    print(">>> 阶段3: 生成报告...")
    report_generation.save_history(results)
    report_generation.generate_report(results)
    
    print("=== 任务全部完成 ===")

if __name__ == "__main__":
    asyncio.run(main())
