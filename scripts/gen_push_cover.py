# 重新生成静态回退封面 backend/static/push_cover.jpg
"""
用 backend/reporting/push_cover.py 的共享绘制模块重绘"经典深蓝"封面，
作为动态封面不可用（无字体/无 Pillow）时的静态回退图。

依赖本机中文字体，仅在本地调整封面设计时运行：
    python scripts/gen_push_cover.py
产物提交进仓库，容器运行时不需要字体参与封面生成。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from reporting.push_cover import draw_cover  # noqa: E402

OUT = os.path.join(ROOT, "backend", "static", "push_cover.jpg")

if __name__ == "__main__":
    img = draw_cover("classic", "")
    img.save(OUT, "JPEG", quality=88, optimize=True, progressive=True)
    print(f"[Cover] 已生成 {OUT} ({os.path.getsize(OUT) // 1024} KB)")
