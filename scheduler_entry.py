#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import schedule
import time
import asyncio
import backend.main as main
import backend.reporting.wecom_push as wecom_push
import backend.acquisition.ship_status_fetcher as ship_status_fetcher
import backend.analysis.vessel_analysis as vessel_analysis
from datetime import datetime
import config

LOG_FILE = os.path.join(config.DATA_DIR, 'scheduler.log')

def write_log(message):
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
    write_log("启动船舶追踪任务...")
    try:
        asyncio.run(ship_status_fetcher.fetch_and_update_positions())
        asyncio.run(vessel_analysis.analyze_vessel_data())
        write_log("船舶追踪任务完成")
    except Exception as e:
        write_log(f"船舶追踪任务出错: {e}")

schedule.every().day.at("00:00").do(job_fetch)
schedule.every().day.at("04:00").do(job_fetch)
schedule.every().day.at("07:30").do(job_fetch)
schedule.every().day.at("12:00").do(job_fetch)
schedule.every().day.at("16:00").do(job_fetch)
schedule.every().day.at("20:00").do(job_fetch)

schedule.every().day.at("08:00").do(job_push)
schedule.every().day.at("18:00").do(job_push)

schedule.every().hour.do(job_ship_tracker)

print("--------------------------------")
print("调度器已启动")
print("抓取任务: 00:00, 04:00, 07:30, 12:00, 16:00, 20:00")
print("推送任务: 08:00, 18:00")
print("船舶追踪: 每小时")
print("--------------------------------")
print("系统正在运行中 (Ctrl+C 停止)...")

while True:
    schedule.run_pending()
    time.sleep(60)
