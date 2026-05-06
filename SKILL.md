---
name: web-clipper
description: Clip web articles to local Markdown files with images. Use when the user provides a URL and wants to save the article content as a Markdown file in the syncthing folder. Also use when the user says "剪藏", "保存链接", "clip this", "save this article", or any request to archive a web page to local storage. Automatically extracts text and images, converts to Markdown, and saves to ~/.openclaw/workspace/syncthing/raw/YYYY-MM-DD/.
---

# Web Clipper Skill

## Purpose

Save web articles as Markdown files with images to a local syncthing-synced folder.

## Workflow

When triggered by a URL (or explicit clip request):

1. **Fetch** the URL using `urllib.request`
2. **Extract** article title and content using site-specific parsers or generic HTML parser
3. **Download** images referenced in the article
4. **Convert** HTML content to Markdown
5. **Save** to `~/.openclaw/workspace/syncthing/raw/YYYY-MM-DD/`

## Script

Use `scripts/clipper.py` for the actual clipping operation.

```bash
python3 ~/.openclaw/skills/web-clipper/scripts/clipper.py "<URL>"
```

## Output Location

- Base dir: `~/.openclaw/workspace/syncthing/raw/`
- Subdir: `YYYY-MM-DD/` (current date)
- Filename: `{sanitized_title}.md`
- Images: `{sanitized_title}_images/` subdirectory

## Behavior Rules

- **Test mode**: When user says "测试" or "test", send the generated Markdown content back to the user
- **Normal mode**: Save silently, only report success/failure
- **Auto-upgrade**: If clipping fails, analyze the error, modify the script, and retry

## Supported Sites

| Site | Domain | Parser Type | Audio Support |
|------|--------|-------------|---------------|
| 华尔街见闻 | wallstreetcn.com | JSON embedded data | ❌ |
| 少数派 | sspai.com | HTML structure | ❌ |
| Bilibili | bilibili.com | JSON (__INITIAL_STATE__) | ✅ 视频下载+语音转文字 |
| 微信公众号 | mp.weixin.qq.com | HTML + image extraction | ❌ |
| 小宇宙 FM | xiaoyuzhoufm.com | Audio extraction | ✅ M4A |
| 知识星球 | zsxq.com | zsxq-cli API | ❌ |
| 其他网站 | * | Generic HTML parser | ❌ |

## 知识星球爬虫 (zsxq-crawler)

知识星球爬虫作为 web-clipper 的子模块，通过官方 `zsxq-cli` 调用 API，将知识星球内容同步为本地 Markdown。

### 前置条件

1. **Node.js 16+** 已安装
2. **zsxq-cli** 已全局安装：`npm install -g zsxq-cli`
3. **zsxq-cli 已登录**：运行 `zsxq-cli auth login` 完成 OAuth 授权
4. **Python 3.8+** 环境

验证登录状态：`zsxq-cli auth status`

### 快速使用

#### 1. 增量爬取（最常用）

只获取上次爬取之后的新内容：

```bash
cd scripts/zsxq_crawler
python zsxq_spider.py
```

#### 2. 按日期爬取（历史回溯）

```bash
python fetch_by_date.py --date 2026-04-29
```

#### 3. 其他模式

```bash
# 获取今天所有内容
python zsxq_spider.py --mode today

# 获取最近 N 条
python zsxq_spider.py --mode recent --count 50

# 测试模式（100条，不更新时间戳）
python zsxq_spider.py --mode test
```

### 输出格式

每个帖子保存为 Markdown 文件，命名规则：`{日期}_{标题}_{ID后6位}.md`

Frontmatter 包含：
- `title`: 标题
- `date`: 发布日期
- `time`: 发布时间
- `author`: 作者
- `type`: 内容类型 (talk/article/q&a)
- `likes`: 点赞数
- `comments`: 评论数
- `source`: 原文链接

输出目录由 `config.py` 中的 `OUTPUT_DIR` 控制。

### 核心配置 (scripts/zsxq_crawler/config.py)

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `ZSXQ_CLI_PATH` | zsxq-cli 可执行文件路径 | npm 全局安装路径 |
| `GROUP_ID` | 目标星球 ID | `48888584885518` |
| `OUTPUT_DIR` | Markdown 输出目录 | `D:/Investing/Investing/知识星球` |
| `REQUEST_DELAY` | 请求间隔（秒） | `1.5` |
| `MAX_TOPICS_PER_PAGE` | 每页条数（最大 30） | `30` |
| `MAX_PAGES` | 单次最大翻页数 | `200` |

