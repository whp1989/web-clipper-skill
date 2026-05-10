---
name: web-clipper-xueqiu
description: 雪球股票信息获取工具。通过东方财富公开API获取指定股票的财务报告和公告信息，保存为Markdown文件。Use when the user mentions 雪球, xueqiu, 股票讨论, 股票公告, or requests to fetch stock information.
---

# Web Clipper - Xueqiu Stock Sub-Skill

## Purpose

通过东方财富公开API获取股票的财务报告和公告信息，保存为Markdown文件到本地syncthing-synced文件夹。

## When to Use

Trigger this sub-skill when:
- User says **"雪球"**, **"xueqiu"**, **"股票讨论"**, **"股票公告"**
- User requests to fetch stock information
- User mentions specific stock name or symbol

## Data Source

**东方财富 (eastmoney.com)** - 公开API，无需登录
- 财务报告：年报、季报数据
- 关键指标：每股收益、营业收入、净利润、净资产收益率

## Script

Use `scripts/xueqiu_stock.py` for the fetching operation.

```bash
python3 ~/.openclaw/skills/web-clipper/scripts/xueqiu_stock.py \
  --symbol "002595" \
  --name "豪迈科技" \
  --output "/path/to/output"
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `symbol` | ✅ | 股票代码（如 002595）或名称（如 豪迈科技） |
| `name` | ❌ | 股票名称（可选，自动搜索） |
| `output` | ❌ | 输出目录（默认: syncthing/raw/YYYY-MM-DD） |
| `max-items` | ❌ | 最大获取条数（默认20） |

## Output Location

- Base dir: `~/.openclaw/workspace/syncthing/raw/YYYY-MM-DD/`
- Filename: `YYYY-MM-DD_股票名称_股票代码_雪球.md`

## Content Structure

生成的Markdown包含：
1. **📢 公告/财务报告** - 年报、季报等财务数据
2. **💬 讨论** - 股吧讨论（当前不可用）

## Behavior Rules

- **Auto-trigger**: When "雪球" or "xueqiu" keyword is detected
- **Gotify notification**: Sends notification after successful fetch
- **NAS sync**: Automatically triggers NAS sync after successful fetch
- **Error handling**: If API fails, sends error notification

## Example Usage

```bash
# 通过股票代码获取
python3 ~/.openclaw/skills/web-clipper/scripts/xueqiu_stock.py \
  --symbol "002595" \
  --name "豪迈科技"

# 通过股票名称获取（自动搜索代码）
python3 ~/.openclaw/skills/web-clipper/scripts/xueqiu_stock.py \
  --symbol "豪迈科技"
```

## GitHub Repository

Same as main skill: https://github.com/whp1989/web-clipper-skill

## Future Enhancements

- Support for real-time stock announcements
- Support for stock discussion forums
- Support for multiple stocks batch fetch
- Integration with stock price data

## Limitations

- 讨论数据当前不可用（东方财富股吧API限制）
- 主要提供财务报告数据
- 数据更新频率取决于东方财富API
