---
name: web-clipper-xueqiu
description: 雪球股票信息获取工具。获取指定股票的讨论和公告信息，保存为Markdown文件。Use when the user mentions 雪球, xueqiu, 股票讨论, 股票公告, or requests to fetch stock information from xueqiu.com.
---

# Web Clipper - Xueqiu Stock Sub-Skill

## Purpose

获取雪球网(xueqiu.com)上指定股票的讨论和公告信息，保存为Markdown文件到本地syncthing-synced文件夹。

## When to Use

Trigger this sub-skill when:
- User says **"雪球"**, **"xueqiu"**, **"股票讨论"**, **"股票公告"**
- User requests to fetch stock information from xueqiu.com
- User mentions specific stock name or symbol

## Important Note

**雪球网需要登录才能获取讨论和公告数据。**
- 首次使用需要提供Cookie
- Cookie会自动保存，后续可自动使用
- 如果Cookie过期，需要重新提供

## How to Get Cookie

1. 在浏览器中登录雪球网 (https://xueqiu.com)
2. 按 F12 打开开发者工具
3. 切换到 Network/网络 标签
4. 刷新页面，找到任意请求
5. 在请求头中复制 Cookie 字段
6. 格式示例: `xq_a_token=xxx; xq_r_token=xxx; xq_id_token=xxx`

## Script

Use `scripts/xueqiu_stock.py` for the fetching operation.

```bash
python3 ~/.openclaw/skills/web-clipper/scripts/xueqiu_stock.py \
  --symbol "SH002595" \
  --name "豪迈科技" \
  --cookie "YOUR_COOKIE_STRING" \
  --output "/path/to/output"
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `symbol` | ✅ | 股票代码（如 SH002595, SZ000001） |
| `name` | ❌ | 股票名称（用于文件名） |
| `cookie` | ❌* | Cookie字符串（首次使用必须提供） |
| `output` | ❌ | 输出目录（默认: syncthing/raw/YYYY-MM-DD） |
| `max-pages` | ❌ | 最大翻页数（默认5） |

*Cookie会自动保存到 `~/.openclaw/workspace/.xueqiu_cookies.json`

## Output Location

- Base dir: `~/.openclaw/workspace/syncthing/raw/YYYY-MM-DD/`
- Filename: `YYYY-MM-DD_股票名称_股票代码.md`

## Behavior Rules

- **Auto-trigger**: When "雪球" or "xueqiu" keyword is detected
- **Cookie handling**: Save provided cookie, reuse for subsequent calls
- **Error handling**: If cookie expired, prompt user to provide new cookie
- **NAS sync**: Automatically triggers NAS sync after successful fetch

## Example Usage

```bash
# First time - provide cookie
python3 ~/.openclaw/skills/web-clipper/scripts/xueqiu_stock.py \
  --symbol "SH002595" \
  --name "豪迈科技" \
  --cookie "xq_a_token=abc123; xq_r_token=def456"

# Subsequent calls - cookie auto-loaded
python3 ~/.openclaw/skills/web-clipper/scripts/xueqiu_stock.py \
  --symbol "SH002595" \
  --name "豪迈科技"
```

## GitHub Repository

Same as main skill: https://github.com/whp1989/web-clipper-skill

## Future Enhancements

- Support for stock announcements/bulletins
- Automatic cookie refresh mechanism
- Support for multiple stocks batch fetch
- Integration with stock price data

## Limitations

- Requires valid login cookie from xueqiu.com
- Cookie may expire after some time
- Rate limiting by xueqiu.com WAF
