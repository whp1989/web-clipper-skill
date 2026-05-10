---
name: web-clipper-xueqiu
description: 雪球股票信息获取工具。使用 pysnowball 库获取雪球网股票数据，保存为Markdown文件。Use when the user mentions 雪球, xueqiu, 股票讨论, or requests to fetch stock information from xueqiu.com.
---

# Web Clipper - Xueqiu Stock Sub-Skill

## Purpose

使用 `pysnowball` 库获取雪球网(xueqiu.com)股票数据，保存为Markdown文件到本地syncthing-synced文件夹。

## When to Use

Trigger this sub-skill when:
- User says **"雪球"**, **"xueqiu"**, **"股票讨论"**
- User requests to fetch stock information from xueqiu.com
- User mentions specific stock name or symbol

## Important Note

**需要有效的雪球网Token才能获取数据。**

Token格式: `xq_a_token=xxx;u=yyy`
- `xq_a_token`: 从浏览器Cookie获取
- `u`: 用户ID

## How to Get Token

1. 在浏览器中登录雪球网 (https://xueqiu.com)
2. 按 F12 打开开发者工具
3. 切换到 Application/Storage → Cookies
4. 找到 `xq_a_token` 和 `u` 字段
5. 复制这两个值

## Installation

```bash
pip install pysnowball
```

## Script

Use `scripts/xueqiu_stock.py` for the fetching operation.

```bash
python3 ~/.openclaw/skills/web-clipper/scripts/xueqiu_stock.py \
  --symbol "SH002595" \
  --name "豪迈科技" \
  --token "YOUR_XQ_A_TOKEN" \
  --u "YOUR_USER_ID" \
  --output "/path/to/output"
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `symbol` | ✅ | 股票代码（如 SH002595, SZ000001） |
| `name` | ❌ | 股票名称（用于文件名） |
| `token` | ❌* | xq_a_token（首次使用必须提供） |
| `u` | ❌* | 用户ID（首次使用必须提供） |
| `output` | ❌ | 输出目录（默认: syncthing/raw/YYYY-MM-DD） |
| `max-pages` | ❌ | 最大翻页数（默认3） |

*Token会自动保存到 `~/.openclaw/workspace/.xueqiu_token.json`

## Output Location

- Base dir: `~/.openclaw/workspace/syncthing/raw/YYYY-MM-DD/`
- Filename: `YYYY-MM-DD_股票名称_股票代码_雪球.md`

## Content Structure

生成的Markdown包含：
1. **📈 实时行情** - 当前价格、涨跌幅等
2. **📊 详细数据** - 市值、市盈率、换手率等
3. **💬 讨论** - 用户讨论（需要有效token）

## Behavior Rules

- **Auto-trigger**: When "雪球" or "xueqiu" keyword is detected
- **Token handling**: Save provided token, reuse for subsequent calls
- **Error handling**: If token invalid, prompt user to provide new token
- **Gotify notification**: Sends notification after successful fetch
- **NAS sync**: Automatically triggers NAS sync after successful fetch

## Example Usage

```bash
# First time - provide token
python3 ~/.openclaw/skills/web-clipper/scripts/xueqiu_stock.py \
  --symbol "SH002595" \
  --name "豪迈科技" \
  --token "df88674792039e1024eb3e572de0b343a6ea4008" \
  --u "1090321739"

# Subsequent calls - token auto-loaded
python3 ~/.openclaw/skills/web-clipper/scripts/xueqiu_stock.py \
  --symbol "SH002595" \
  --name "豪迈科技"
```

## GitHub Repository

Same as main skill: https://github.com/whp1989/web-clipper-skill

## Dependencies

- pysnowball (雪球官方API封装)
- requests (用于获取讨论数据)

## Future Enhancements

- Support for stock announcements/bulletins
- Automatic token refresh mechanism
- Support for multiple stocks batch fetch

## Limitations

- Requires valid xueqiu.com token with API access
- Token may expire after some time
- Discussion data requires additional API permissions
