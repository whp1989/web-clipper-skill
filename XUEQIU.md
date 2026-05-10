---
name: web-clipper-xueqiu
description: 雪球股票信息获取工具。通过RSSHub获取指定股票的公告和讨论信息，保存为Markdown文件。Use when the user mentions 雪球, xueqiu, 股票讨论, 股票公告, or requests to fetch stock information from xueqiu.com.
---

# Web Clipper - Xueqiu Stock Sub-Skill

## Purpose

通过RSSHub获取雪球网(xueqiu.com)上指定股票的公告和讨论信息，保存为Markdown文件到本地syncthing-synced文件夹。

## When to Use

Trigger this sub-skill when:
- User says **"雪球"**, **"xueqiu"**, **"股票讨论"**, **"股票公告"**
- User requests to fetch stock information from xueqiu.com
- User mentions specific stock name or symbol

## RSSHub Service

**注意**: 需要使用自建的RSSHub服务，地址为 `https://rsshub.pandaponds`

**路由**:
- 股票公告: `/xueqiu/stock_info/{symbol}`
- 股票讨论: `/xueqiu/stock_comments/{symbol}`

**示例**:
- `https://rsshub.pandaponds/xueqiu/stock_info/SH002595`
- `https://rsshub.pandaponds/xueqiu/stock_comments/SH002595`

## Script

Use `scripts/xueqiu_stock.py` for the fetching operation.

```bash
python3 ~/.openclaw/skills/web-clipper/scripts/xueqiu_stock.py \
  --symbol "SH002595" \
  --name "豪迈科技" \
  --output "/path/to/output"
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `symbol` | ✅ | 股票代码（如 SH002595, SZ000001） |
| `name` | ❌ | 股票名称（用于文件名） |
| `output` | ❌ | 输出目录（默认: syncthing/raw/YYYY-MM-DD） |
| `rsshub` | ❌ | RSSHub地址（默认: https://rsshub.pandaponds） |

## Output Location

- Base dir: `~/.openclaw/workspace/syncthing/raw/YYYY-MM-DD/`
- Filename: `YYYY-MM-DD_股票名称_股票代码_雪球.md`

## Content Structure

生成的Markdown包含两个部分：
1. **📢 公告** - 公司公告、财报等信息
2. **💬 讨论** - 用户讨论、评论等信息

## Behavior Rules

- **Auto-trigger**: When "雪球" or "xueqiu" keyword is detected
- **Gotify notification**: Sends notification after successful fetch
- **NAS sync**: Automatically triggers NAS sync after successful fetch
- **Error handling**: If RSSHub is unreachable, sends error notification

## Example Usage

```bash
# 获取豪迈科技的公告和讨论
python3 ~/.openclaw/skills/web-clipper/scripts/xueqiu_stock.py \
  --symbol "SH002595" \
  --name "豪迈科技"

# 使用自定义RSSHub地址
python3 ~/.openclaw/skills/web-clipper/scripts/xueqiu_stock.py \
  --symbol "SH002595" \
  --name "豪迈科技" \
  --rsshub "https://your-rsshub-instance.com"
```

## GitHub Repository

Same as main skill: https://github.com/whp1989/web-clipper-skill

## RSSHub Source Reference

- Stock comments: https://github.com/DIYgod/RSSHub/blob/master/lib/routes/xueqiu/stock-comments.tsx
- Stock info: https://github.com/DIYgod/RSSHub/blob/master/lib/routes/xueqiu/stock-info.ts

## Future Enhancements

- Support for multiple stocks batch fetch
- Support for historical data range selection
- Integration with stock price data

## Limitations

- Requires accessible RSSHub instance (rsshub.pandaponds)
- RSSHub must have xueqiu routes enabled
- Network connectivity to RSSHub required
