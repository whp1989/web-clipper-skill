#!/usr/bin/env python3
"""
雪球股票信息获取工具 - xueqiu-stock (RSSHub版本)
通过RSSHub获取指定股票的公告和讨论信息，保存为Markdown文件。

RSSHub路由:
- 股票信息: https://rsshub.pandaponds/xueqiu/stock_info/{symbol}
- 股票讨论: https://rsshub.pandaponds/xueqiu/stock_comments/{symbol}

源码参考: https://github.com/DIYgod/RSSHub/blob/master/lib/routes/xueqiu/stock-comments.tsx
"""

import os
import sys
import json
import re
import time
import argparse
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path
import xml.etree.ElementTree as ET

# Configuration
OUTPUT_BASE = Path("~/.openclaw/workspace/syncthing/raw").expanduser()
MULTIMEDIA_DIR = OUTPUT_BASE / "multimedia"
API_CONFIG_PATHS = [
    Path("~/.openclaw/workspace/.openclaw/api-config.json").expanduser(),
    Path("~/.openclaw/api-config.json").expanduser(),
]

# RSSHub配置
RSSHUB_BASE = "https://rsshub.pandaponds"


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


def fetch_rss_feed(feed_url, timeout=30):
    """
    Fetch RSS feed from RSSHub.
    
    Args:
        feed_url: RSSHub feed URL
        timeout: Request timeout in seconds
    
    Returns:
        list: RSS items, or None if failed
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/rss+xml, application/xml, text/xml, */*',
    }
    
    try:
        req = urllib.request.Request(feed_url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content = response.read().decode('utf-8')
            
            # Parse XML
            root = ET.fromstring(content)
            
            # Extract items
            items = []
            channel = root.find('channel')
            if channel is not None:
                for item in channel.findall('item'):
                    entry = {
                        'title': item.findtext('title', ''),
                        'link': item.findtext('link', ''),
                        'description': item.findtext('description', ''),
                        'pubDate': item.findtext('pubDate', ''),
                        'author': item.findtext('author', ''),
                    }
                    items.append(entry)
            
            return items
    except urllib.error.URLError as e:
        print(f"[ERROR] RSS fetch failed: {e}", file=sys.stderr)
        return None
    except ET.ParseError as e:
        print(f"[ERROR] XML parse failed: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}", file=sys.stderr)
        return None


def parse_stock_info_items(items):
    """
    Parse stock info items (announcements/bulletins).
    
    Args:
        items: RSS items from stock_info feed
    
    Returns:
        list: Parsed announcement items
    """
    announcements = []
    
    for item in items:
        title = item.get('title', '')
        link = item.get('link', '')
        description = item.get('description', '')
        pub_date = item.get('pubDate', '')
        
        # Parse date
        date_str = ""
        if pub_date:
            try:
                # RSS date format: Mon, 06 Jan 2026 10:00:00 GMT
                dt = datetime.strptime(pub_date, '%a, %d %b %Y %H:%M:%S %Z')
                dt = dt.astimezone(timezone(timedelta(hours=8)))
                date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                date_str = pub_date
        
        announcement = {
            'title': title,
            'link': link,
            'description': description,
            'date': date_str,
            'type': 'announcement',
        }
        announcements.append(announcement)
    
    return announcements


def parse_stock_comments_items(items):
    """
    Parse stock comments items (discussions).
    
    Args:
        items: RSS items from stock_comments feed
    
    Returns:
        list: Parsed discussion items
    """
    discussions = []
    
    for item in items:
        title = item.get('title', '')
        link = item.get('link', '')
        description = item.get('description', '')
        pub_date = item.get('pubDate', '')
        author = item.get('author', '未知用户')
        
        # Parse date
        date_str = ""
        if pub_date:
            try:
                dt = datetime.strptime(pub_date, '%a, %d %b %Y %H:%M:%S %Z')
                dt = dt.astimezone(timezone(timedelta(hours=8)))
                date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                date_str = pub_date
        
        # Clean HTML from description
        desc_text = re.sub(r'<[^>]+>', '', description)
        desc_text = desc_text.replace('&nbsp;', ' ')
        desc_text = desc_text.replace('&lt;', '<')
        desc_text = desc_text.replace('&gt;', '>')
        desc_text = desc_text.replace('&amp;', '&')
        
        discussion = {
            'title': title,
            'link': link,
            'description': desc_text,
            'date': date_str,
            'author': author,
            'type': 'discussion',
        }
        discussions.append(discussion)
    
    return discussions


def download_file(url, file_name, output_dir):
    """
    Download file from URL to multimedia directory.
    
    Args:
        url: File URL
        file_name: File name
        output_dir: Output directory
    
    Returns:
        Path: Downloaded file path, or None if failed
    """
    try:
        multimedia_path = Path(output_dir)
        multimedia_path.mkdir(parents=True, exist_ok=True)
        
        safe_name = re.sub(r'[<>":/\\|?*]', '_', file_name)
        file_path = multimedia_path / safe_name
        
        if file_path.exists():
            print(f"[INFO] File already exists, skipping: {safe_name}")
            return str(file_path)
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=60) as response:
            with open(file_path, 'wb') as f:
                f.write(response.read())
        
        print(f"[SUCCESS] Downloaded: {safe_name} ({file_path.stat().st_size} bytes)")
        return str(file_path)
    except Exception as e:
        print(f"[WARN] Download failed: {e}")
        return None


def save_to_markdown(announcements, discussions, stock_name, symbol, output_dir):
    """
    Save announcements and discussions to Markdown file.
    
    Args:
        announcements: List of announcement items
        discussions: List of discussion items
        stock_name: Stock name
        symbol: Stock symbol
        output_dir: Output directory
    
    Returns:
        Path: Saved file path
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Build filename
    today = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
    safe_name = re.sub(r'[<>":/\\|?*]', '_', stock_name)
    filename = f"{today}_{safe_name}_{symbol}_雪球.md"
    file_path = output_path / filename
    
    # Build markdown content
    now = datetime.now(timezone(timedelta(hours=8)))
    
    markdown = f"""---
title: {stock_name}({symbol}) - 雪球信息
date: {today}
source: xueqiu.com via RSSHub
symbol: {symbol}
---

# {stock_name}({symbol}) - 雪球信息

**获取时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}
**数据来源**: [雪球网](https://xueqiu.com/S/{symbol})
**公告数量**: {len(announcements)} 条
**讨论数量**: {len(discussions)} 条

---

## 📢 公告

"""
    
    if announcements:
        for item in announcements:
            markdown += f"""### {item['title']}

**时间**: {item['date']}
**链接**: [{item['link']}]({item['link']})

{item['description']}

---

"""
    else:
        markdown += "*暂无公告*\n\n"
    
    markdown += "## 💬 讨论\n\n"
    
    if discussions:
        for item in discussions:
            markdown += f"""### {item['title']}

**作者**: {item['author']} | **时间**: {item['date']}
**链接**: [{item['link']}]({item['link']})

{item['description']}

---

"""
    else:
        markdown += "*暂无讨论*\n\n"
    
    # Write file
    file_path.write_text(markdown, encoding='utf-8')
    
    print(f"[SUCCESS] Saved: {file_path}")
    return str(file_path)


