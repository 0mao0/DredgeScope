# 企业微信推送卡片动态封面绘制模块
"""按推送时段（早报/晚报）实时绘制当日卡片头图封面，带磁盘缓存。

设计：延续静态封面的"深蓝海底 + 耙吸船剪影 + 声呐弧"语言，
早报为暖色日出格调（朝阳），晚报为冷色月夜格调（月亮+星），右上角日期胶囊。
产物缓存在 assets/covers/push_cover_YYYYMMDD_am|pm.jpg，经 /assets 路由公网可达。
绘制失败（无中文字体、Pillow 缺失等）返回 None，由调用方回退静态封面。
"""
import math
import os
from datetime import datetime

W, H = 960, 400
TEXT_MAIN = (245, 249, 252)

# classic 为静态回退封面 backend/static/push_cover.jpg 的原始设计
PALETTES = {
    "classic": {
        "top": (10, 31, 60), "bottom": (17, 64, 95), "accent": (72, 199, 214),
        "sub": (158, 197, 220), "hull": (4, 12, 26), "extra": None,
    },
    "morning": {
        "top": (16, 40, 68), "bottom": (122, 74, 50), "accent": (242, 168, 96),
        "sub": (236, 199, 158), "hull": (10, 16, 26), "extra": "sun",
    },
    "evening": {
        "top": (8, 14, 34), "bottom": (42, 46, 96), "accent": (150, 160, 226),
        "sub": (178, 186, 224), "hull": (4, 8, 20), "extra": "moon",
    },
}

SUB_EN = {
    "classic": "GLOBAL DREDGING INTELLIGENCE BRIEFING",
    "morning": "GLOBAL DREDGING INTELLIGENCE - MORNING BRIEF",
    "evening": "GLOBAL DREDGING INTELLIGENCE - EVENING BRIEF",
}


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def find_font(bold, size):
    """按候选路径查找可用 TTF/TTC 字体，未找到返回 None（禁止用默认位图字体，中文会变方块）"""
    names = (
        ["msyhbd.ttc", "NotoSansCJK-Bold.ttc", "wqy-zenhei.ttc", "uming.ttc"]
        if bold
        else ["msyh.ttc", "NotoSansCJK-Regular.ttc", "wqy-zenhei.ttc", "uming.ttc"]
    )
    dirs = [
        r"C:\Windows\Fonts",
        "/usr/share/fonts",
        "/usr/share/fonts/truetype",
        "/usr/share/fonts/truetype/arphic",
        "/usr/share/fonts/truetype/arphic-uming",
        "/usr/share/fonts/truetype/wqy",
        "/usr/share/fonts/opentype/noto",
    ]
    for d in dirs:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                try:
                    from PIL import ImageFont

                    return ImageFont.truetype(p, size)
                except Exception:
                    continue
    return None


def _draw_background(img, pal):
    """纵向渐变背景 + 底部三道水纹线"""
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    for y in range(H):
        draw.line([(0, y), (W, y)], fill=_lerp(pal["top"], pal["bottom"], y / H))
    for i, (amp, base) in enumerate([(10, 330), (14, 352), (18, 372)]):
        pts = []
        for x in range(0, W + 1, 8):
            y = base + amp * math.sin((x / W) * math.pi * (3 + i) + i * 1.7)
            pts.append((x, y))
        draw.line(pts, fill=_lerp(pal["bottom"], pal["accent"], 0.12 + 0.09 * i), width=2)


def _draw_sonar_arcs(img, pal):
    """右侧声呐同心弧"""
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    cx, cy = W - 130, 40
    for i, r in enumerate(range(60, 340, 46)):
        draw.arc(
            [cx - r, cy - r, cx + r, cy + r],
            start=95, end=185,
            fill=_lerp(pal["top"], pal["accent"], max(0.12, 0.42 - i * 0.06)),
            width=2,
        )


def _draw_dredger(img, pal):
    """右下角耙吸挖泥船剪影：船体 + 斜伸耙臂与耙头"""
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    hull = pal["hull"]
    draw.polygon([(400, 300), (760, 300), (732, 336), (436, 336)], fill=hull)
    draw.rectangle([660, 268, 720, 300], fill=hull)
    draw.rectangle([672, 252, 700, 268], fill=hull)
    for i in range(3):
        draw.rectangle([676 + i * 9, 258, 681 + i * 9, 263], fill=pal["accent"])
    draw.line([(428, 302), (266, 366)], fill=hull, width=10)
    draw.ellipse([250, 356, 284, 380], fill=hull)
    draw.line([(258, 378), (238, 392)], fill=hull, width=5)
    draw.line([(274, 378), (294, 392)], fill=hull, width=5)
    draw.line([(580, 300), (360, 330)], fill=hull, width=3)
    for x in range(360, 416, 12):
        draw.line([(x, 344 + (x % 24) / 6), (x + 6, 344 + (x % 24) / 6)], fill=pal["accent"], width=2)


