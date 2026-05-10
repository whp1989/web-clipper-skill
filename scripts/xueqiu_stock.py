#!/usr/bin/env python3
"""
雪球股票信息获取工具 - xueqiu-stock
通过东方财富公开API获取股票公告和讨论信息，保存为Markdown文件。

当东方财富不可用时，可切换到RSSHub方案（需要可访问的RSSHub实例）。
"""

import os
import sys
import json
import re
import time
import argparse
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Configuration
OUTPUT_BASE = Path("~/.openclaw/workspace/syncthing/raw").expanduser()
MULTIMEDIA_DIR = OUTPUT_BASE / "multimedia"
API_CONFIG_PATHS = [
    Path("~/.openclaw/workspace/.openclaw/api-config.json").expanduser(),
    Path("~/.openclaw/api-config.json").expanduser(),
]

# 东方财富API (公开，无需登录)
EASTMONEY_SEARCH_API = "https://searchapi.eastmoney.com/api/suggest/get"
EASTMONEY_NOTICE_API = "https://datacenter-web.eastmoney.com/api/data/v1/get"


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


def search_stock_code(stock_name):
    """
    搜索股票代码
    
    Args:
        stock_name: 股票名称或代码
    
    Returns:
        tuple: (股票代码, 股票名称, 市场) 或 (None, None, None)
    """
    try:
        params = {
            'input': stock_name,
            'type': '14',
            'count': '5',
        }
        
        url = f"{EASTMONEY_SEARCH_API}?{urllib.parse.urlencode(params)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://www.eastmoney.com/',
        }
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get('QuotationCodeTable', {}).get('Data'):
                stock = data['QuotationCodeTable']['Data'][0]
                code = stock.get('Code')
                name = stock.get('Name')
                market = stock.get('SecurityTypeName')
                return code, name, market
            
            return None, None, None
    except Exception as e:
        print(f"[ERROR] Search failed: {e}")
        return None, None, None


def fetch_stock_announcements(stock_code, max_items=20):
    """
    获取股票公告和财务数据
    
    Args:
        stock_code: 股票代码
        max_items: 最大获取条数
    
    Returns:
        list: 公告/财务数据列表
    """
    announcements = []
    
    try:
        # 东方财富财务数据API (已验证可用)
        params = {
            'sortColumns': 'UPDATE_DATE,SECURITY_CODE',
            'sortTypes': '-1,-1',
            'pageSize': max_items,
            'pageNumber': 1,
            'reportName': 'RPT_FCI_PERFORMANCEE',
            'columns': 'ALL',
            'source': 'WEB',
            'client': 'WEB',
            'filter': f'(SECURITY_CODE="{stock_code}")',
        }
        
        url = f"{EASTMONEY_NOTICE_API}?{urllib.parse.urlencode(params)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://data.eastmoney.com/notices/',
        }
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get('result', {}).get('data'):
                for item in data['result']['data']:
                    # 构建标题
                    report_type = item.get('DATATYPE', '')
                    year = item.get('REPORT_DATE', '')[:4] if item.get('REPORT_DATE') else ''
                    title = f"{year}年 {report_type}" if year and report_type else report_type
                    
                    # 构建描述
                    desc_parts = []
                    if item.get('BASIC_EPS'):
                        desc_parts.append(f"每股收益: {item['BASIC_EPS']}")
                    if item.get('TOTAL_OPERATE_INCOME'):
                        income = item['TOTAL_OPERATE_INCOME'] / 100000000
                        desc_parts.append(f"营业收入: {income:.2f}亿")
                    if item.get('PARENT_NETPROFIT'):
                        profit = item['PARENT_NETPROFIT'] / 100000000
                        desc_parts.append(f"净利润: {profit:.2f}亿")
                    if item.get('WEIGHTAVG_ROE'):
                        desc_parts.append(f"净资产收益率: {item['WEIGHTAVG_ROE']}%")
                    
                    announcement = {
                        'title': title or '财务报告',
                        'date': item.get('NOTICE_DATE', item.get('UPDATE_DATE', '')),
                        'type': report_type or '财务数据',
                        'description': '\n'.join(desc_parts),
                        'url': f"https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/Index?type=web&code={stock_code}",
                    }
                    announcements.append(announcement)
        
        return announcements
    except Exception as e:
        print(f"[ERROR] Fetch announcements failed: {e}")
        return []


