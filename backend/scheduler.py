import schedule
import time
import asyncio
import main
import reporting.wecom_push as wecom_push
import acquisition.ship_status_fetcher as ship_status_fetcher
import analysis.vessel_analysis as vessel_analysis
from datetime import datetime
import sys
import os
import config

# Add backend to path just in case
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

LOG_FILE = os.path.join(config.DATA_DIR, 'scheduler.log')

def write_log(message):
    """写入日志到文件"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{timestamp}] {message}\n"
    print(log_msg.strip())
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_msg)
    except Exception as e:
        print(f"写入日志失败: {e}")

def job_fetch():
    write_log("启动抓取任务...")
    try:
        # Create new event loop for each run if needed, but asyncio.run handles it
        asyncio.run(main.main())
        write_log("抓取任务完成")
    except Exception as e:
        write_log(f"抓取任务出错: {e}")

def job_push():
    write_log("启动推送任务...")
    try:
        wecom_push.push_daily_report()
        write_log("推送任务完成")
    except Exception as e:
        write_log(f"推送任务出错: {e}")

def job_ship_tracker():
    """船舶追踪与分析任务"""
    write_log("启动船舶追踪任务...")
    try:
        # 1. 抓取/更新位置 (如果有数据源)
        ship_status_fetcher.update_ship_statuses()
        
        # 2. 分析轨迹并更新状态
        updated = vessel_analysis.analyze_and_update_all_ships()
        write_log(f"船舶追踪完成，分析更新了 {updated} 艘船舶状态")
    except Exception as e:
        write_log(f"船舶追踪任务出错: {e}")

# 1. 数据采集 (0, 4, 8, 12, 16, 20)
schedule.every().day.at("00:00").do(job_fetch)
schedule.every().day.at("04:00").do(job_fetch)
schedule.every().day.at("08:00").do(job_fetch)
schedule.every().day.at("12:00").do(job_fetch)
schedule.every().day.at("16:00").do(job_fetch)
schedule.every().day.at("20:00").do(job_fetch)

# 2. 数据推送 (08:00, 18:00)
schedule.every().day.at("08:00").do(job_push)
schedule.every().day.at("18:00").do(job_push)

# 3. 船舶追踪 (每小时)
schedule.every().hour.do(job_ship_tracker)

print("=== 疏浚情报定时任务系统启动 ===")
print("计划任务:")
print("- 采集: 00:00, 04:00, 08:00, 12:00, 16:00, 20:00")
print("- 推送: 08:00, 18:00")
print("- 追踪: 每小时")
print("--------------------------------")

# 首次运行提示
print("系统正在运行中 (Ctrl+C 停止)...")

while True:
    schedule.run_pending()
    time.sleep(60)
