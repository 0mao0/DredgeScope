import requests
import json
import os
import urllib.parse
from datetime import datetime, timedelta
import config
import database

DEFAULT_CATEGORY = "Project"

CATEGORIES_MAP = {
    "Market": "📈 市场动态",
    "Bid": "💰 中标信息",
    "Project": "🏗️ 项目信息",
    "Equipment": "🛠️ 设备修造",
    "R&D": "🔬 科技研发",
    "Regulation": "⚖️ 技术法规"
}

def get_push_window(now):
    """获取推送窗口的时间范围
    
    早报: 00:00-08:00 -> 昨天18:00 到 今天08:00
    日报: 08:00-18:00 -> 今天08:00 到 今天18:00
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
        label = f"{label_prefix}日报"
    return start_dt, end_dt, label

def normalize_hot_title(title, max_len=10):
    """规范化热门新闻标题长度与格式"""
    if not title:
        return ""
    text = str(title).strip().replace("\n", " ").replace("\r", " ")
    if len(text) <= max_len:
        return text
    return text[:max_len]

def build_hot_news_titles(events, max_items=4, title_max_len=10):
    """构建今日热门新闻标题列表"""
    seen_keys = set()
    titles = []
    has_more = False
    for e in events:
        article_id = e.get("article_id")
        article_url = e.get("article_url")
        dedup_key = article_id if article_id is not None else article_url
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)
        raw_title = e.get("title_cn") or e.get("project_name") or e.get("article_title")
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

def push_daily_report():
    """推送日报到企业微信"""
    now = datetime.now()
    start_dt, end_dt, label = get_push_window(now)
    start_time = start_dt.isoformat()
    end_time = end_dt.isoformat()
    
    events = database.get_events_by_time_range(start_time, end_time)

    # Filter junk (Sync with dashboard.html logic)
    # 过滤掉无效信息，确保推送数量与前端展示一致
    valid_events = []
    for e in events:
        title = (e.get('title_cn') or e.get('article_title') or "").lower()
        cat = e.get('category', DEFAULT_CATEGORY)
        if "back to home" in title or "page not found" in title:
            continue
        valid_events.append(e)
    events = valid_events
    
    if not events:
        print("无新情报，发送空消息通知")
        if config.WECOM_WEBHOOK_URL:
            try:
                # 发送纯文本通知
                payload = {
                    "msgtype": "text",
                    "text": {
                        "content": f"【全球疏浚情报 {label}】\n截至目前，暂无最新情报更新。"
                    }
                }
                requests.post(config.WECOM_WEBHOOK_URL, json=payload)
                print("[Push] 已发送无情报通知")
            except Exception as e:
                print(f"[Push] 发送空消息失败: {e}")
        return

    # 最终决定：直接使用服务器上的静态资源 (假设服务器配置正确)
    # 如果是在本地测试，这个链接可能无法被外网访问，但不影响流程
    cover_image_url = f"{config.BACKEND_URL.rstrip('/')}/assets/draghead.png"
    
    found_cover = False
    for e in events:
        if not found_cover and e.get('screenshot_path'):
            if "127.0.0.1" in config.BACKEND_URL or "localhost" in config.BACKEND_URL:
                pass
            else:
                filename = os.path.basename(e['screenshot_path'])
                encoded_filename = urllib.parse.quote(filename)
                cover_image_url = f"{config.BACKEND_URL.rstrip('/')}/assets/{encoded_filename}"
                found_cover = True

    # 2. 构造 Template Card
    date_str = label
    unique_article_ids = {e.get("article_id") for e in events if e.get("article_id") is not None}
    total_count = len(unique_article_ids)
    
    hot_titles = build_hot_news_titles(events, max_items=4, title_max_len=10)
    v_list = [
        {
            "title": title,
            "desc": ""
        }
        for title in hot_titles
    ]


    # 构造跳转链接 (如果没有配置公网 IP，使用 localhost 也没用，但可以作为占位)
    # 使用 mode=recent 参数，确保用户点击后看到的是推送统计的“最近24小时”数据，而不是自然日数据
    jump_url = f"{config.BACKEND_URL.rstrip('/')}/?mode=recent"
    if "127.0.0.1" in jump_url:
        # 提示用户在本地
        pass

    payload = {
        "msgtype": "template_card",
        "template_card": {
            "card_type": "news_notice",
            "source": {
                "icon_url": "https://cdn-icons-png.flaticon.com/512/2942/2942544.png", # 挖掘机/地球图标
                "desc": "全球疏浚情报",
                "desc_color": 0
            },
            "main_title": {
                "title": f"{date_str}",
                "desc": f"本次更新: {total_count} 条"
            },
            "card_image": {
                "url": cover_image_url,
                "aspect_ratio": 1.3
            },
            "vertical_content_list": v_list,
            "card_action": {
                "type": 1,
                "url": jump_url,
                "appid": "APPID", 
                "pagepath": "PAGEPATH"
            },
            "jump_list": [
                {
                    "type": 1,
                    "url": jump_url,
                    "title": "查看完整 BI 数据大屏"
                }
            ]
        }
    }

    # 3. 发送
    if config.WECOM_WEBHOOK_URL:
        print(f"Pushing to: {config.WECOM_WEBHOOK_URL}")
        try:
            resp = requests.post(config.WECOM_WEBHOOK_URL, json=payload)
            print(f"[Push] 响应: {resp.text}")
            
            # 如果 Template Card 失败 (例如 errcode != 0)，尝试降级为 Text 消息
            resp_json = resp.json()
            if resp_json.get("errcode") != 0:
                print("Template Card 推送失败，尝试降级为 Text 消息...")
                text_content = f"【全球疏浚情报 {date_str}】\n"
                text_content += f"本次更新: {total_count} 条\n\n"
                for v in v_list:
                    text_content += f"{v['title']}\n"
                text_content += f"\n详情请访问: {jump_url}"
                
                text_payload = {
                    "msgtype": "text",
                    "text": {
                        "content": text_content
                    }
                }
                requests.post(config.WECOM_WEBHOOK_URL, json=text_payload)
                
        except Exception as e:
            print(f"[Push] 发送失败: {e}")
    else:
        print("[Push] 未配置 Webhook URL，跳过发送")

if __name__ == "__main__":
    push_daily_report()