def fetch_stock_discussions(stock_code, max_items=20):
    """
    获取股票讨论 (使用股吧数据)
    
    Args:
        stock_code: 股票代码
        max_items: 最大获取条数
    
    Returns:
        list: 讨论列表
    """
    discussions = []
    
    try:
        # 东方财富股吧API
        url = f"https://guba.eastmoney.com/api/taobaolst"
        params = {
            'type': '1',
            'code': stock_code,
            'page': '1',
            'size': max_items,
        }
        
        full_url = f"{url}?{urllib.parse.urlencode(params)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': f'https://guba.eastmoney.com/list,{stock_code}.html',
        }
        
        req = urllib.request.Request(full_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get('re', []):
                for item in data['re']:
                    discussion = {
                        'title': item.get('title', ''),
                        'author': item.get('author', ''),
                        'content': item.get('content', ''),
                        'date': item.get('post_publish_time', ''),
                        'url': item.get('post_id', ''),
                    }
                    discussions.append(discussion)
        
        return discussions
    except Exception as e:
        print(f"[ERROR] Fetch discussions failed: {e}")
        return []


def save_to_markdown(announcements, discussions, stock_name, stock_code, output_dir):
    """
    保存到Markdown文件
    
    Args:
        announcements: 公告列表
        discussions: 讨论列表
        stock_name: 股票名称
        stock_code: 股票代码
        output_dir: 输出目录
    
    Returns:
        Path: 保存的文件路径
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 构建文件名
    today = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
    safe_name = re.sub(r'[<>":/\\|?*]', '_', stock_name)
    filename = f"{today}_{safe_name}_{stock_code}_雪球.md"
    file_path = output_path / filename
    
    # 构建Markdown内容
    now = datetime.now(timezone(timedelta(hours=8)))
    
    markdown = f"""---
title: {stock_name}({stock_code}) - 股票信息
date: {today}
source: eastmoney.com
symbol: {stock_code}
---

# {stock_name}({stock_code}) - 股票信息

**获取时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}
**数据来源**: [东方财富](https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/Index?type=web&code={stock_code})
**公告/财报数量**: {len(announcements)} 条
**讨论数量**: {len(discussions)} 条

---

## 📢 公告/财务报告

"""
    
    if announcements:
        for item in announcements:
            markdown += f"""### {item['title']}

**时间**: {item['date']} | **类型**: {item['type']}

{item['description']}

**链接**: [{item['url']}]({item['url']})

---

"""
    else:
        markdown += "*暂无公告*\n\n"
    
    markdown += "## 💬 讨论\n\n"
    
    if discussions:
        for item in discussions:
            # 清理HTML标签
            content = re.sub(r'<[^>]+>', '', item.get('content', ''))
            content = content.replace('&nbsp;', ' ')
            
            markdown += f"""### {item['title']}

**作者**: {item['author']} | **时间**: {item['date']}

{content}

---

"""
    else:
        markdown += "*暂无讨论*\n\n"
    
    # 写入文件
    file_path.write_text(markdown, encoding='utf-8')
    
    print(f"[SUCCESS] Saved: {file_path}")
    return str(file_path)


def main():
    parser = argparse.ArgumentParser(description='雪球股票信息获取工具 (东方财富方案)')
    parser.add_argument('--symbol', type=str, required=True, help='股票代码（如 002595）或名称（如 豪迈科技）')
    parser.add_argument('--name', type=str, help='股票名称（可选）')
    parser.add_argument('--output', type=str, default=str(OUTPUT_BASE), help='输出目录')
    parser.add_argument('--max-items', type=int, default=20, help='最大获取条数（默认20）')
    
    args = parser.parse_args()
    
    input_value = args.symbol
    stock_name = args.name
    output_dir = args.output
    max_items = args.max_items
    
    print(f"=" * 60)
    print(f"雪球股票信息获取 (东方财富方案)")
    print(f"=" * 60)
    
    # 判断输入是代码还是名称
    if input_value.isdigit():
        stock_code = input_value
        if not stock_name:
            # 尝试搜索名称
            _, found_name, _ = search_stock_code(stock_code)
            if found_name:
                stock_name = found_name
            else:
                stock_name = stock_code
        print(f"股票代码: {stock_code}")
    else:
        # 搜索股票代码
        print(f"正在搜索: {input_value}")
        stock_code, found_name, market = search_stock_code(input_value)
        if not stock_code:
            print(f"[ERROR] 未找到股票: {input_value}")
            sys.exit(1)
        stock_name = input_value
        print(f"搜索结果: {found_name} ({stock_code}) - {market}")
    
    print(f"股票名称: {stock_name}")
    print(f"输出目录: {output_dir}")
    print(f"=" * 60)
    
    # 获取公告
    print(f"\n[INFO] 获取公告...")
    announcements = fetch_stock_announcements(stock_code, max_items)
    print(f"[INFO] 获取到 {len(announcements)} 条公告")
    
    # 获取讨论
    print(f"\n[INFO] 获取讨论...")
    discussions = fetch_stock_discussions(stock_code, max_items)
    print(f"[INFO] 获取到 {len(discussions)} 条讨论")
    
    # 保存到文件
    if announcements or discussions:
        file_path = save_to_markdown(announcements, discussions, stock_name, stock_code, output_dir)
        
        # 发送通知
        gotify_notify(
            f"雪球: {stock_name}",
            f"获取 {len(announcements)} 条公告, {len(discussions)} 条讨论\n{file_path}",
            priority=5
        )
        
        # 触发NAS同步
        trigger_nas_sync()
        
        print(f"\n" + "=" * 60)
        print(f"完成！")
        print(f"公告: {len(announcements)} 条")
        print(f"讨论: {len(discussions)} 条")
        print(f"文件: {file_path}")
        print(f"=" * 60)
    else:
        print("\n[WARN] 未获取到任何数据")
        gotify_notify(
            f"雪球: {stock_name} - 获取失败",
            "未能获取任何数据",
            priority=8
        )


if __name__ == "__main__":
    main()
