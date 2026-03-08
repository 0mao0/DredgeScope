"""
更新微信Session

需要手动从浏览器获取新的Cookie和Token

步骤:
1. 登录 mp.weixin.qq.com
2. 打开浏览器开发者工具(F12)
3. 刷新页面，找到任意请求
4. 复制Cookie和token参数
5. 运行此脚本更新Session
"""
import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

from acquisition.sources.wechat.wechat_source import WeChatSource


def update_session():
    """更新微信Session"""
    print("=" * 60)
    print("更新微信Session")
    print("=" * 60)
    print()

    # 提示用户输入
    print("请从浏览器开发者工具中获取以下信息:")
    print("1. 登录 mp.weixin.qq.com")
    print("2. 按F12打开开发者工具")
    print("3. 刷新页面，在Network标签找到任意请求")
    print("4. 复制Cookie和token参数")
    print()

    # 使用现有的Session文件作为默认值
    source = WeChatSource()
    default_cookie = source.cookie[:100] + "..." if len(source.cookie) > 100 else source.cookie
    default_token = source.token

    print(f"当前Cookie (前100字符): {default_cookie if default_cookie else '无'}")
    print(f"当前Token: {default_token if default_token else '无'}")
    print()

    # 获取新凭证
    cookie = input("请输入新的Cookie (或按Enter保持当前): ").strip()
    token = input("请输入新的Token (或按Enter保持当前): ").strip()

    # 如果用户没有输入，保持原值
    if not cookie:
        cookie = source.cookie
        print("保持当前Cookie")
    if not token:
        token = source.token
        print("保持当前Token")

    if not cookie or not token:
        print("❌ Cookie和Token不能为空!")
        return

    # 更新Session
    print("\n正在更新Session...")
    source.set_auth(cookie, token)

    # 验证
    print("\n正在验证Session...")
    import asyncio

    async def test_fetch():
        try:
            items = await source.fetch_by_biz("MzI1NzYwNTQ5Ng==", count=1)
            return items
        except Exception as e:
            print(f"验证失败: {e}")
            return []

    items = asyncio.run(test_fetch())

    if items:
        print(f"✅ Session更新成功!")
        print(f"📝 测试采集到文章: {items[0]['title'][:50]}...")
    else:
        print("❌ Session可能已失效，无法采集文章")
        print("提示: 请确保Cookie和Token是最新的")


if __name__ == "__main__":
    update_session()
