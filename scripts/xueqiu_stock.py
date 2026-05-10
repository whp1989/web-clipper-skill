#!/usr/bin/env python3
"""
雪球股票信息获取工具 - xueqiu-stock
使用 pysnowball 库获取雪球网股票数据

使用方法：
1. 首次使用需要提供 xq_a_token 和 u（用户ID）
2. Token会自动保存到本地文件
3. 后续自动加载使用
4. Token过期后需要重新提供
"""

import os
import sys
import json
import re
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 尝试导入 pysnowball
try:
    import pysnowball as ball
    PYSNOWBALL_AVAILABLE = True
except ImportError:
    PYSNOWBALL_AVAILABLE = False
    print("[ERROR] pysnowball 未安装，请先安装: pip install pysnowball")
    sys.exit(1)

# Configuration
OUTPUT_BASE = Path("~/.openclaw/workspace/syncthing/raw").expanduser()
MULTIMEDIA_DIR = OUTPUT_BASE / "multimedia"
TOKEN_FILE = Path("~/.openclaw/workspace/.xueqiu_token.json").expanduser()
API_CONFIG_PATHS = [
    Path("~/.openclaw/workspace/.openclaw/api-config.json").expanduser(),
    Path("~/.openclaw/api-config.json").expanduser(),
]


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
        import requests
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


def save_token(token_data):
    """保存Token到文件"""
    try:
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
            json.dump(token_data, f, indent=2)
        print(f"[INFO] Token已保存到: {TOKEN_FILE}")
    except Exception as e:
        print(f"[WARN] 保存Token失败: {e}")


def load_token():
    """从文件加载Token"""
    if TOKEN_FILE.exists():
        try:
            with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] 加载Token失败: {e}")
    return None


def get_token_string(provided_token=None, provided_u=None):
    """
    获取Token字符串
    
    Args:
        provided_token: 用户提供的xq_a_token
        provided_u: 用户提供的u（用户ID）
    
    Returns:
        str: 完整的token字符串，或None
    """
    # 如果提供了token，使用提供的
    if provided_token and provided_u:
        token_str = f"xq_a_token={provided_token};u={provided_u}"
        save_token({"xq_a_token": provided_token, "u": provided_u})
        return token_str
    
    # 尝试加载保存的token
    saved_token = load_token()
    if saved_token and saved_token.get("xq_a_token") and saved_token.get("u"):
        print("[INFO] 使用保存的Token")
        return f"xq_a_token={saved_token['xq_a_token']};u={saved_token['u']}"
    
    print("[ERROR] 未找到Token，请提供xq_a_token和u参数")
    return None


def fetch_stock_info(symbol):
    """
    获取股票信息
    
    Args:
        symbol: 股票代码（如 SH002595）
    
    Returns:
        dict: 股票信息
    """
    try:
        # 获取实时行情
        quote = ball.quotec(symbol)
        print(f"[DEBUG] Quote: {quote}")
        
        # 获取详细行情
        detail = ball.quote_detail(symbol)
        print(f"[DEBUG] Detail keys: {detail.keys() if detail else 'None'}")
        
        # 获取盘口数据
        pankou = ball.pankou(symbol)
        
        return {
            "quote": quote,
            "detail": detail,
            "pankou": pankou
        }
    except Exception as e:
        print(f"[ERROR] 获取股票信息失败: {e}")
        return None


def fetch_stock_discussions(symbol, max_pages=3):
    """
    获取股票讨论
    
    Args:
        symbol: 股票代码
        max_pages: 最大页数
    
    Returns:
        list: 讨论列表
    """
    discussions = []
    
    # pysnowball 没有直接的讨论接口，使用雪球API
    import requests
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': f'https://xueqiu.com/S/{symbol}',
        'X-Requested-With': 'XMLHttpRequest',
    }
    
    # 从token中获取cookie
    token_str = get_token_string()
    if token_str:
        # 解析token为cookie字典
        cookies = {}
        for item in token_str.split(';'):
            if '=' in item:
                key, value = item.strip().split('=', 1)
                cookies[key] = value
        
        for page in range(1, max_pages + 1):
            try:
                url = 'https://xueqiu.com/query/v1/symbol/search/status'
                params = {
                    'count': 10,
                    'comment': 0,
                    'symbol': symbol,
                    'hl': 0,
                    'source': 'user',
                    'sort': 'time',
                    'page': page,
                }
                
                resp = requests.get(url, headers=headers, params=params, cookies=cookies, timeout=15)
                
                if resp.status_code != 200:
                    break
                
                data = resp.json()
                
                if data.get('code') != 200:
                    break
                
                items = data.get('data', {}).get('items', [])
                if not items:
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
                
            except Exception as e:
                print(f"[ERROR] 获取讨论失败: {e}")
                break
    
    return discussions


def save_to_markdown(stock_info, discussions, stock_name, symbol, output_dir):
    """
    保存到Markdown文件
    
    Args:
        stock_info: 股票信息
        discussions: 讨论列表
        stock_name: 股票名称
        symbol: 股票代码
        output_dir: 输出目录
    
    Returns:
        Path: 保存的文件路径
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 构建文件名
    today = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
    safe_name = re.sub(r'[<>":/\\|?*]', '_', stock_name)
    filename = f"{today}_{safe_name}_{symbol}_雪球.md"
    file_path = output_path / filename
    
    # 构建Markdown内容
    now = datetime.now(timezone(timedelta(hours=8)))
    
    markdown = f"""---
title: {stock_name}({symbol}) - 雪球数据
date: {today}
source: xueqiu.com
symbol: {symbol}
---

# {stock_name}({symbol}) - 雪球数据