### 关键实现细节

#### 增量爬取逻辑

1. 读取 `time.md` 中的上次爬取截止时间
2. 调用 zsxq-cli 获取该时间之后的新帖子
3. 每页 30 条，自动翻页直到无新内容
4. 生成 Markdown 文件到 `OUTPUT_DIR`
5. 更新 `time.md` 时间戳

#### 内嵌文章完整内容获取

知识星球的 `talk.text` 字段通常只有 400 字符的摘要，真正的完整内容在 `talk.article.inline_article_url` 中。

爬虫会自动：
1. 检测 `talk.article` 是否存在
2. 使用认证过的 session 请求 `inline_article_url`
3. 从 HTML 中提取 `<div class="content ql-editor">` 的内容
4. 将 HTML 转换为 Markdown 格式
5. 当获取到完整文章时，跳过被截断的摘要，避免内容重复

#### 时间戳文件

`time.md` 位于 skill 根目录，自动维护，格式：

```markdown
# 爬取时间记录

**上次爬取截止时间**: 2026-05-01T12:00:00+08:00
```

如需全量重新爬取，删除 `time.md` 即可。

### zsxq-cli 调用方式

通过 subprocess 调用官方 CLI：

```python
subprocess.run(
    [cli_path, "group", "topics", "--group-id", group_id, "--json"],
    capture_output=True,
    text=True,
    encoding="utf-8",
)
```

CLI 自动处理 OAuth Token、签名和限流。

### 故障排查

| 问题 | 解决 |
|------|------|
| zsxq-cli 未找到 | 检查 `config.py` 中 `ZSXQ_CLI_PATH` |
| zsxq-cli 未登录 | 运行 `zsxq-cli auth login` |
| 增量爬取无新内容 | 检查/删除 `time.md` 时间戳 |
| 输出中文乱码 | 确保终端编码为 UTF-8 |

### 注意事项

1. 仅供个人学习使用，遵守知识星球服务条款
2. 本程序仅做只读爬取，不涉及发帖/评论
3. 图片仅保存链接，如需本地存储需额外处理
4. 官方 CLI 有内置限流保护，保持 `REQUEST_DELAY >= 1` 秒

---

## Parser Architecture

### Registry Pattern
```python
SITE_PARSERS = {}

@register_parser("example.com")
def parse_example(html, url):
    # Site-specific extraction logic
    return {'title': ..., 'content': ..., 'images': [...]}
```

### Fallback Chain
1. Try site-specific parser (if domain matches)
2. Check parser health (success rate tracking)
3. If parser fails → fallback to generic HTML parser
4. If generic fails → suggest Playwright/Selenium

## Parser Evolution & Self-Healing

The skill includes automatic monitoring and evolution mechanisms:

### Health Tracking
- Each parser tracks success/failure rates
- Warns when success rate drops below 50% (after 3+ attempts)
- Suggests checking website structure

### Failure Diagnosis
When a parser fails, the system automatically diagnoses:
1. **HTML too short** → Suggests JavaScript rendering (Playwright/Selenium)
2. **Embedded JSON found** → Suggests checking JSON parsing logic
3. **Anti-bot detected** → Suggests cookie/session handling
4. **Title/Content missing** → Suggests updating selectors
5. **Structure changes** → Identifies potential new containers

### Evolution Reports
Failed parses automatically save reports to:
```
syncthing/raw/evolution-reports/YYYYMMDD_HHMMSS_domain_report.json
```

Each report contains:
- URL and domain
- HTML sample (first 5000 chars)
- Parser result details
- Diagnosis with suggestions
- Parser health statistics

### Manual Evolution Workflow
When a parser breaks:
1. Check `evolution-reports/` for failure details
2. Analyze HTML sample to find new structure
3. Update parser logic in `clipper.py`
4. Test with `--test` flag
5. Health tracking will automatically detect improvement

## GitHub Repository

**URL**: https://github.com/whp1989/web-clipper-skill

### 子模块结构

```
web-clipper-skill/
├── SKILL.md                          # 本文件
├── README.md
├── CHANGELOG.md
└── scripts/
    ├── clipper.py                    # 主剪藏脚本
    ├── push-to-github.sh             # 自动推送脚本
    └── zsxq_crawler/                 # 知识星球爬虫子模块
        ├── config.py
        ├── zsxq_cli_client.py        # zsxq-cli 封装
        ├── zsxq_spider.py            # 主爬虫（增量/今日/近期）
        ├── fetch_by_date.py          # 按日期爬取
        ├── api_client.py             # 备用 API 客户端
        └── test_auth.py              # 认证测试
```

