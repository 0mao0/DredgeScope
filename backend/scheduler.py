import asyncio
import os
import time
import threading
from datetime import datetime

import acquisition.ship_status_fetcher as ship_status_fetcher
import analysis.ships_status as ships_status
import config
import main
import reporting.wecom_push as wecom_push
import schedule

LOG_FILE = os.path.join(config.DATA_DIR, "scheduler.log")


def write_log(message: str) -> None:
    """写入日志到文件"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}\n"
    print(log_msg.strip())
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_msg)
    except Exception as e:
        print(f"写入日志失败: {e}")


def run_threaded(job_func):
    """在独立线程中运行任务，避免阻塞调度器"""
    job_thread = threading.Thread(target=job_func)
    job_thread.start()


def job_fetch() -> None:
    """执行信息抓取任务"""
    write_log("启动抓取任务...")
    try:
        # 使用 asyncio.run 运行异步主函数
        # 注意：在线程中直接调用 asyncio.run 是安全的，因为它会创建一个新的事件循环
        asyncio.run(main.main())
        write_log("抓取任务完成")
    except Exception as e:
        write_log(f"抓取任务出错: {e}")


def job_push() -> None:
    """执行推送任务"""
    write_log("启动推送任务...")
    try:
        wecom_push.push_daily_report()
        write_log("推送任务完成")
    except Exception as e:
        write_log(f"推送任务出错: {e}")


def job_ship_tracker() -> None:
    """执行船舶追踪与分析任务"""
    write_log("启动船舶追踪任务...")
    try:
        ship_status_fetcher.update_ship_statuses()
        updated = ships_status.update_ships_status_from_tracks()
        write_log(f"船舶追踪任务完成，分析更新了 {updated} 艘船舶状态")
    except Exception as e:
        write_log(f"船舶追踪任务出错: {e}")


def setup_schedule() -> None:
    """注册定时任务"""
    # 抓取任务耗时较长，使用多线程运行，避免阻塞船舶追踪
    schedule.every().day.at("00:00").do(run_threaded, job_fetch)
    schedule.every().day.at("04:00").do(run_threaded, job_fetch)
    schedule.every().day.at("07:30").do(run_threaded, job_fetch)
    schedule.every().day.at("12:00").do(run_threaded, job_fetch)
    schedule.every().day.at("16:00").do(run_threaded, job_fetch)
    schedule.every().day.at("20:00").do(run_threaded, job_fetch)
    
    # 推送任务也建议独立线程
    schedule.every().day.at("08:00").do(run_threaded, job_push)
    schedule.every().day.at("18:00").do(run_threaded, job_push)
    
    # 船舶追踪任务频率高但耗时短，可以直接运行，也可以独立线程（为了保险起见，建议也独立）
    schedule.every(5).minutes.do(run_threaded, job_ship_tracker)


def main_entry() -> None:
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
