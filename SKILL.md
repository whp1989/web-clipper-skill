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

| Site | Domain | Parser Type |
|------|--------|-------------|
| 华尔街见闻 | wallstreetcn.com | JSON embedded data |
| 少数派 | sspai.com | HTML structure |
| Bilibili | bilibili.com | JSON (__INITIAL_STATE__) |
| 微信公众号 | mp.weixin.qq.com | HTML + image extraction |
| 其他网站 | * | Generic HTML parser |

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

## Future Enhancements

- Playwright/Selenium fallback for heavy JS sites
- Automatic parser generation from evolution reports
- Cookie/session persistence for authenticated sites
- Batch URL processing
