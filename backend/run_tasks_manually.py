import sys
import os
import argparse
import asyncio

# 添加当前目录到 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

import scheduler
import config

def run(use_test_source=False):
    print("=== 手动运行采集和推送任务 ===")
    
    # 根据参数选择源文件
    original_sources_file = config.SOURCES_FILE
    if use_test_source:
        config.SOURCES_FILE = os.path.join(current_dir, 'static', 'sources_test.json')
        print(f"使用测试源文件: {config.SOURCES_FILE}")
    else:
        print(f"使用默认源文件: {config.SOURCES_FILE}")
    
    print("\n[1/2] 开始运行采集任务 (job_fetch)...")
    try:
        scheduler.job_fetch()
    except Exception as e:
        print(f"采集任务运行失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 恢复 SOURCES_FILE
        if use_test_source:
            config.SOURCES_FILE = original_sources_file

    print("\n[2/2] 开始运行推送任务 (job_push)...")
    try:
        scheduler.job_push()
        print("推送任务运行完成。")
    except Exception as e:
        print(f"推送任务运行失败: {e}")
        import traceback
        traceback.print_exc()
        
    print("\n=== 任务运行结束 ===")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='手动运行疏浚情报采集和推送任务')
    parser.add_argument('--test', action='store_true', help='使用测试源文件 (sources_test.json) 运行')
    args = parser.parse_args()
    
    run(use_test_source=args.test)
