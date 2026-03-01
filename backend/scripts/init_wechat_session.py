import os
import sys
import json

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

from acquisition.wechat_acquisition import wechat_scraper

def init_session():
    # 用户提供的有效凭证
    cookie = "annual_review_dialog=1; appmsglist_action_3926441091=card; pac_uid=0_rtjyZ2hszQmiR; omgid=0_rtjyZ2hszQmiR; _qimei_uuid42=1a216121f0510069894d022c4bb9cab352474487d3; _qimei_fingerprint=f68a77ee33e57aef0f0bbe0cc32345de; _qimei_h38=2fd2e029894d022c4bb9cab30200000441a216; _qimei_q32=f57391af57510d650a9780ef28f9f0c8; _qimei_q36=71cdafc47703fd5f7f0ea206300016c1941e; rewardsn=; wxtokenkey=777; ua_id=PIovFYxdb4CtCYcGAAAAAGwjMlFzND6sHY-v_wIYhso=; _clck=vq5oi5|1|g3x|0; wxuin=72207368736061; uuid=b95f548fb33ea3ec65079ead810296e0; rand_info=CAESIJEw5CNxF8c2Lav71vck9JRBtcFXkmoBswBo9gWOyXbr; slave_bizuin=3926441091; data_bizuin=3926441091; bizuin=3926441091; data_ticket=waubZ3Atudyv/ZXTf0qjg7o0oVGqFzXumzO47DFZKPxuFYC/9del1v7qrx9nOyrT; slave_sid=d3l3VlU2SGVqaG5udlR1aHhZTVpNeHI3RXRHSWxYVzZTTFJjN0V2QVJqWGF0b1FSNVFLNUlXUkJmUXpvYlBPRnFyQU9sZEthN2FxX0VIb1J0Ykk4WEpvR2N4Z3lRS3lsdXBWSXhIOF80d25HM3ZtNVVNSUZzN1FBOHJ6a21ZRzZHOFN0dHU3NVJ5NWJoZ2hz; slave_user=gh_383f402641cb; xid=9b00fc5c94ada1d119e01d08c4e9c62f; mm_lang=zh_CN; _clsk=1fh0k1e|1772207399866|3|1|mp.weixin.qq.com/weheat-agent/payload/record"
    token = "1270342123"
    
    print("正在持久化微信 Session...")
    wechat_scraper.set_auth(cookie, token)
    
    # 验证是否成功
    if os.path.exists(wechat_scraper.session_file):
        print(f"✅ Session 已成功保存到: {wechat_scraper.session_file}")
        
        # 尝试进行一次测试采集
        print("正在尝试测试采集 (中交疏浚)...")
        articles = wechat_scraper.get_articles_by_biz("MzI1NzYwNTQ5Ng==", count=1)
        if articles:
            print(f"🚀 采集成功! 最新文章: {articles[0]['title']}")
        else:
            print("❌ 采集失败，请检查 Cookie 是否已失效。")
    else:
        print("❌ Session 保存失败。")

if __name__ == "__main__":
    init_session()
