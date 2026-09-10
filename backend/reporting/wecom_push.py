import requests
import os
import sys
from dotenv import load_dotenv
from datetime import datetime, timedelta
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
import config
import database

DEFAULT_CATEGORY = "Market"

CATEGORIES_MAP = {
    "Market": "📈 市场动态",
    "Bid": "💰 中标信息",
    "Project": "🏗️ 项目信息",
    "Equipment": "🛠️ 设备修造",
    "R&D": "🔬 科技研发",
    "Regulation": "⚖️ 技术法规"
}

CATEGORY_PRIORITY = ["Bid", "Project", "Equipment", "Regulation", "R&D", "Market"]

def pick_primary_category(categories):
    order = ["Bid", "Project", "Equipment", "Regulation", "R&D", "Market"]
    for key in order:
        if key in categories:
            return key
    return categories[0] if categories else DEFAULT_CATEGORY

def get_scheduler_log_path():
    """获取调度日志文件路径"""
    return os.path.join(config.DATA_DIR, "scheduler.log")


def write_scheduler_log(message):
    """写入调度日志内容"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}\n"
    try:
        with open(get_scheduler_log_path(), "a", encoding="utf-8") as f:
            f.write(log_msg)
    except Exception:
        pass

def post_wecom_webhook(payload, label):
    """发送企业微信 Webhook，并返回解析后的响应字典"""
    if not config.WECOM_WEBHOOK_URL:
        # 尝试重新加载 .env 配置文件
        print(f"[Config] Webhook URL 未找到，尝试重新加载 .env: {config.env_path}")
        load_dotenv(config.env_path, override=True)
        config.WECOM_WEBHOOK_URL = os.getenv("WECOM_WEBHOOK_URL")
        
        if config.WECOM_WEBHOOK_URL:
             print("[Config] 重新加载成功，Webhook URL 已更新")
        else:
             print("[Config] 重新加载失败，Webhook URL 仍为空")

    if not config.WECOM_WEBHOOK_URL:
        write_scheduler_log(f"推送统计: 窗口{label} Webhook未配置")
        return {"errcode": -1, "errmsg": "Webhook未配置"}
    try:
        resp = requests.post(config.WECOM_WEBHOOK_URL, json=payload, timeout=20)
        text = resp.text or ""
        print(f"[Push] HTTP {resp.status_code}: {text}")
        try:
            return resp.json()
        except Exception:
            return {"errcode": -2, "errmsg": "响应非 JSON", "raw": text}
    except Exception as e:
        return {"errcode": -3, "errmsg": f"请求失败: {e}"}

def get_push_window(now):
    """获取推送窗口的时间范围
    
    早报: 00:00-08:00 -> 昨天18:00 到 今天08:00
    晚报: 08:00-18:00 -> 今天08:00 到 今天18:00
    """
    label_prefix = f"{now.month}月{now.day}日"
    hour = now.hour
    if hour <= 8:
        start_dt = (now - timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
        end_dt = now.replace(hour=8, minute=0, second=0, microsecond=0)
        label = f"{label_prefix}早报"
    else:
        start_dt = now.replace(hour=8, minute=0, second=0, microsecond=0)
        end_dt = now.replace(hour=18, minute=0, second=0, microsecond=0)
        label = f"{label_prefix}晚报"
    return start_dt, end_dt, label

def normalize_hot_title(title, max_len=10):
    """规范化热门新闻标题长度与格式"""
    if not title:
        return ""
    text = str(title).strip().replace("\n", " ").replace("\r", " ")
    if len(text) <= max_len:
        return text
    return text[:max_len]

def build_hot_news_titles(articles, max_items=4, title_max_len=10):
    """构建今日热门新闻标题列表"""
    seen_keys = set()
    titles = []
    has_more = False
    for e in articles:
        article_id = e.get("id")
        article_url = e.get("url")
        dedup_key = article_id if article_id is not None else article_url
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)
        raw_title = e.get("title_cn") or e.get("title")
        title = normalize_hot_title(raw_title, max_len=title_max_len)
        if not title:
            continue
        if len(titles) < max_items:
            titles.append(title)
        else:
            has_more = True
            break
    if has_more:
        titles.append("...")
    return titles

def truncate_for_wecom(text, max_chars=40):
    """按字符数截断文本，超出长度时以省略号结尾"""
    if not text:
        return ""
    text = str(text).strip().replace("\n", " ").replace("\r", " ")
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"

def rank_articles_for_push(articles, max_items=5):
    """按重要度分数降序、分类优先级、入库时间倒序排序并截取"""
    def sort_key(article):
        significance = article.get("significance")
        score = significance if isinstance(significance, int) and not isinstance(significance, bool) else -1
        category = article.get("category") or DEFAULT_CATEGORY
        priority = CATEGORY_PRIORITY.index(category) if category in CATEGORY_PRIORITY else len(CATEGORY_PRIORITY)
        created_at = article.get("created_at") or ""
        return (score, -priority, created_at)

    return sorted(articles, key=sort_key, reverse=True)[:max_items]

THUMB_ASPECT = 2.4  # 企业微信卡片配图接近 2.4:1 的横条比例
THUMB_WIDTH = 640   # 缩略图目标宽度（像素）
THUMB_BLANK_STDDEV = 8  # 灰度标准差低于该值视为白图/纯色图，不推送


def _normalize_asset_path(screenshot_path):
    """把截图路径统一为 assets/ 开头的相对路径，空路径返回空字符串"""
    path = str(screenshot_path or "").strip().lstrip("/")
    if not path:
        return ""
    if not path.startswith("assets/"):
        path = f"assets/{path}"
    return path


def ensure_push_thumb(screenshot_path):
    """为推送卡片生成缩略图（裁剪 2.4:1、宽 640、JPEG q70），带磁盘缓存

    Returns:
        str: 缩略图相对路径（assets/thumbs/xxx.jpg），白图/纯色图返回 ""
        None: 无法生成（文件缺失、Pillow 异常等），调用方应回退原图 URL
    """
    rel = _normalize_asset_path(screenshot_path)
    if not rel:
        return None
    src = os.path.normpath(os.path.join(config.DATA_DIR, rel))
    thumb_dir = os.path.join(config.ASSETS_DIR, "thumbs")
    stem = os.path.splitext(os.path.basename(src))[0]
    thumb_file = os.path.join(thumb_dir, f"{stem}.jpg")
    thumb_rel = f"assets/thumbs/{stem}.jpg"
    try:
        if not os.path.isfile(src):
            return None
        if os.path.isfile(thumb_file) and os.path.getmtime(thumb_file) >= os.path.getmtime(src):
            return thumb_rel
        from PIL import Image, ImageStat

        img = Image.open(src).convert("RGB")
        w, h = img.size
        crop_h = min(h, max(1, int(w / THUMB_ASPECT)))
        img = img.crop((0, 0, w, crop_h))
        scale = THUMB_WIDTH / max(1, w)
        if scale < 1:
            img = img.resize((THUMB_WIDTH, max(1, int(crop_h * scale))), Image.LANCZOS)
        stddevs = ImageStat.Stat(img.convert("L")).stddev
        if not stddevs or stddevs[0] < THUMB_BLANK_STDDEV:
            print(f"[Push:缩略图] 跳过白图 {rel} (stddev={stddevs[0] if stddevs else 0:.1f})")
            return ""
        os.makedirs(thumb_dir, exist_ok=True)
        img.save(thumb_file, "JPEG", quality=70, optimize=True, progressive=True)
        print(f"[Push:缩略图] 生成 {thumb_rel} ({os.path.getsize(thumb_file) // 1024} KB)")
        return thumb_rel
    except Exception as e:
        print(f"[Push:缩略图] 生成失败 {rel}: {e}")
        return None


def article_image_url(article, base_url):
    """文章配图的公网 URL：优先缩略图，无法生成时回退原图，白图返回空字符串"""
    thumb = ensure_push_thumb(article.get("screenshot_path"))
    if thumb == "":
        return ""
    path = thumb or _normalize_asset_path(article.get("screenshot_path"))
    if not path:
        return ""
    return f"{base_url.rstrip('/')}/{path}"


def push_cover_picurl(base_url, label=""):
    """头部大图封面 URL：PUSH_COVER_URL 覆盖 > 当日动态封面（早报/晚报双色调） > 静态回退封面"""
    if config.PUSH_COVER_URL:
        return config.PUSH_COVER_URL
    try:
        from reporting import push_cover

        rel = push_cover.ensure_dynamic_cover(label)
        if rel:
            return f"{base_url.rstrip('/')}/{rel}"
    except Exception as e:
        print(f"[Push:封面] 动态封面不可用: {e}")
    return f"{base_url.rstrip('/')}/static/push_cover.jpg"

def build_news_payload(articles, base_url, total_count, label, category_line):
    """构造单条重要新闻消息（news 图文消息），汇总作为第一张，末尾追加查看全部条目

    图片规则：头部大图固定使用统一封面；条目有截图才附带 picurl（优先缩略图，白图不携带）。
    """
    article_items = []
    for article in articles:
        article_id = article.get("id")
        if article_id is None:
            continue
        title = truncate_for_wecom(article.get("title_cn") or article.get("title"), 40)
        description = truncate_for_wecom(article.get("summary_cn") or title, 160)
        item = {
            "title": title or "未命名新闻",
            "description": description,
            "url": f"{base_url.rstrip('/')}/?id={article_id}",
        }
        picurl = article_image_url(article, base_url)
        if picurl:
            item["picurl"] = picurl
        article_items.append(item)
    if not article_items:
        return None
    news_articles = [{
        "title": truncate_for_wecom(f"{label} · 更新 {total_count} 条", 40),
        "description": category_line or f"本次更新 {total_count} 条",
        "url": f"{base_url.rstrip('/')}/?mode=recent",
        "picurl": push_cover_picurl(base_url, label),
    }]
    news_articles.extend(article_items)
    news_articles.append({
        "title": f"查看全部 {total_count} 条 →",
        "description": "进入系统查看完整列表",
        "url": f"{base_url.rstrip('/')}/?mode=recent",
    })
    return {"msgtype": "news", "news": {"articles": news_articles}}

def build_markdown_fallback(label, total_count, category_line, articles, base_url):
    """构造 news 发送失败时的 markdown 降级消息"""
    lines = [f"【全球疏浚情报 {label}】", f"本次更新: {total_count} 条", category_line, ""]
    for article in articles:
        article_id = article.get("id")
        if article_id is None:
            continue
        title = truncate_for_wecom(article.get("title_cn") or article.get("title"), 40)
        lines.append(f"[{title}]({base_url.rstrip('/')}/?id={article_id})")
    lines.append(f"[查看全部 {total_count} 条 →]({base_url.rstrip('/')}/?mode=recent)")
    return {"msgtype": "markdown", "markdown": {"content": "\n".join(lines)}}

def build_push_messages(articles, label, total_count, category_line, base_url):
    """构造本次推送的全部消息（单条 news 列表、降级文本）"""
    top_articles = rank_articles_for_push(articles, max_items=5)
    return {
        "news": build_news_payload(top_articles, base_url, total_count, label, category_line),
        "markdown": build_markdown_fallback(label, total_count, category_line, top_articles, base_url),
    }

def parse_event_datetime(value):
    if not value:
        return None, False
    text = str(value).strip()
    if not text:
        return None, False
    try:
        if "T" in text:
            return datetime.fromisoformat(text), False
        if " " in text and ":" in text:
            return datetime.fromisoformat(text.replace(" ", "T")), False
        return datetime.strptime(text, "%Y-%m-%d"), True
    except Exception:
        return None, False

def filter_events_by_publish_window(events, start_dt, end_dt):
    """根据时间窗口过滤事件，优先保证入库时间在窗口内的记录保留"""
    filtered = []
    for e in events:
        created_dt, created_date_only = parse_event_datetime(e.get("created_at"))
        if created_dt:
            if created_date_only:
                if start_dt.date() <= created_dt.date() <= end_dt.date():
                    filtered.append(e)
                    continue
            else:
                if start_dt <= created_dt <= end_dt:
                    filtered.append(e)
                    continue
        pub_dt, date_only = parse_event_datetime(e.get("pub_date"))
        if not pub_dt:
            pub_dt, date_only = parse_event_datetime(e.get("created_at"))
        if not pub_dt:
            continue
        if date_only:
            if pub_dt.date() < start_dt.date() or pub_dt.date() > end_dt.date():
                continue
        else:
            if pub_dt < start_dt or pub_dt > end_dt:
                continue
        filtered.append(e)
    return filtered

def normalize_title_key(text):
    if not text:
        return ""
    t = str(text).lower()
    stopwords = [
        "集团", "公司", "股份", "有限", "有限公司",
        "达成", "签订", "签署", "修改", "修订", "协议",
        "合作", "宣布", "公告"
    ]
    for w in stopwords:
        t = t.replace(w, "")
    t = "".join(ch for ch in t if ch.isalnum() or '\u4e00' <= ch <= '\u9fff')
    return t

def dedupe_market_events(articles):
    deduped_events = []
    seen_market = set()
    for e in articles:
        if e.get("category") == "Market":
            title_key = normalize_title_key(e.get("title_cn") or e.get("title") or e.get("summary_cn"))
            if not title_key:
                title_key = e.get("url") or e.get("id")
            if title_key and title_key in seen_market:
                continue
            if title_key:
                seen_market.add(title_key)
        deduped_events.append(e)
    return deduped_events

def build_category_counts(articles):
    buckets = {k: set() for k in CATEGORIES_MAP.keys()}
    for e in articles:
        cat = e.get("category") or DEFAULT_CATEGORY
        if cat not in buckets:
            cat = DEFAULT_CATEGORY
        article_id = e.get("id")
        key = article_id if article_id is not None else e.get("url") or e.get("title")
        if key is None:
            continue
        buckets[cat].add(key)
    return {k: len(v) for k, v in buckets.items()}

def push_daily_report():
    """推送日报到企业微信：单条重要新闻消息（汇总作为第一张）"""
    now = datetime.now()
    start_dt, end_dt, label = get_push_window(now)
    start_time = start_dt.isoformat()
    end_time = end_dt.isoformat()

    articles = database.get_articles_by_time_range_strict(start_time, end_time, is_retained=1)
    raw_event_count = len(articles)

    if not articles:
        print("无新情报，发送空消息通知")
        write_scheduler_log(f"推送统计: 窗口{label} 原始记录{raw_event_count} 过滤后0 推送0")
        payload = {
            "msgtype": "text",
            "text": {
                "content": f"【全球疏浚情报 {label}】\n截至目前，暂无最新情报更新。"
            }
        }
        resp_json = post_wecom_webhook(payload, label)
        if resp_json.get("errcode") == 0:
            print("[Push] 已发送无情报通知")
        else:
            print(f"[Push] 无情报通知发送失败: {resp_json}")
        return

    for e in articles:
        e["category"] = pick_primary_category(e.get("categories") or [])

    total_count = len(articles)
    category_counts = build_category_counts(articles)
    category_labels = {
        "Market": "市场",
        "Bid": "中标",
        "Project": "项目",
        "Equipment": "设备",
        "R&D": "研发",
        "Regulation": "法规"
    }
    category_line = " | ".join([f"{category_labels[k]}{category_counts.get(k, 0)}" for k in category_labels.keys() if category_counts.get(k, 0) > 0])
    write_scheduler_log(
        f"推送统计: 窗口{label} 原始记录{raw_event_count} 推送{total_count}"
    )

    base_url = config.PUSH_BASE_URL
    messages = build_push_messages(articles, label, total_count, category_line, base_url)

    # 单条重要新闻消息；失败时降级为 markdown 链接
    news_payload = messages["news"]
    if news_payload:
        resp_json = post_wecom_webhook(news_payload, label)
        if resp_json.get("errcode") != 0:
            print("News 推送失败，尝试降级为 Markdown 消息...")
            fallback_resp = post_wecom_webhook(messages["markdown"], label)
            if fallback_resp.get("errcode") != 0:
                print(f"[Push] 降级 Markdown 推送失败: {fallback_resp}")

if __name__ == "__main__":
    push_daily_report()
