#!/usr/bin/env python3
"""
雪球股票讨论获取工具 - 使用 camofox-browser（唯一方案）

使用方法：
python3 xueqiu_camofox.py --symbol "002595" --name "豪迈科技"

股票代码格式：
- 上海股票：6xxxxxx → 自动添加 SH 前缀
- 深圳股票：0xxxxxx, 3xxxxxx → 自动添加 SZ 前缀
- 北京股票：8xxxxxx → 自动添加 BJ 前缀
- 港股：0xxxxxx, 6xxxxxx → 自动添加 HK 前缀
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
        print("[WARN] Gotify未配置，跳过通知")
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
            if 'id' in result:
                print("[INFO] Gotify通知已发送")
                return True
            else:
                print(f"[WARN] Gotify通知失败: {result}")
                return False
    except Exception as e:
        print(f"[WARN] Gotify通知异常: {e}")
        return False


def trigger_nas_sync():
    """Trigger NAS sync."""
    try:
        import subprocess
        result = subprocess.run(
            ['bash', '/root/.openclaw/workspace/sync-wrapper.sh'],
            capture_output=True,
            text=True,
            timeout=120,
            cwd='/root/.openclaw/workspace'
        )
        if result.returncode == 0:
            print("[INFO] NAS同步已触发")
            return True
        else:
            print(f"[WARN] NAS同步失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"[WARN] NAS同步异常: {e}")
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


def build_stock_symbol(symbol):
    """
    构建雪球股票代码
    
    输入：002595, 600519, 688008
    输出：SZ002595, SH600519, SH688008
    """
    # 如果已经是带前缀的格式，直接返回
    if symbol.startswith(('SH', 'SZ', 'BJ', 'HK')):
        return symbol
    
    # 根据数字前缀判断交易所
    if symbol.startswith('6') or symbol.startswith('688') or symbol.startswith('689'):
        # 上海主板、科创板
        return f"SH{symbol}"
    elif symbol.startswith('0') or symbol.startswith('3') or symbol.startswith('002'):
        # 深圳主板、创业板、中小板
        return f"SZ{symbol}"
    elif symbol.startswith('8') or symbol.startswith('4'):
        # 北京证券交易所
        return f"BJ{symbol}"
    elif symbol.startswith('0') and len(symbol) == 5:
        # 港股
        return f"HK{symbol}"
    else:
        # 默认上海
        return f"SH{symbol}"


def parse_discussions_from_snapshot(snapshot):
    """从camofox快照中解析讨论内容"""
    discussions = []
    
    # 获取快照文本
    snapshot_text = snapshot.get('snapshot', '')
    if not snapshot_text:
        print("[WARN] 快照内容为空")
        return discussions
    
    # 使用正则表达式匹配article标签内的内容
    # 雪球讨论结构：article > link(用户头像) > link(用户名) > link(时间) > text(内容)
    article_pattern = r'article:\s*(.*?)(?=article:|$)'
    articles = re.findall(article_pattern, snapshot_text, re.DOTALL)
    
    for article in articles:
        discussion = {}
        
        # 提取用户名 - 匹配 link "用户名" [e\d+]:\n  - /url: /数字
        user_match = re.search(r'link "([^"]+)" \[e\d+\]:\s*\n\s*- /url: /(\d+)', article)
        if user_match:
            discussion['user'] = user_match.group(1)
            discussion['user_id'] = user_match.group(2)
        
        # 提取时间和来源 - 匹配 link "时间·来源" [e\d+]:
        time_match = re.search(r'link "([^"]+·[^"]+)" \[e\d+\]:', article)
        if time_match:
            time_str = time_match.group(1)
            # 分离时间和来源
            if '·' in time_str:
                parts = time_str.split('·', 1)
                discussion['time'] = parts[0].strip()
                discussion['source'] = parts[1].strip() if len(parts) > 1 else ''
        
        # 提取内容 - 匹配 text: 内容
        text_match = re.search(r'text: ([^\n]+)', article)
        if text_match:
            discussion['text'] = text_match.group(1)
        
        # 提取点赞数 - 匹配 link " 数字"
        like_match = re.search(r'link " (\d+)"', article)
        if like_match:
            discussion['likes'] = int(like_match.group(1))
        
        # 提取转发数
        forward_match = re.search(r'link " (\d+)"', article)
        if forward_match:
            discussion['forwards'] = int(forward_match.group(1))
        
        # 提取评论数
        comment_match = re.search(r'link " (\d+)"', article)
        if comment_match:
            discussion['comments'] = int(comment_match.group(1))
        
        # 提取文章链接
        article_link_match = re.search(r'link \$[^\$]+\$ \[e\d+\]:\s*\n\s*- /url: /(\d+/\d+)', article)
        if article_link_match:
            discussion['article_id'] = article_link_match.group(1)
        
        # 只添加有内容的讨论
        if discussion.get('text') or discussion.get('article_id'):
            discussions.append(discussion)
    
    print(f"[INFO] 从快照解析到 {len(discussions)} 条讨论")
    return discussions


def fetch_stock_discussions(symbol, name, count=20):
    """
    获取股票讨论
    
    Args:
        symbol: 股票代码，如 002595（自动构建为SZ002595）
        name: 股票名称
        count: 获取讨论数量
    
    Returns:
        list: 讨论列表
    """
    # 构建完整股票代码
    full_symbol = build_stock_symbol(symbol)
    print(f"[INFO] 获取 {name}({full_symbol}) 的讨论...")
    
    # 1. 创建 tab 访问雪球页面
    result = camofox_request('POST', '/tabs', {
        'userId': 'xueqiu',
        'sessionKey': full_symbol,
        'url': f'https://xueqiu.com/S/{full_symbol}'
    })
    
    if not result or 'tabId' not in result:
        print("[ERROR] 创建 tab 失败")
        return []
    
    tab_id = result['tabId']
    print(f"[INFO] Tab created: {tab_id}")
    
    # 2. 等待页面加载
    print("[INFO] 等待页面加载...")
    time.sleep(20)
    
    # 3. 尝试关闭可能的广告/登录弹窗
    print("[INFO] 检查并关闭弹窗...")
    # 点击页面空白处或按ESC关闭弹窗
    camofox_request('POST', f'/tabs/{tab_id}/press', {
        'userId': 'xueqiu',
        'key': 'Escape'
    })
    time.sleep(2)
    
    # 4. 滚动页面触发懒加载
    print("[INFO] 滚动页面...")
    for i in range(10):
        camofox_request('POST', f'/tabs/{tab_id}/scroll', {
            'userId': 'xueqiu',
            'direction': 'down',
            'amount': 1500
        })
        time.sleep(5)
        
        # 每滚动3次尝试点击"展开"按钮
        if i % 3 == 0:
            print(f"[INFO] 尝试展开内容 (滚动{i+1}次)...")
            # 尝试点击所有"展开"按钮
            camofox_request('POST', f'/tabs/{tab_id}/evaluate', {
                'userId': 'xueqiu',
                'expression': '''() => {
                    const buttons = document.querySelectorAll('a, button, span');
                    for (const btn of buttons) {
                        if (btn.textContent.includes('展开') || btn.textContent.includes('查看更多')) {
                            btn.click();
                        }
                    }
                    return 'clicked';
                }'''
            })
            time.sleep(3)
    
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
    output_path = Path(output_dir).expanduser()
    output_path.mkdir(parents=True, exist_ok=True)
    
    today = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
    safe_name = re.sub(r'[<>"/\\|?*]', '_', stock_name)
    full_symbol = build_stock_symbol(symbol)
    filename = f"{today}_{safe_name}_{full_symbol}_雪球讨论.md"
    file_path = output_path / filename
    
    markdown = f"""---
