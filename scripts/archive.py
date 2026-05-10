#!/usr/bin/env python3
"""
Archive Tool - Save user content to local Markdown files in archive folder.
Triggered by keyword "归档" (archive).
"""

import os
import sys
import re
from datetime import datetime
from pathlib import Path

# Configuration
OUTPUT_BASE = Path("~/.openclaw/workspace/syncthing/raw").expanduser()


def load_api_key():
    """Load API key from local config file."""
    config_paths = [
        Path("~/.openclaw/workspace/.openclaw/api-config.json").expanduser(),
        Path("~/.openclaw/api-config.json").expanduser(),
    ]
    
    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    key = config.get('openrouter_api_key')
                    if key:
                        return key
            except:
                continue
    
    # Fallback: try environment variable
    return os.environ.get('OPENROUTER_API_KEY', '')


def generate_title(content):
    """Generate a concise title from content using LLM."""
    try:
        import urllib.request
        import json
        
        # Load API key from config
        api_key = load_api_key()
        if not api_key:
            print("⚠️ No API key found, using fallback title", file=sys.stderr)
            raise Exception("No API key available")
        
        # Truncate content if too long
        max_chars = 2000
        truncated = content[:max_chars] if len(content) > max_chars else content
        
        prompt = f"""请为以下内容生成一个简洁的中文标题（不超过15个字），只输出标题本身，不要任何额外内容：

{truncated}

标题："""
        
        payload = {
            "model": "kimi-coding/k2p5",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 50,
            "temperature": 0.3
        }
        
        req = urllib.request.Request(
            "https://api.moonshot.cn/v1/chat/completions",
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            },
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            if 'choices' in result and len(result['choices']) > 0:
                title = result['choices'][0].get('message', {}).get('content', '').strip()
                # Clean up title
                title = re.sub(r'^["\'\s]+|["\'\s]+$', '', title)
                title = re.sub(r'^(标题|Title)[:\s]*', '', title, flags=re.IGNORECASE)
                if title and len(title) > 3:
                    print(f"📝 LLM generated title: {title}", file=sys.stderr)
                    return title
    except Exception as e:
        print(f"⚠️ LLM title generation failed: {e}", file=sys.stderr)
    
    # Fallback: use first line or timestamp
    first_line = content.strip().split('\n')[0][:30]
    if len(first_line) > 5:
        return first_line
    
    timestamp = datetime.now().strftime("%H%M%S")
    return f"archive_{timestamp}"


def sanitize_filename(name, max_len=80):
    """Sanitize string for use as filename."""
    sanitized = re.sub(r'[^\w\s-]', '_', name)
    sanitized = re.sub(r'\s+', '_', sanitized)
    sanitized = sanitized.strip('_')
    
    if len(sanitized) > max_len:
        sanitized = sanitized[:max_len]
    
    if not sanitized:
        sanitized = "untitled"
    
    return sanitized


def archive_content(content, title=None, source_info=None):
    """
    Save content to archive folder.
    
    Args:
        content: The text content to archive
        title: Optional title for the document
        source_info: Optional source information (e.g., who sent it, context)
    
    Returns:
        Path to saved file
    """
    # Archive directory at same level as date folders
    archive_dir = OUTPUT_BASE / "归档"
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate title if not provided
    if not title:
        title = generate_title(content)
    
    base_name = sanitize_filename(title)
    
    md_path = archive_dir / f"{base_name}.md"
    
    # Handle duplicate filenames
    counter = 1
    original_path = md_path
    while md_path.exists():
        md_path = original_path.parent / f"{base_name}_{counter}.md"
        counter += 1
    
    # Build markdown content
    now = datetime.now()
    
    markdown = f"""---
title: {title or '归档内容'}
archived: {now.isoformat()}
{'' if not source_info else f'source: {source_info}'}
---

# {title or '归档内容'}

**归档时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}
{'' if not source_info else f'**来源**: {source_info}'}

---

{content}

---

*Archived by archive-tool*
"""
    
    # Save file
    md_path.write_text(markdown, encoding='utf-8')
    
    print(f"✅ Archived: {md_path}", file=sys.stderr)
    
    # Trigger NAS sync
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
        else:
            print(f"⚠️ NAS sync failed: {sync_result.stderr[:200]}", file=sys.stderr)
    except Exception as e:
        print(f"⚠️ NAS sync trigger failed: {e}", file=sys.stderr)
    
    return str(md_path)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 archive.py <content> [title] [source_info]", file=sys.stderr)
        sys.exit(1)
    
    content = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else None
    source_info = sys.argv[3] if len(sys.argv) > 3 else None
    
    try:
        result = archive_content(content, title, source_info)
        print(f"SUCCESS:{result}")
    except Exception as e:
        print(f"ERROR:{str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