def _draw_extra(img, pal, extra):
    """时段装饰：早报朝阳（左侧地平线半圆）、晚报月亮+星"""
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    if extra == "sun":
        draw.ellipse([96, 276, 236, 416], fill=_lerp(pal["accent"], (255, 230, 180), 0.35))
        draw.ellipse([116, 296, 216, 396], fill=pal["accent"])
    elif extra == "moon":
        draw.ellipse([620, 52, 660, 92], fill=_lerp(pal["sub"], (255, 255, 255), 0.6))
        for (sx, sy, r) in [(560, 40, 2), (600, 124, 2), (540, 150, 1), (648, 158, 2), (580, 100, 1)]:
            draw.ellipse([sx - r, sy - r, sx + r, sy + r], fill=_lerp(pal["sub"], (255, 255, 255), 0.5))


def _draw_texts(img, pal, label, slot):
    """主副标题、装饰线、角标；label 非空时右上角加日期胶囊"""
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    f_title, f_sub, f_tag = find_font(True, 66), find_font(False, 24), find_font(False, 18)
    f_pill = find_font(False, 22)
    if None in (f_title, f_sub, f_tag, f_pill):
        raise RuntimeError("未找到可用的中文字体，放弃动态封面")

    draw.text((64, 92), "全球疏浚情报", font=f_title, fill=TEXT_MAIN)
    draw.rectangle([40, 96, 48, 158], fill=pal["accent"])
    x = 64
    for ch in SUB_EN[slot]:
        draw.text((x, 184), ch, font=f_sub, fill=pal["sub"])
        x += draw.textlength(ch, font=f_sub) + 4
    draw.line([(64, 232), (300, 232)], fill=pal["accent"], width=3)
    tag = "DredgeScope"
    tw = draw.textlength(tag, font=f_tag)
    draw.text((W - tw - 40, H - 44), tag, font=f_tag, fill=pal["sub"])

    if label:
        lw = draw.textlength(label, font=f_pill)
        px0, py0, px1, py1 = W - lw - 96, 24, W - 40, 68
        draw.rounded_rectangle([px0, py0, px1, py1], radius=22,
                               fill=_lerp(pal["top"], pal["bottom"], 0.6),
                               outline=pal["accent"], width=2)
        draw.text((px0 + 28, py0 + 10), label, font=f_pill, fill=TEXT_MAIN)


def draw_cover(slot, label):
    """绘制一幅封面图，字体缺失抛 RuntimeError"""
    from PIL import Image

    pal = PALETTES[slot]
    img = Image.new("RGB", (W, H))
    _draw_background(img, pal)
    _draw_sonar_arcs(img, pal)
    _draw_extra(img, pal, pal["extra"])
    _draw_dredger(img, pal)
    _draw_texts(img, pal, label, slot)
    return img


def ensure_dynamic_cover(label, now=None):
    """按标签（含"早报/晚报"）生成或复用当日封面，返回 assets 相对路径；失败返回 None"""
    import config

    now = now or datetime.now()
    slot = "morning" if "早报" in (label or "") else "evening"
    suffix = "am" if slot == "morning" else "pm"
    fname = f"push_cover_{now.strftime('%Y%m%d')}_{suffix}.jpg"
    cover_dir = os.path.join(config.ASSETS_DIR, "covers")
    target = os.path.join(cover_dir, fname)
    rel = f"assets/covers/{fname}"
    try:
        if os.path.isfile(target):
            return rel
        img = draw_cover(slot, label or "")
        os.makedirs(cover_dir, exist_ok=True)
        img.save(target, "JPEG", quality=88, optimize=True, progressive=True)
        print(f"[Push:封面] 动态封面 {rel} ({os.path.getsize(target) // 1024} KB)")
        return rel
    except Exception as e:
        print(f"[Push:封面] 动态封面生成失败，回退静态: {e}")
        return None
