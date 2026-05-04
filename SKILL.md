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
| 其他网站 | * | Generic HTML parser | ❌ |

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

### Auto-Push Updates
After modifying `clipper.py` or `SKILL.md`:
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
git clone https://github.com/whp1989/web-clipper-skill.git ~/.openclaw/skills/web-clipper
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