def main():
    parser = argparse.ArgumentParser(description='雪球股票信息获取工具 (RSSHub版)')
    parser.add_argument('--symbol', type=str, required=True, help='股票代码（如 SH002595）')
    parser.add_argument('--name', type=str, help='股票名称（可选）')
    parser.add_argument('--output', type=str, default=str(OUTPUT_BASE), help='输出目录')
    parser.add_argument('--rsshub', type=str, default=RSSHUB_BASE, help='RSSHub地址')
    
    args = parser.parse_args()
    
    symbol = args.symbol
    stock_name = args.name or symbol
    output_dir = args.output
    rsshub_base = args.rsshub
    
    print(f"=" * 60)
    print(f"雪球股票信息获取 (RSSHub)")
    print(f"=" * 60)
    print(f"股票代码: {symbol}")
    print(f"股票名称: {stock_name}")
    print(f"输出目录: {output_dir}")
    print(f"RSSHub: {rsshub_base}")
    print(f"=" * 60)
    
    # Fetch stock info (announcements)
    info_url = f"{rsshub_base}/xueqiu/stock_info/{symbol}"
    print(f"\n[INFO] Fetching announcements from: {info_url}")
    info_items = fetch_rss_feed(info_url)
    
    if info_items is None:
        print("[WARN] Failed to fetch announcements")
        info_items = []
    else:
        print(f"[INFO] Fetched {len(info_items)} announcements")
    
    announcements = parse_stock_info_items(info_items)
    
    # Fetch stock comments (discussions)
    comments_url = f"{rsshub_base}/xueqiu/stock_comments/{symbol}"
    print(f"\n[INFO] Fetching discussions from: {comments_url}")
    comments_items = fetch_rss_feed(comments_url)
    
    if comments_items is None:
        print("[WARN] Failed to fetch discussions")
        comments_items = []
    else:
        print(f"[INFO] Fetched {len(comments_items)} discussions")
    
    discussions = parse_stock_comments_items(comments_items)
    
    # Save to file
    if announcements or discussions:
        file_path = save_to_markdown(announcements, discussions, stock_name, symbol, output_dir)
        
        # Send notification
        gotify_notify(
            f"雪球: {stock_name}",
            f"获取 {len(announcements)} 条公告, {len(discussions)} 条讨论\n{file_path}",
            priority=5
        )
        
        # Trigger NAS sync
        trigger_nas_sync()
        
        print(f"\n" + "=" * 60)
        print(f"完成！")
        print(f"公告: {len(announcements)} 条")
        print(f"讨论: {len(discussions)} 条")
        print(f"文件: {file_path}")
        print(f"=" * 60)
    else:
        print("\n[WARN] No data fetched")
        gotify_notify(
            f"雪球: {stock_name} - 获取失败",
            "未能获取任何数据，请检查RSSHub服务状态",
            priority=8
        )


if __name__ == "__main__":
    main()
