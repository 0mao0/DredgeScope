import asyncio
import logging
from acquisition.wechat_acquisition import wechat_scraper

# 设置日志
logging.basicConfig(level=logging.INFO)

async def test_wechat():
    # 用户提供的 Cookie 和 Token
    cookie = "annual_review_dialog=1; appmsglist_action_3926441091=card; pac_uid=0_rtjyZ2hszQmiR; omgid=0_rtjyZ2hszQmiR; _qimei_uuid42=1a216121f0510069894d022c4bb9cab352474487d3; _qimei_fingerprint=f68a77ee33e57aef0f0bbe0cc32345de; _qimei_h38=2fd2e029894d022c4bb9cab30200000441a216; _qimei_q32=f57391af57510d650a9780ef28f9f0c8; _qimei_q36=71cdafc47703fd5f7f0ea206300016c1941e; rewardsn=; wxtokenkey=777; ua_id=PIovFYxdb4CtCYcGAAAAAGwjMlFzND6sHY-v_wIYhso=; _clck=vq5oi5|1|g3x|0; wxuin=72207368736061; uuid=b95f548fb33ea3ec65079ead810296e0; rand_info=CAESIJEw5CNxF8c2Lav71vck9JRBtcFXkmoBswBo9gWOyXbr; slave_bizuin=3926441091; data_bizuin=3926441091; bizuin=3926441091; data_ticket=waubZ3Atudyv/ZXTf0qjg7o0oVGqFzXumzO47DFZKPxuFYC/9del1v7qrx9nOyrT; slave_sid=d3l3VlU2SGVqaG5udlR1aHhZTVpNeHI3RXRHSWxYVzZTTFJjN0V2QVJqWGF0b1FSNVFLNUlXUkJmUXpvYlBPRnFyQU9sZEthN2FxX0VIb1J0Ykk4WEpvR2N4Z3lRS3lsdXBWSXhIOF80d25HM3ZtNVVNSUZzN1FBOHJ6a21ZRzZHOFN0dHU3NVJ5NWJoZ2hz; slave_user=gh_383f402641cb; xid=9b00fc5c94ada1d119e01d08c4e9c62f; mm_lang=zh_CN; _clsk=1fh0k1e|1772207399866|3|1|mp.weixin.qq.com/weheat-agent/payload/record"
    token = "1270342123"
    
    # 设置认证
    wechat_scraper.set_auth(cookie=cookie, token=token)
    
    # 用户 URL 中的 fakeid
    user_fakeid = "MzI1NzYwNTQ5Ng==" 
    
    print(f"正在尝试采集 fakeid={user_fakeid} 的文章...")
    articles = wechat_scraper.get_articles_by_biz(user_fakeid, count=3)
    
    if articles:
        print("采集成功！前 3 篇文章：")
        for i, a in enumerate(articles, 1):
            print(f"{i}. {a['title']} ({a['date']})")
    else:
        print("采集失败，请检查 Cookie 或 Token 是否已过期。")

if __name__ == "__main__":
    asyncio.run(test_wechat())
