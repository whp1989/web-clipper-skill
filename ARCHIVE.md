---
name: web-clipper-archive
description: Archive user content to local Markdown files. Use when the user says "归档", "archive", "保存这个", "存起来", or any request to save user-provided content (not URLs) to the syncthing folder. Stores content in ~/.openclaw/workspace/syncthing/raw/YYYY-MM-DD/归档/.
---

# Web Clipper - Archive Sub-Skill

## Purpose

Save user-provided content (text, notes, summaries, etc.) as Markdown files to a local syncthing-synced folder. This is for **user-generated or user-shared content**, not web URLs.

## When to Use

Trigger this sub-skill when:
- User says **"归档"**, **"archive"**, **"保存这个"**, **"存起来"**
- User provides content they want to keep (text, notes, thoughts, summaries)
- User explicitly requests to archive something (not clip a URL)

**Do NOT use for URLs** — use the main `clipper.py` for web links.

## Workflow

When triggered by "归档" keyword:

1. **Extract** the content to be archived (from user message)
2. **Generate** a title (from user input or auto-generated)
3. **Save** to `~/.openclaw/workspace/syncthing/raw/YYYY-MM-DD/归档/`
4. **Trigger** NAS sync automatically

## Script

Use `scripts/archive.py` for the archiving operation.

```bash
python3 ~/.openclaw/skills/web-clipper/scripts/archive.py "<content>" "<title>" "<source_info>"
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `content` | ✅ | The text content to archive |
| `title` | ❌ | Document title (auto-generated if omitted) |
| `source_info` | ❌ | Source context (e.g., "from user message", "meeting notes") |

## Output Location

- Base dir: `~/.openclaw/workspace/syncthing/raw/`
- Subdir: `归档/` (same level as date folders)
- Filename: `{sanitized_title}.md` (or `archive_HHMMSS.md` if no title)

## Behavior Rules

- **Auto-trigger**: When "归档" keyword is detected in user message, automatically execute
- **Title handling**: If user provides a title, use it; otherwise auto-generate from content or timestamp
- **Duplicate handling**: If filename exists, append counter (`_1`, `_2`, etc.)
- **NAS sync**: Automatically triggers NAS sync after successful archive
- **Silent mode**: Save silently, only report success/failure

## Content Format

Archived Markdown includes:
- YAML frontmatter with title, archived timestamp, source info
- Formatted content with headers
- Archive timestamp and source attribution

## Example Usage

```bash
# Archive with title
python3 ~/.openclaw/skills/web-clipper/scripts/archive.py \
  "This is my important note about the meeting..." \
  "Meeting Notes - Project Alpha"

# Archive without title (uses timestamp)
python3 ~/.openclaw/skills/web-clipper/scripts/archive.py \
  "Quick thought: need to review the Q3 report"
```

## Integration with Main Skill

This is a **sub-skill** of `web-clipper`. The main skill handles URLs; this sub-skill handles user content.

**Detection priority:**
1. If input is a URL → use `clipper.py`
2. If input contains "归档" or is user content → use `archive.py`

## GitHub Repository

Same as main skill: https://github.com/whp1989/web-clipper-skill

Archive tool is included in the same repository under `scripts/archive.py`.

## Future Enhancements

- Support for tagging archived content
- Auto-categorization based on content analysis
- Integration with wiki system for structured archiving
- Support for archiving images/attachments alongside text
