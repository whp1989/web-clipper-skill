---
name: web-clipper-archive
description: Archive user content to local Markdown files. Use when the user says "归档", "archive", "保存这个", "存起来", "稍后读", "read later", or any request to save user-provided content (not URLs) to the syncthing folder. Stores content in ~/.openclaw/workspace/syncthing/raw/归档/.
---

# Web Clipper - Archive Sub-Skill

## Purpose

Save user-provided content (text, notes, summaries, etc.) as Markdown files to a local syncthing-synced folder. This is for **user-generated or user-shared content**, not web URLs.

## When to Use

Trigger this sub-skill when:
- User says **"归档"**, **"archive"**, **"保存这个"**, **"存起来"**
- User says **"稍后读"**, **"read later"**, **"稍后看"**
- User provides content they want to keep (text, notes, thoughts, summaries)
- User explicitly requests to archive something (not clip a URL)

**Do NOT use for URLs** — use the main `clipper.py` for web links.

## Two Modes

### 1. 归档模式 (Archive Mode) - Default
- Creates a new Markdown file for each piece of content
- File name based on LLM-generated title or user-provided title
- Location: `syncthing/raw/归档/{title}.md`
- Triggered by: "归档", "archive", "保存这个", "存起来"

### 2. 稍后读模式 (Read Later Mode)
- Appends content to a single shared file: `稍后读.md`
- New entries added at the **top** (most recent first)
- Entries separated by dividers (`---`)
- Location: `syncthing/raw/归档/稍后读.md`
- Triggered by: "稍后读", "read later", "稍后看"

## Workflow

### Archive Mode (归档)
1. **Extract** the content to be archived (from user message)
2. **Generate** a title (from user input or auto-generated)
3. **Save** to `syncthing/raw/归档/{title}.md`
4. **Trigger** NAS sync automatically

### Read Later Mode (稍后读)
1. **Extract** the content to save
2. **Get** a title (user-provided or auto-generated)
3. **Append** to top of `syncthing/raw/归档/稍后读.md`
4. **Trigger** NAS sync automatically

## Script

Use `scripts/archive.py` for the archiving operation.

```bash
# Archive mode (default)
python3 ~/.openclaw/skills/web-clipper/scripts/archive.py "<content>" "<title>" "<source_info>"

# Read Later mode
python3 ~/.openclaw/skills/web-clipper/scripts/archive.py "<content>" "<title>" "<source_info>" --read-later
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `content` | ✅ | The text content to archive |
| `title` | ❌ | Document title (auto-generated if omitted) |
| `source_info` | ❌ | Source context (e.g., "from user message", "meeting notes") |
| `--read-later` | ❌ | If present, append to 稍后读.md instead of creating new file |

## Output Location

### Archive Mode
- Base dir: `~/.openclaw/workspace/syncthing/raw/归档/`
- Filename: `{sanitized_title}.md` (or `archive_HHMMSS.md` if no title)

### Read Later Mode
- File: `~/.openclaw/workspace/syncthing/raw/归档/稍后读.md`
- Format: Single file with multiple entries, newest at top

## 稍后读.md Structure

```markdown
---
title: 稍后读
created: 2026-05-10T19:20:00
---

# 稍后读

> 收集待阅读的内容，按时间倒序排列（最新的在最上面）

---

## Article Title 3

**添加时间**: 2026-05-10 19:25:00
**来源**: User message

Content of the third article...

---

## Article Title 2

**添加时间**: 2026-05-10 19:22:00
**来源**: User message

Content of the second article...

---

## Article Title 1

**添加时间**: 2026-05-10 19:20:00
**来源**: User message

Content of the first article...

---
```

## Behavior Rules

- **Auto-trigger**: When "归档" or "稍后读" keyword is detected in user message, automatically execute
- **Title handling**: If user provides a title, use it; otherwise auto-generate from content or timestamp
- **Duplicate handling**: For archive mode, append counter (`_1`, `_2`, etc.) if filename exists
- **NAS sync**: Automatically triggers NAS sync after successful save
- **Silent mode**: Save silently, only report success/failure

## Content Format

### Archive Mode
Archived Markdown includes:
- YAML frontmatter with title, archived timestamp, source info
- Formatted content with headers
- Archive timestamp and source attribution

### Read Later Mode
Each entry includes:
- `---` separator before each entry
- H2 heading with title
- **添加时间** timestamp
- **来源** attribution (if provided)
- Content body

## Example Usage

```bash
# Archive with title
python3 ~/.openclaw/skills/web-clipper/scripts/archive.py \
  "This is my important note about the meeting..." \
  "Meeting Notes - Project Alpha"

# Add to read later list
python3 ~/.openclaw/skills/web-clipper/scripts/archive.py \
  "Interesting article about AI trends..." \
  "AI Trends Article" \
  "from user message" \
  --read-later

# Read later without title (auto-generated)
python3 ~/.openclaw/skills/web-clipper/scripts/archive.py \
  "Quick thought: need to review the Q3 report" \
  "" \
  "" \
  --read-later
```

## Integration with Main Skill

This is a **sub-skill** of `web-clipper`. The main skill handles URLs; this sub-skill handles user content.

**Detection priority:**
1. If input is a URL → use `clipper.py`
2. If input contains "稍后读" or "read later" → use `archive.py --read-later`
3. If input contains "归档" or is user content → use `archive.py`

## GitHub Repository

Same as main skill: https://github.com/whp1989/web-clipper-skill

Archive tool is included in the same repository under `scripts/archive.py`.

## Future Enhancements

- Support for tagging archived content
- Auto-categorization based on content analysis
- Integration with wiki system for structured archiving
- Support for archiving images/attachments alongside text
- Read later item management (mark as read, delete, prioritize)
