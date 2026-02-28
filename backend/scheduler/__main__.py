import schedule
import time
import asyncio
import main
import reporting.wecom_push as wecom_push
import acquisition.ship_status_fetcher as ship_status_fetcher
import analysis.vessel_analysis as vessel_analysis
from datetime import datetime
import os

LOG_FILE = os.path.join(os.path.dirname(__file__), "scheduler.log")

def write_log(message):
    """写入日志到文件"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}\n"
    print(log_msg.strip())
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_msg)
    except Exception as e:
        print(f"写入日志失败: {e}")

def job_fetch():
    """执行信息抓取任务"""
    write_log("启动抓取任务...")
    try:
        asyncio.run(main.main())
        write_log("抓取任务完成")
    except Exception as e:
        write_log(f"抓取任务出错: {e}")

def job_push():
    """执行推送任务"""
    write_log("启动推送任务...")
    try:
        wecom_push.push_daily_report()
        write_log("推送任务完成")
    except Exception as e:
        write_log(f"推送任务出错: {e}")

def job_ship_tracker():
    """执行船舶追踪与分析任务"""
    write_log("启动船舶追踪任务...")
    try:
        ship_status_fetcher.update_ship_statuses()
        updated = vessel_analysis.analyze_and_update_all_ships()
        write_log(f"船舶追踪任务完成，分析更新了 {updated} 艘船舶状态")
    except Exception as e:
        write_log(f"船舶追踪任务出错: {e}")

def setup_schedule():
    """注册定时任务"""
    schedule.every().day.at("00:00").do(job_fetch)
    schedule.every().day.at("04:00").do(job_fetch)
    schedule.every().day.at("07:30").do(job_fetch)
    schedule.every().day.at("12:00").do(job_fetch)
    schedule.every().day.at("16:00").do(job_fetch)
    schedule.every().day.at("20:00").do(job_fetch)
    schedule.every().day.at("08:00").do(job_push)
    schedule.every().day.at("18:00").do(job_push)
    # 修改为每 1 分钟运行一次
    schedule.every(5).minutes.do(job_ship_tracker)

def main_entry():
    """启动调度器主循环"""
    setup_schedule()
    print("=== 疏浚情报定时任务系统启动 ===")
    print("计划任务:")
    print("- 采集: 00:00, 04:00, 07:30, 0:00, 12:00, 16:00, 20:00")
    print("- 推送: 08:00, 18:00")
    print("- 追踪: 每 5 分钟")
    print("--------------------------------")
    print("系统正在运行中 (Ctrl+C 停止)...")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main_entry()
