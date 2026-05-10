#!/usr/bin/env python3
"""
雪球股票信息获取工具 - xueqiu-stock
通过雪球网Cookie获取指定股票的公告和讨论信息，保存为Markdown文件。

使用方法：
1. 首次使用需要提供Cookie
2. Cookie会自动保存到本地文件
3. 后续自动加载使用
4. Cookie过期后需要重新提供
"""

import os
import sys
import json
import re
import time
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests

# Configuration
OUTPUT_BASE = Path("~/.openclaw/workspace/syncthing/raw").expanduser()
MULTIMEDIA_DIR = OUTPUT_BASE / "multimedia"
COOKIE_FILE = Path("~/.openclaw/workspace/.xueqiu_cookies.json").expanduser()
API_CONFIG_PATHS = [
    Path("~/.openclaw/workspace/.openclaw/api-config.json").expanduser(),
    Path("~/.openclaw/api-config.json").expanduser(),
]

# 雪球API配置
XUEQIU_HOME = "https://xueqiu.com"
XUEQIU_API_BASE = "https://xueqiu.com/query/v1/symbol/search/status"

# 请求头模板
HEADERS_TEMPLATE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://xueqiu.com/",
    "Origin": "https://xueqiu.com",
}


def load_api_config():
    """Load API config from local file."""
    for config_path in API_CONFIG_PATHS:
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                continue
    return {}


def gotify_notify(title, message, priority=5):
    """Send Gotify notification using local config."""
    config = load_api_config()
    server = config.get('gotify_server')
    token = config.get('gotify_token')
    
    if not server or not token:
        print(f"  ⚠️ Gotify not configured", file=sys.stderr)
        return False
    
    try:
        url = f"{server}/message?token={token}"
        data = {
            'title': title,
            'message': message,
            'priority': priority
        }
        
        resp = requests.post(url, data=data, timeout=15)
        result = resp.json()
        
        if 'id' in result:
            print(f"  [Gotify] 通知已发送: {title}", file=sys.stderr)
            return True
        else:
            print(f"  [Gotify] 发送失败", file=sys.stderr)
            return False
    except Exception as e:
        print(f"  [Gotify] 异常: {e}", file=sys.stderr)
        return False


def trigger_nas_sync():
    """Trigger NAS sync after successful fetch."""
    print("🔄 Triggering NAS sync...", file=sys.stderr)
    try:
        import subprocess
        sync_result = subprocess.run(
            ['bash', '/root/.openclaw/workspace/sync-wrapper.sh'],
            capture_output=True,
            text=True,
            timeout=120,
            cwd='/root/.openclaw/workspace'
        )
        if sync_result.returncode == 0:
            print("✅ NAS sync triggered", file=sys.stderr)
            return True
        else:
            print(f"⚠️ NAS sync failed: {sync_result.stderr[:200]}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"⚠️ NAS sync trigger failed: {e}", file=sys.stderr)
        return False


def save_cookies(cookies):
    """保存Cookie到文件"""
    try:
        COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, indent=2)
        print(f"[INFO] Cookie已保存到: {COOKIE_FILE}")
    except Exception as e:
        print(f"[WARN] 保存Cookie失败: {e}")


def load_cookies():
    """从文件加载Cookie"""
    if COOKIE_FILE.exists():
        try:
            with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] 加载Cookie失败: {e}")
    return None


def get_session_with_cookies(provided_cookie=None):
    """
    获取带Cookie的session
    
    Args:
        provided_cookie: 用户提供的Cookie字符串（可选）
    
    Returns:
        requests.Session: 带Cookie的session，或None
    """
    session = requests.Session()
    session.headers.update(HEADERS_TEMPLATE)
    
    # 如果提供了Cookie，使用提供的
    if provided_cookie:
        print("[INFO] 使用用户提供的Cookie")
        # 解析Cookie字符串
        cookies = {}
        for item in provided_cookie.split(';'):
            if '=' in item:
                key, value = item.strip().split('=', 1)
                cookies[key] = value
        
        # 设置到session
        session.cookies.update(cookies)
        
        # 保存到文件
        save_cookies(cookies)
        return session
    
    # 尝试加载保存的Cookie
    saved_cookies = load_cookies()
    if saved_cookies:
        print("[INFO] 使用保存的Cookie")
        session.cookies.update(saved_cookies)
        return session
    
    print("[ERROR] 未找到Cookie，请提供Cookie参数")
    return None


