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
    if hour < 8:
        start_dt = (now - timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
        end_dt = now.replace(hour=8, minute=0, second=0, microsecond=0)
        label = f"{label_prefix}早报"
    else:
        start_dt = now.replace(hour=8, minute=0, second=0, microsecond=0)
        end_dt = now.replace(hour=18, minute=0, second=0, microsecond=0)
        label = f"{label_prefix}日报"
    return start_dt, end_dt, label

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

    # 1. 统计数据
    # cat_counts = {k: 0 for k in CATEGORIES_MAP.keys()}
    # 新逻辑：按文章去重统计 (用户要求：数量是新闻的数量，而不是events的数量)
    cat_article_ids = {k: set() for k in CATEGORIES_MAP.keys()}
    
    # 分组数据用于详情展示 (取每类最重要的1-2条)
    cat_highlights = {k: [] for k in CATEGORIES_MAP.keys()}
    
    # 最终决定：直接使用服务器上的静态资源 (假设服务器配置正确)
    # 如果是在本地测试，这个链接可能无法被外网访问，但不影响流程
    cover_image_url = f"{config.BACKEND_URL.rstrip('/')}/assets/draghead.png"
    
    found_cover = False

    for e in events:
        cat = e.get('category', DEFAULT_CATEGORY)
        # 兼容性处理：如果 cat 不在 map 中，归为 DEFAULT
        if cat not in cat_article_ids:
            cat = DEFAULT_CATEGORY
        
        # 统计文章ID
        article_id = e.get('article_id')
        if article_id:
            cat_article_ids[cat].add(article_id)
        
        if not found_cover and e.get('screenshot_path'):
            if "127.0.0.1" in config.BACKEND_URL or "localhost" in config.BACKEND_URL:
                pass 
            else:
                filename = os.path.basename(e['screenshot_path'])
                encoded_filename = urllib.parse.quote(filename)
                cover_image_url = f"{config.BACKEND_URL.rstrip('/')}/assets/{encoded_filename}"
                found_cover = True
        
        # 添加到高亮列表 (简单的逻辑：按时间倒序，每类存前3个)
        # 注意：这里需要去重，避免同一篇文章显示多次
        existing_urls = {h['url'] for h in cat_highlights[cat]}
        if len(cat_highlights[cat]) < 3 and e.get('article_url') not in existing_urls:
            # 构造简短描述
            desc = ""
            if cat == 'Bid':
                desc = f"{e.get('location', '')} {e.get('contract_value', '')}"
            elif cat == 'Market':
                desc = f"{e.get('details', {}).get('company_name', '')} {e.get('details', {}).get('trend', '')}"
            elif cat == 'Project':
                desc = f"{e.get('project_status', '')} {e.get('details', {}).get('completion_percentage', '')}"
            else:
                desc = e.get('article_title', '')[:20]
            
            # 清理 desc 中的 None
            desc = desc.replace("None", "").strip()
            
            # 优先使用中文标题 (title_cn > project_name > article_title)
            display_title = e.get('title_cn')
            if not display_title:
                display_title = e.get('project_name') or e.get('article_title')
            
            cat_highlights[cat].append({
                "title": display_title,
                "desc": desc,
                "url": e.get('article_url')
            })

    # 计算最终数量
    cat_counts = {k: len(v) for k, v in cat_article_ids.items()}

    # 2. 构造 Template Card
    date_str = label
    unique_article_ids = {e.get("article_id") for e in events if e.get("article_id") is not None}
    total_count = len(unique_article_ids)
    
    # 构造 vertical_content_list
    v_list = []
    
    # 企业微信限制：news_notice 类型的 vertical_content_list 最多 4 项
    # 我们按数量排序，取前 4 个
    # v_list 已经有了 title 和 desc
    # 我们需要根据 cat_counts 来排序 v_list 吗？
    # v_list 目前是按 map 顺序遍历的。
    # 让我们重新构建 v_list，按数量倒序
    
    # 1. 构造 (count, item) 列表
    sorted_cats = []
    for cat_key in CATEGORIES_MAP.keys():
        cat_name = CATEGORIES_MAP[cat_key]
        count = cat_counts[cat_key]
        if count > 0:
            sorted_cats.append((count, cat_key, cat_name))
    
    # 2. 排序 (count desc)
    sorted_cats.sort(key=lambda x: x[0], reverse=True)
    
    # 3. 取前 4 个 (企业微信限制)
    top_cats = sorted_cats[:4]
    
    # 4. 重新生成 v_list
    v_list = []
    for count, cat_key, cat_name in top_cats:
        # 格式优化：标题后加括号数字
        display_title = f"{cat_name} ({count})"
        
        v_list.append({
            "title": display_title,
            "desc": ""  # 用户要求删除概况详情
        })
        
    # 如果还有更多分类被隐藏
    if len(sorted_cats) > 4:
        # 在最后一个条目或副标题中提示？
        # news_notice 没有 extra footer.
        # 我们可以在 main_title.desc 中提示 "今日更新 X 条 (显示前4类)"
        pass


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
