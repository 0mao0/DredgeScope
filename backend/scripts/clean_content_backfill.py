"""历史文章 AI 正文清洗补跑脚本（手动执行，不纳入调度）"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import database
from analysis import info_analysis
from openai import AsyncOpenAI


async def run_backfill(limit=None, ids=None):
    """
    对未清洗文章执行 AI 正文清洗并回写

    Args:
        limit: 最多清洗篇数；None 表示不限
        ids: 指定文章 ID 列表；优先于 limit

    Returns:
        统计字典 {"total", "cleaned", "failed"}
    """
    if not config.TEXT_LLM_API_KEY:
        print("[Backfill] TEXT_LLM_API_KEY 未配置，退出")
        return {"total": 0, "cleaned": 0, "failed": 0}

    client = AsyncOpenAI(api_key=config.TEXT_LLM_API_KEY, base_url=config.TEXT_LLM_API_BASE)
    items = database.get_articles_by_ids(ids) if ids else database.get_articles_need_clean(limit=limit)
    total = len(items)
    cleaned = 0
    failed = 0
    sem = asyncio.Semaphore(3)

    async def worker(item):
        nonlocal cleaned, failed
        async with sem:
            text = await info_analysis.clean_content_with_llm(client, item)
            if text:
                database.update_content_clean(item["id"], text)
                cleaned += 1
            else:
                failed += 1

    await asyncio.gather(*(worker(item) for item in items))
    print(f"[Backfill] 共 {total} 篇，清洗成功 {cleaned}，失败/跳过 {failed}")
    return {"total": total, "cleaned": cleaned, "failed": failed}


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="历史文章 AI 正文清洗补跑")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--limit", type=int, default=100, help="最多清洗篇数（默认 100）")
    group.add_argument("--all", action="store_true", help="清洗全部未清洗文章")
    group.add_argument("--ids", type=str, default="", help="指定文章 ID，逗号分隔")
    args = parser.parse_args()

    ids = [int(x) for x in args.ids.split(",") if x.strip()] if args.ids else None
    if ids or args.all:
        limit = None
    else:
        limit = args.limit

    asyncio.run(run_backfill(limit=limit, ids=ids))


if __name__ == "__main__":
    main()