def fetch_stock_discussions(session, symbol, max_pages=5):
    """
    获取股票讨论信息
    
    Args:
        session: 带Cookie的requests.Session
        symbol: 股票代码（如 SH002595）
        max_pages: 最大翻页数
    
    Returns:
        list: 讨论列表
    """
    discussions = []
    
    for page in range(1, max_pages + 1):
        print(f"[INFO] 获取第 {page} 页讨论...")
        
        params = {
            "count": 10,
            "comment": 0,
            "symbol": symbol,
            "hl": 0,
            "source": "user",
            "sort": "time",
            "page": page,
        }
        
        try:
            resp = session.get(XUEQIU_API_BASE, params=params, timeout=15)
            
            if resp.status_code == 403:
                print("[WARN] 403 Forbidden，Cookie可能已过期")
                break
            
            if resp.status_code != 200:
                print(f"[WARN] HTTP {resp.status_code}")
                break
            
            # 检查是否是JSON
            try:
                data = resp.json()
            except:
                print("[WARN] 返回的不是JSON，可能是WAF拦截")
                break
            
            if data.get("code") != 200:
                print(f"[WARN] API返回错误: {data.get('message', '未知错误')}")
                break
            
            items = data.get("data", {}).get("items", [])
            if not items:
                print("[INFO] 无更多讨论，结束翻页")
                break
            
            for item in items:
                discussion = {
                    "id": item.get("id"),
                    "title": item.get("title", ""),
                    "text": item.get("text", ""),
                    "created_at": item.get("created_at"),
                    "user": item.get("user", {}).get("screen_name", "未知用户"),
                    "likes": item.get("like_count", 0),
                    "comments": item.get("reply_count", 0),
                    "retweets": item.get("retweet_count", 0),
                }
                discussions.append(discussion)
            
            print(f"[INFO] 第 {page} 页获取 {len(items)} 条讨论")
            
            # 添加延迟避免触发风控
            if page < max_pages:
                time.sleep(1.5)
                
        except Exception as e:
            print(f"[ERROR] 获取讨论失败: {e}")
            break
    
    print(f"[INFO] 共获取 {len(discussions)} 条讨论")
    return discussions


def parse_discussion_to_markdown(discussion):
    """
    将讨论解析为Markdown格式
    
    Args:
        discussion: 讨论字典
    
    Returns:
        str: Markdown内容
    """
    # 清理HTML标签
    text = discussion["text"]
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&amp;', '&')
    
    # 格式化时间
    created_at = discussion.get("created_at", "")
    if created_at:
        try:
            dt = datetime.fromtimestamp(created_at / 1000, tz=timezone(timedelta(hours=8)))
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            time_str = str(created_at)
    else:
        time_str = "未知时间"
    
    markdown = f"""### {discussion.get('title', '无标题')}

**作者**: {discussion['user']} | **时间**: {time_str}
**点赞**: {discussion['likes']} | **评论**: {discussion['comments']} | **转发**: {discussion['retweets']}

{text}

---

"""
    return markdown


def save_discussions_to_file(discussions, stock_name, symbol, output_dir):
    """
    保存讨论到Markdown文件
    
    Args:
        discussions: 讨论列表
        stock_name: 股票名称
        symbol: 股票代码
        output_dir: 输出目录
    
    Returns:
        Path: 保存的文件路径
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 构建文件名: {日期}_{股票名称}_{股票代码}.md
    today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    safe_name = re.sub(r'[<>":/\\|?*]', '_', stock_name)
    filename = f"{today}_{safe_name}_{symbol}.md"
    file_path = output_path / filename
    
    # 构建Markdown内容
    now = datetime.now(timezone(timedelta(hours=8)))
    
    markdown = f"""---
title: {stock_name}({symbol}) - 雪球讨论
date: {today}
source: xueqiu.com
symbol: {symbol}
---

# {stock_name}({symbol}) - 雪球讨论

**获取时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}
**数据来源**: [雪球网](https://xueqiu.com/S/{symbol})
**讨论数量**: {len(discussions)} 条

---

"""
    
    for discussion in discussions:
        markdown += parse_discussion_to_markdown(discussion)
    
    # 写入文件
    file_path.write_text(markdown, encoding='utf-8')
    
    print(f"[SUCCESS] 已保存: {file_path}")
    return file_path


def main():
    parser = argparse.ArgumentParser(description='雪球股票讨论获取工具')
    parser.add_argument('--symbol', type=str, required=True, help='股票代码（如 SH002595）')
    parser.add_argument('--name', type=str, help='股票名称（可选）')
    parser.add_argument('--output', type=str, default=str(OUTPUT_BASE), help='输出目录')
    parser.add_argument('--max-pages', type=int, default=5, help='最大翻页数（默认5）')
    parser.add_argument('--cookie', type=str, help='雪球网Cookie字符串（首次使用需要提供）')
    
    args = parser.parse_args()
    
    symbol = args.symbol
    stock_name = args.name or symbol
    output_dir = args.output
    
    print(f"=" * 60)
    print(f"雪球股票讨论获取")
    print(f"=" * 60)
    print(f"股票代码: {symbol}")
    print(f"股票名称: {stock_name}")
    print(f"输出目录: {output_dir}")
    if args.cookie:
        print(f"Cookie: 用户提供")
    print(f"=" * 60)
    
    # 获取Cookie
    session = get_session_with_cookies(args.cookie)
    if not session:
        print("[ERROR] 无法获取Cookie，退出")
        print("[INFO] 提示: 雪球网需要登录才能获取讨论数据")
        print("[INFO] 请提供Cookie参数: --cookie 'xq_a_token=xxx; xq_r_token=xxx'")
        sys.exit(1)
    
    # 获取讨论
    discussions = fetch_stock_discussions(session, symbol, max_pages=args.max_pages)
    
    if not discussions:
        print("[WARN] 未获取到任何讨论")
        print("[INFO] 可能原因: Cookie无效或已过期，请重新提供Cookie")
        sys.exit(0)
    
    # 保存到文件
    file_path = save_discussions_to_file(discussions, stock_name, symbol, output_dir)
    
    # 发送通知
    gotify_notify(
        f"雪球: {stock_name}",
        f"获取 {len(discussions)} 条讨论\n{file_path}",
        priority=5
    )
    
    # 触发NAS同步
    trigger_nas_sync()
    
    print(f"=" * 60)
    print(f"完成！共保存 {len(discussions)} 条讨论")
    print(f"文件路径: {file_path}")
    print(f"=" * 60)


if __name__ == "__main__":
    main()
