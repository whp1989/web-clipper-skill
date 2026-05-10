#!/usr/bin/env python3
"""
雪球股票讨论获取工具 - 使用 camofox-browser

使用方法：
python3 xueqiu_camofox.py --symbol "SH688008" --name "澜起科技"
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import urllib.request
import urllib.error

# Configuration
OUTPUT_BASE = Path("~/.openclaw/workspace/syncthing/raw").expanduser()
CAMOFOX_URL = "http://localhost:9377"


def load_api_config():
    """Load API config from local file."""
    config_paths = [
        Path("~/.openclaw/workspace/.openclaw/api-config.json").expanduser(),
        Path("~/.openclaw/api-config.json").expanduser(),
    ]
    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                continue
    return {}


def gotify_notify(title, message, priority=5):
    """Send Gotify notification."""
    config = load_api_config()
    server = config.get('gotify_server')
    token = config.get('gotify_token')
    if not server or not token:
        return False
    try:
        import urllib.request
        import urllib.parse
        url = f"{server}/message?token={token}"
        data = urllib.parse.urlencode({
            'title': title,
            'message': message,
            'priority': priority
        }).encode('utf-8')
        req = urllib.request.Request(url, data=data, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode('utf-8'))
            return 'id' in result
    except:
        return False


def trigger_nas_sync():
    """Trigger NAS sync."""
    try:
        import subprocess
        subprocess.run(
            ['bash', '/root/.openclaw/workspace/sync-wrapper.sh'],
            capture_output=True,
            text=True,
            timeout=120,
            cwd='/root/.openclaw/workspace'
        )
        return True
    except:
        return False


def camofox_request(method, path, data=None):
    """Make request to camofox API."""
    url = f"{CAMOFOX_URL}{path}"
    headers = {'Content-Type': 'application/json'}
    
    if data:
        data = json.dumps(data).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print(f"[ERROR] HTTP {e.code}: {e.read().decode('utf-8')}")
        return None
    except Exception as e:
        print(f"[ERROR] Request failed: {e}")
        return None


def import_cookies():
    """导入雪球 Cookie"""
    cookie_file = Path('/tmp/xueqiu_cookies.json')
    if not cookie_file.exists():
        print("[WARN] Cookie 文件不存在，跳过导入")
        return False
    
    try:
        with open(cookie_file, 'r') as f:
            cookies = json.load(f)
        
        # 添加必要的字段
        for c in cookies:
            c['sameSite'] = 'Lax'
            c['httpOnly'] = False
            c['secure'] = True
        
        # 使用 camofox API 设置 cookies
        result = camofox_request('POST', '/sessions/xueqiu/cookies', {
            'cookies': cookies
        })
        
        if result and result.get('ok'):
            print(f"[INFO] Cookie 导入成功: {result.get('count', 0)} 个")
            return True
        else:
            print("[WARN] Cookie 导入失败")
            return False
    except Exception as e:
        print(f"[WARN] Cookie 导入异常: {e}")
        return False


def parse_discussions_from_snapshot(snapshot):
    """从快照中解析讨论内容"""
    discussions = []
    
    # 获取快照文本
    snapshot_text = snapshot.get('snapshot', '')
    if not snapshot_text:
        print("[WARN] 快照内容为空")
        return discussions
    
    # 使用正则表达式匹配文章/讨论
    # 匹配模式：article 标签内的内容
    article_pattern = r'article:\s*(.*?)(?=article:|$)'
    articles = re.findall(article_pattern, snapshot_text, re.DOTALL)
    
    for article in articles:
        discussion = {}
        
        # 提取用户名
        user_match = re.search(r'link "([^"]+)" \[e\d+\]:\s*\n\s*- /url: /\d+', article)
        if user_match:
            discussion['user'] = user_match.group(1)
        
        # 提取时间和来源
        time_match = re.search(r'link "(\d+分钟前|.*?·.*?)" \[e\d+\]:', article)
        if time_match:
            discussion['time'] = time_match.group(1)
        
        # 提取内容
        text_match = re.search(r'text: ([^\n]+)', article)
        if text_match:
            discussion['text'] = text_match.group(1)
        
        # 提取点赞数
        like_match = re.search(r'link " (\d+)"', article)
        if like_match:
            discussion['likes'] = int(like_match.group(1))
        
        if discussion:
            discussions.append(discussion)
    
    print(f"[INFO] 解析到 {len(discussions)} 条讨论")
    return discussions


def fetch_stock_discussions(symbol, name, count=20):
    """
    获取股票讨论
    
    Args:
        symbol: 股票代码，如 SH688008
        name: 股票名称
        count: 获取讨论数量
    
    Returns:
        list: 讨论列表
    """
    print(f"[INFO] 获取 {name}({symbol}) 的讨论...")
    
    # 1. 导入 Cookie（如果存在）
    import_cookies()
    
    # 2. 创建 tab 访问雪球页面
    result = camofox_request('POST', '/tabs', {
        'userId': 'xueqiu',
        'sessionKey': symbol,
        'url': f'https://xueqiu.com/S/{symbol}'
    })
    
    if not result or 'tabId' not in result:
        print("[ERROR] 创建 tab 失败")
        return []
    
    tab_id = result['tabId']
    print(f"[INFO] Tab created: {tab_id}")
    
    # 3. 等待页面加载（增加等待时间）
    print("[INFO] 等待页面加载...")
    time.sleep(20)
    
    # 4. 滚动页面触发懒加载
    print("[INFO] 滚动页面...")
    for i in range(8):
        camofox_request('POST', f'/tabs/{tab_id}/scroll', {
            'userId': 'xueqiu',
            'direction': 'down',
            'amount': 1200
        })
        time.sleep(5)
    
    # 5. 获取页面快照
    print("[INFO] 获取页面快照...")
    snapshot = camofox_request('GET', f'/tabs/{tab_id}/snapshot?userId=xueqiu')
    
    if not snapshot:
        print("[ERROR] 获取快照失败")
        return []
    
    print(f"[INFO] 快照获取成功，URL: {snapshot.get('url', 'N/A')}")
    print(f"[INFO] 快照长度: {snapshot.get('totalChars', 0)} 字符")
    
    # 6. 解析讨论内容
    discussions = parse_discussions_from_snapshot(snapshot)
    
    # 7. 关闭 tab
    camofox_request('DELETE', f'/tabs/{tab_id}', {'userId': 'xueqiu'})
    
    return discussions


def save_to_markdown(stock_name, symbol, discussions, output_dir):
    """保存到Markdown文件"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    today = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
    safe_name = re.sub(r'[<>":/\\|?*]', '_', stock_name)
    filename = f"{today}_{safe_name}_{symbol}_雪球讨论.md"
    file_path = output_path / filename
    
    markdown = f"""---
title: {stock_name}({symbol}) - 雪球讨论
date: {today}
source: xueqiu.com
symbol: {symbol}
---

# {stock_name}({symbol}) - 雪球讨论

**获取时间**: {datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')}
**数据来源**: [雪球网](https://xueqiu.com/S/{symbol})
**讨论数量**: {len(discussions)}条

---

"""
    
    for i, disc in enumerate(discussions, 1):
        user = disc.get('user', '未知用户')
        time_str = disc.get('time', '')
        text = disc.get('text', '')
        likes = disc.get('likes', 0)
        
        markdown += f"""### {i}. {user}
**时间**: {time_str} | **点赞**: {likes}

{text[:500]}{'...' if len(text) > 500 else ''}

---

"""
    
    file_path.write_text(markdown, encoding='utf-8')
    print(f"✅ 已保存: {file_path}")
    return str(file_path)