**获取时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}
**数据来源**: [雪球网](https://xueqiu.com/S/{symbol})

---

"""
    
    # 添加股票行情
    if stock_info and stock_info.get('detail'):
        detail_data = stock_info['detail'].get('data', {})
        detail_quote = detail_data.get('quote', {}) if detail_data else {}
        if detail_quote:
            markdown += f"""## 📈 实时行情

**股票名称**: {detail_quote.get('name', 'N/A')}
**当前价格**: {detail_quote.get('current', 'N/A')}
**涨跌幅**: {detail_quote.get('percent', 'N/A')}%
**涨跌额**: {detail_quote.get('chg', 'N/A')}
**成交量**: {detail_quote.get('volume', 'N/A')}
**成交额**: {detail_quote.get('amount', 'N/A')}
**开盘价**: {detail_quote.get('open', 'N/A')}
**最高价**: {detail_quote.get('high', 'N/A')}
**最低价**: {detail_quote.get('low', 'N/A')}
**昨收**: {detail_quote.get('last_close', 'N/A')}

---

"""
    
    # 添加详细数据
    if stock_info and stock_info.get('detail'):
        detail_data = stock_info['detail'].get('data', {})
        detail_quote = detail_data.get('quote', {}) if detail_data else {}
        if detail_quote:
            markdown += f"""## 📊 详细数据

**总市值**: {detail_quote.get('market_capital', 'N/A')}
**流通市值**: {detail_quote.get('float_market_capital', 'N/A')}
**市盈率(TTM)**: {detail_quote.get('pe_ttm', 'N/A')}
**市净率**: {detail_quote.get('pb', 'N/A')}
**换手率**: {detail_quote.get('turnover_rate', 'N/A')}%
**振幅**: {detail_quote.get('amplitude', 'N/A')}%
**52周最高**: {detail_quote.get('high52w', 'N/A')}
**52周最低**: {detail_quote.get('low52w', 'N/A')}

---

"""
    
    # 添加讨论
    markdown += f"""## 💬 讨论 ({len(discussions)}条)

"""
    
    if discussions:
        for item in discussions:
            # 清理HTML标签
            text = item['text']
            text = re.sub(r'<[^>]+>', '', text)
            text = text.replace('&nbsp;', ' ')
            
            # 格式化时间
            created_at = item.get("created_at", "")
            if created_at:
                try:
                    dt = datetime.fromtimestamp(created_at / 1000, tz=timezone(timedelta(hours=8)))
                    time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    time_str = str(created_at)
            else:
                time_str = "未知时间"
            
            markdown += f"""### {item.get('title', '无标题')}

**作者**: {item['user']} | **时间**: {time_str}
**点赞**: {item['likes']} | **评论**: {item['comments']} | **转发**: {item['retweets']}

{text}

---

"""
    else:
        markdown += "*暂无讨论*\n\n"
    
    # 写入文件
    file_path.write_text(markdown, encoding='utf-8')
    
    print(f"[SUCCESS] 已保存: {file_path}")
    return str(file_path)


def main():
    parser = argparse.ArgumentParser(description='雪球股票数据获取工具 (pysnowball)')
    parser.add_argument('--symbol', type=str, required=True, help='股票代码（如 SH002595）')
    parser.add_argument('--name', type=str, help='股票名称（可选）')
    parser.add_argument('--output', type=str, default=str(OUTPUT_BASE), help='输出目录')
    parser.add_argument('--max-pages', type=int, default=3, help='最大翻页数（默认3）')
    parser.add_argument('--token', type=str, help='xq_a_token（首次使用需要提供）')
    parser.add_argument('--u', type=str, help='用户ID u（首次使用需要提供）')
    
    args = parser.parse_args()
    
    symbol = args.symbol
    stock_name = args.name or symbol
    output_dir = args.output
    
    print(f"=" * 60)
    print(f"雪球股票数据获取 (pysnowball)")
    print(f"=" * 60)
    print(f"股票代码: {symbol}")
    print(f"股票名称: {stock_name}")
    print(f"输出目录: {output_dir}")
    if args.token:
        print(f"Token: 用户提供")
    print(f"=" * 60)
    
    # 获取Token
    token_str = get_token_string(args.token, args.u)
    if not token_str:
        print("[ERROR] 无法获取Token，退出")
        print("[INFO] 提示: 需要登录雪球网获取 xq_a_token 和 u")
        print("[INFO] 获取方法: 浏览器登录xueqiu.com → F12 → Application → Cookies")
        print("[INFO] 参数: --token '你的xq_a_token' --u '你的用户ID'")
        sys.exit(1)
    
    # 设置token
    ball.set_token(token_str)
    print("[INFO] Token设置成功")
    
    # 获取股票信息
    print(f"\n[INFO] 获取股票行情...")
    stock_info = fetch_stock_info(symbol)
    
    if stock_info:
        print("[INFO] 股票行情获取成功")
    else:
        print("[WARN] 股票行情获取失败")
    
    # 获取讨论
    print(f"\n[INFO] 获取讨论...")
    discussions = fetch_stock_discussions(symbol, max_pages=args.max_pages)
    print(f"[INFO] 获取到 {len(discussions)} 条讨论")
    
    # 保存到文件
    file_path = save_to_markdown(stock_info, discussions, stock_name, symbol, output_dir)
    
    # 发送通知
    gotify_notify(
        f"雪球: {stock_name}",
        f"获取股票数据成功\n{file_path}",
        priority=5
    )
    
    # 触发NAS同步
    trigger_nas_sync()
    
    print(f"=" * 60)
    print(f"完成！")
    print(f"文件路径: {file_path}")
    print(f"=" * 60)


if __name__ == "__main__":
    main()