title: {stock_name}({full_symbol}) - 雪球讨论
date: {today}
source: xueqiu.com
symbol: {full_symbol}
---

# {stock_name}({full_symbol}) - 雪球讨论

**获取时间**: {datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')}
**数据来源**: [雪球网](https://xueqiu.com/S/{full_symbol})
**讨论数量**: {len(discussions)}条

---

"""
    
    for i, disc in enumerate(discussions, 1):
        user = disc.get('user', '未知用户')
        time_str = disc.get('time', '')
        source = disc.get('source', '')
        text = disc.get('text', '')
        likes = disc.get('likes', 0)
        forwards = disc.get('forwards', 0)
        comments = disc.get('comments', 0)
        article_id = disc.get('article_id', '')
        
        # 构建雪球文章链接
        article_url = f"https://xueqiu.com/{article_id}" if article_id else ""
        
        markdown += f"""### {i}. {user}
**时间**: {time_str} | **来源**: {source} | **点赞**: {likes} | **转发**: {forwards} | **评论**: {comments}

{text[:1000]}{'...' if len(text) > 1000 else ''}

"""
        if article_url:
            markdown += f"[查看原文]({article_url})\n\n"
        
        markdown += "---\n\n"
    
    file_path.write_text(markdown, encoding='utf-8')
    print(f"✅ 已保存: {file_path}")
    return str(file_path)


def main():
    parser = argparse.ArgumentParser(description='雪球股票讨论获取 (camofox版)')
    parser.add_argument('--symbol', required=True, help='股票代码，如 002595（自动识别交易所）')
    parser.add_argument('--name', required=True, help='股票名称，如 豪迈科技')
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
        print("[INFO] 可能原因: 页面结构变化、网络问题")
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