def main():
    parser = argparse.ArgumentParser(description='雪球股票讨论获取 (camofox版)')
    parser.add_argument('--symbol', required=True, help='股票代码，如 SH688008')
    parser.add_argument('--name', required=True, help='股票名称，如 澜起科技')
    parser.add_argument('--count', type=int, default=20, help='获取讨论数量（默认20）')
    parser.add_argument('--output', default=str(OUTPUT_BASE), help='输出目录')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("雪球股票讨论获取 (camofox版)")
    print("=" * 60)
    print(f"股票代码: {args.symbol}")
    print(f"股票名称: {args.name}")
    print(f"输出目录: {args.output}")
    
    # 获取讨论
    discussions = fetch_stock_discussions(args.symbol, args.name, args.count)
    
    if not discussions:
        print("\n[WARN] 未获取到任何讨论")
        print("[INFO] 可能原因: 页面结构变化、需要登录或网络问题")
        sys.exit(1)
    
    # 保存到Markdown
    file_path = save_to_markdown(args.name, args.symbol, discussions, args.output)
    
    # 发送通知
    gotify_notify(
        f"雪球讨论: {args.name}",
        f"获取到 {len(discussions)} 条讨论\n文件: {Path(file_path).name}",
        priority=5
    )
    
    # 触发NAS同步
    trigger_nas_sync()
    
    print(f"\n{'=' * 60}")
    print(f"完成！")
    print(f"讨论: {len(discussions)} 条")
    print(f"文件: {file_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
