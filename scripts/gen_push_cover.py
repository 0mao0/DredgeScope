# 生成企业微信推送统一封面图（960x400，2.4:1）
"""
生成 backend/static/push_cover.jpg —— 企业微信 news 卡片头部大图统一封面。

设计：深蓝渐变海底背景 + 疏浚船耙吸臂剪影 + 声呐弧线纹理，
左侧中文主标题与英文副标题，右下角 DredgeScope 角标。

依赖本机的中文字体（Windows: msyhbd.ttc / msyh.ttc），仅在本地重新设计封面时运行：
    python scripts/gen_push_cover.py
产物提交进仓库，容器运行时不需要字体和 Pillow 参与封面生成。
"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 960, 400
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "backend", "static", "push_cover.jpg")

TOP_COLOR = (10, 31, 60)      # 深海军蓝
BOTTOM_COLOR = (17, 64, 95)   # 海底蓝
ACCENT = (72, 199, 214)       # 青蓝高亮（疏浚/水）
FAINT = (255, 255, 255)
TEXT_MAIN = (245, 249, 252)
TEXT_SUB = (158, 197, 220)


def find_font(bold: bool, size: int):
    """按候选路径查找可用字体（优先中文字体）"""
    names = (
        ["msyhbd.ttc", "msyh.ttc", "NotoSansCJK-Bold.ttc", "wqy-zenhei.ttc"]
        if bold
        else ["msyh.ttc", "NotoSansCJK-Regular.ttc", "wqy-microhei.ttc"]
    )
    dirs = [r"C:\Windows\Fonts", "/usr/share/fonts", "/usr/share/fonts/truetype"]
    for d in dirs:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    continue
    return ImageFont.load_default()


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def draw_background(img: Image.Image):
    """纵向渐变背景 + 底部水纹线"""
    draw = ImageDraw.Draw(img)
    for y in range(H):
        draw.line([(0, y), (W, y)], fill=lerp(TOP_COLOR, BOTTOM_COLOR, y / H))
    # 底部三道水纹线，模拟海面剖视
    for i, (amp, base, alpha_seg) in enumerate([(10, 330, 0.10), (14, 352, 0.18), (18, 372, 0.30)]):
        pts = []
        for x in range(0, W + 1, 8):
            y = base + amp * math.sin((x / W) * math.pi * (3 + i) + i * 1.7)
            pts.append((x, y))
        color = lerp(BOTTOM_COLOR, ACCENT, alpha_seg * 3)
        draw.line(pts, fill=color, width=2)


def draw_sonar_arcs(img: Image.Image):
    """右侧声呐同心弧，象征疏浚测量"""
    draw = ImageDraw.Draw(img)
    cx, cy = W - 130, 40
    for i, r in enumerate(range(60, 340, 46)):
        alpha = max(18, 60 - i * 10)
        color = lerp(BOTTOM_COLOR, ACCENT, alpha / 255 * 2.2)
        draw.arc([cx - r, cy - r, cx + r, cy + r], start=95, end=185, fill=color, width=2)


def draw_dredger(img: Image.Image):
    """左下角耙吸挖泥船剪影：船体 + 斜伸的耙臂与耙头"""
    draw = ImageDraw.Draw(img)
    hull = (4, 12, 26)
    # 船体（甲板线约 y=300）
    draw.polygon(
        [(340, 300), (700, 300), (672, 336), (376, 336)],
        fill=hull,
    )
    # 上层建筑
    draw.rectangle([600, 268, 660, 300], fill=hull)
    draw.rectangle([612, 252, 640, 268], fill=hull)
    # 驾驶台舷窗亮点
    for i in range(3):
        draw.rectangle([616 + i * 9, 258, 621 + i * 9, 263], fill=ACCENT)
    # 耙臂（从船艏斜向下伸到海底）
    draw.line([(368, 302), (206, 366)], fill=hull, width=10)
    # 耙头
    draw.ellipse([190, 356, 224, 380], fill=hull)
    draw.line([(198, 378), (178, 392)], fill=hull, width=5)
    draw.line([(214, 378), (234, 392)], fill=hull, width=5)
    # 耙臂上吊索
    draw.line([(520, 300), (300, 330)], fill=hull, width=3)
    # 船艏激起的水流虚线
    for x in range(300, 356, 12):
        draw.line([(x, 344 + (x % 24) / 6), (x + 6, 344 + (x % 24) / 6)], fill=ACCENT, width=2)


def draw_texts(img: Image.Image):
    """左侧主副标题、装饰线，右下角角标"""
    draw = ImageDraw.Draw(img)
    f_title = find_font(True, 66)
    f_sub = find_font(False, 24)
    f_tag = find_font(False, 18)

    title = "全球疏浚情报"
    draw.text((64, 92), title, font=f_title, fill=TEXT_MAIN)
    # 主标题左侧竖排高亮条
    draw.rectangle([40, 96, 48, 158], fill=ACCENT)
    # 英文副标题（字符间距手动加宽）
    sub = "GLOBAL DREDGING INTELLIGENCE BRIEFING"
    x = 64
    for ch in sub:
        draw.text((x, 184), ch, font=f_sub, fill=TEXT_SUB)
        x += draw.textlength(ch, font=f_sub) + 4
    # 分隔线
    draw.line([(64, 232), (300, 232)], fill=ACCENT, width=3)
    # 右下角角标
    tag = "DredgeScope"
    tw = draw.textlength(tag, font=f_tag)
    draw.text((W - tw - 40, H - 44), tag, font=f_tag, fill=TEXT_SUB)


def main():
    img = Image.new("RGB", (W, H))
    draw_background(img)
    draw_sonar_arcs(img)
    draw_dredger(img)
    draw_texts(img)
    img.save(OUT, "JPEG", quality=88, optimize=True, progressive=True)
    print(f"[Cover] 已生成 {OUT} ({os.path.getsize(OUT) // 1024} KB)")


if __name__ == "__main__":
    sys.exit(main())