### Auto-Push Updates
After modifying `clipper.py`, `SKILL.md`, or `zsxq_crawler/*.py`:

```bash
bash ~/.openclaw/skills/web-clipper/scripts/push-to-github.sh
```

This automatically:
1. Copies latest files to the repo
2. Commits with timestamp and change summary
3. Pushes to GitHub

### For Other Agents
Other agents can install this skill:

```bash
# 完整安装（含知识星球爬虫）
git clone https://github.com/whp1989/web-clipper-skill.git ~/.openclaw/skills/web-clipper

# 仅安装剪藏功能（不含知识星球）
git clone --sparse https://github.com/whp1989/web-clipper-skill.git ~/.openclaw/skills/web-clipper
cd ~/.openclaw/skills/web-clipper
git sparse-checkout set scripts/clipper.py SKILL.md
```

## Error Handling

If `clipper.py` fails:
1. Read the error output
2. Check if it's a network issue, parsing issue, or encoding issue
3. Edit `scripts/clipper.py` to fix the problem
4. Retry the clip
5. Report what was fixed

## Image Handling

- Download images referenced by `<img src="...">` tags
- Save to `{title}_images/` subdirectory
- Rewrite image references in Markdown to local paths
- Skip images that fail to download (log warning)
- Handle HTTP → HTTPS conversion for image URLs

## Dependencies

Pure Python 3 standard library only:
- `urllib.request`
- `html.parser`
- `re`, `json`, `os`, `sys`
- `datetime`, `pathlib`
- `hashlib` (for image deduplication)

No pip install required.

## Audio Transcription (OpenRouter)

For podcast/audio content, the skill can transcribe audio using OpenRouter API:

```bash
# Transcribe with OpenRouter (requires API key)
python3 ~/.openclaw/skills/web-clipper/scripts/clipper.py \
  "https://www.xiaoyuzhoufm.com/episode/xxx" \
  --transcribe \
  --whisper-url "openrouter" \
  --openrouter-key "sk-or-v1-..."
```

**Supported models:**
- `mistralai/voxtral-small-24b-2507` (tested, supports Chinese)
- Other audio-capable models on OpenRouter

**Cost:** ~$0.03 per 5-minute segment

**Note:** Audio is automatically split into 5-minute segments to avoid API limits.

## API 密钥配置（本地存储，不上传GitHub）

OpenRouter API 密钥等敏感信息存储在本地配置文件：

**配置文件路径：**
- `~/.openclaw/workspace/.openclaw/api-config.json`
- `~/.openclaw/api-config.json`（备选）

**配置格式：**
```json
{
  "openrouter_api_key": "sk-or-v1-...",
  "openrouter_model": "mistralai/voxtral-small-24b-2507",
  "audio_segment_minutes": 10,
  "gotify_server": "https://go.pandaponds.com",
  "gotify_token": "your-token-here",
  "gotify_app": "LOGS"
}
```

**配置项说明：**
| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `openrouter_api_key` | OpenRouter API密钥 | 必填 |
| `openrouter_model` | 语音转文字模型 | `mistralai/voxtral-small-24b-2507` |
| `audio_segment_minutes` | 音频分段时长（分钟） | `10` |
| `gotify_server` | Gotify服务器地址 | 可选 |
| `gotify_token` | Gotify应用Token | 可选 |
| `gotify_app` | Gotify应用名称 | 可选 |

**注意：** 此配置文件包含敏感信息，请勿加入Git仓库。skill代码中通过 `load_api_config()` 函数读取此配置。

## Gotify 通知

剪藏完成后，skill会自动发送Gotify通知（如果已配置）：

**通知内容：**
- 标题：✅ 剪藏完成: [来源] 文章标题
- 内容：来源URL、文件名、图片数量、完成时间

**配置步骤：**
1. 在 `api-config.json` 中添加 `gotify_server` 和 `gotify_token`
2. 下次剪藏完成后自动发送通知
3. 通知失败不会阻塞剪藏流程

**优先级：** 5（普通优先级）

## Future Enhancements

- Playwright/Selenium fallback for heavy JS sites
- Automatic parser generation from evolution reports
- Cookie/session persistence for authenticated sites
- Batch URL processing
