#!/usr/bin/env python3
"""
Web Magnet Extractor - Extract magnet links from web pages and save to 磁链.md.
Triggered by "获取网页磁链" keyword.

Supports javbus.com and similar sites.

Selection rules:
1. Always save the largest magnet
2. Also save any magnet with '-U' suffix (uncensored) if it's not already the largest
3. If largest is -U, only save one
"""

import os
import sys
import re
import argparse
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

# Configuration
OUTPUT_BASE = Path("~/.openclaw/workspace/syncthing/raw").expanduser()
ARCHIVE_DIR = OUTPUT_BASE / "归档"

# Try to import requests/playwright
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


def load_api_config():
    """Load API config from local config file."""
    config_paths = [
        Path("~/.openclaw/workspace/.openclaw/api-config.json").expanduser(),
        Path("~/.openclaw/api-config.json").expanduser(),
    ]
    
    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    import json
                    return json.load(f)
            except:
                continue
    
    return {}


def gotify_notify(title, message, priority=5):
    """Send Gotify notification using local config."""
    config = load_api_config()
    
    server = config.get('gotify_server')
    token = config.get('gotify_token')
    
    if not server or not token:
        print(f"  ⚠️ Gotify not configured", file=sys.stderr)
        return False
    
    try:
        import urllib.request
        import urllib.parse
        import json
        
        url = f"{server}/message?token={token}"
        data = urllib.parse.urlencode({
            'title': title,
            'message': message,
            'priority': priority
        }).encode('utf-8')
        
        req = urllib.request.Request(url, data=data, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode('utf-8'))
            if 'id' in result:
                print(f"  [Gotify] 通知已发送: {title}", file=sys.stderr)
                return True
            else:
                print(f"  [Gotify] 发送失败", file=sys.stderr)
                return False
    except Exception as e:
        print(f"  [Gotify] 异常: {e}", file=sys.stderr)
        return False


def trigger_nas_sync():
    """Trigger NAS sync after successful archive."""
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
            return True
        else:
            print(f"⚠️ NAS sync failed: {sync_result.stderr[:200]}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"⚠️ NAS sync trigger failed: {e}", file=sys.stderr)
        return False


def fetch_page_with_requests(url, timeout=15):
    """Fetch page content using requests library."""
    if not HAS_REQUESTS:
        return None, "requests not available"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://www.javbus.com/',
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200:
            return resp.text, None
        else:
            return None, f"HTTP {resp.status_code}"
    except Exception as e:
        return None, str(e)


def fetch_page_with_playwright(url, timeout=30000):
    """Fetch page content using Playwright (handles JS-rendered pages)."""
    if not HAS_PLAYWRIGHT:
        return None, "playwright not available"
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            response = page.goto(url, wait_until='networkidle', timeout=timeout)
            if response:
                content = page.content()
                browser.close()
                return content, None
            else:
                browser.close()
                return None, "Page load failed"
    except Exception as e:
        return None, str(e)


def fetch_page(url):
    """Fetch page content, trying multiple methods."""
    print(f"📡 Fetching: {url}", file=sys.stderr)
    
    # Try requests first (faster)
    content, error = fetch_page_with_requests(url)
    if content:
        print(f"✅ Fetched with requests ({len(content)} chars)", file=sys.stderr)
        return content
    
    print(f"⚠️ requests failed: {error}", file=sys.stderr)
    
    # Fallback to playwright
    content, error = fetch_page_with_playwright(url)
    if content:
        print(f"✅ Fetched with playwright ({len(content)} chars)", file=sys.stderr)
        return content
    
    print(f"❌ playwright failed: {error}", file=sys.stderr)
    return None


def parse_size(size_str):
    """Parse size string like '5.2 GB', '1.3 GB', '800 MB' to bytes."""
    if not size_str:
        return 0
    
    size_str = size_str.strip().upper().replace(',', '')
    
    # Extract number and unit
    match = re.match(r'([\d.]+)\s*([KMGT]?B?)', size_str)
    if not match:
        return 0
    
    num, unit = match.groups()
    try:
        num = float(num)
    except:
        return 0
    
    multipliers = {
        'B': 1,
        'KB': 1024,
        'MB': 1024**2,
        'GB': 1024**3,
        'TB': 1024**4,
        'K': 1024,
        'M': 1024**2,
        'G': 1024**3,
        'T': 1024**4,
    }
    
    return int(num * multipliers.get(unit, 1))


def extract_magnet_links(html_content, base_url=None):
    """
    Extract magnet links from HTML content.
    Returns list of dicts: {'link': str, 'size_str': str, 'size_bytes': int, 'title': str}
    """
    magnets = []
    
    # Pattern 1: Direct magnet links in <a> tags
    magnet_pattern = r'href=["\'](magnet:\?[^"\'\s]+)["\']'
    for match in re.finditer(magnet_pattern, html_content, re.IGNORECASE):
        link = match.group(1)
        # Extract size from nearby text (look within 200 chars before and after)
        start = max(0, match.start() - 200)
        end = min(len(html_content), match.end() + 200)
        context = html_content[start:end]
        
        # Try to find size in context
        size_match = re.search(r'(\d+\.?\d*\s*[KMGT]?B)', context, re.IGNORECASE)
        size_str = size_match.group(1) if size_match else None
        size_bytes = parse_size(size_str) if size_str else 0
        
        # Try to find title
        title_match = re.search(r'title=["\']([^"\']+)["\']', context) or \
                      re.search(r'>([^<]{5,50})<', context)
        title = title_match.group(1).strip() if title_match else ""
        
        magnets.append({
            'link': link,
            'size_str': size_str,
            'size_bytes': size_bytes,
            'title': title
        })
    
    # Pattern 2: JavBus specific - use RSSHub's method
    # Extract gid, uc, img from page and call ajax API
    gid_match = re.search(r"var gid = (\d+);", html_content)
    uc_match = re.search(r"var uc = (\d+);", html_content)
    img_match = re.search(r"var img = '([^']+)';", html_content)
    
    if gid_match and uc_match and base_url:
        gid = gid_match.group(1)
        uc = uc_match.group(1)
        img = img_match.group(1) if img_match else ""
        
        parsed = urlparse(base_url)
        if parsed and parsed.scheme and parsed.netloc:
            # Use the RSSHub-discovered API endpoint
            api_url = f"{parsed.scheme}://{parsed.netloc}/ajax/uncledatoolsbyajax.php"
            
            print(f"🔍 Found JavBus params, trying API: {api_url}", file=sys.stderr)
            
            # Use requests with short timeout
            if HAS_REQUESTS:
                try:
                    resp = requests.get(api_url, params={
                        'gid': gid,
                        'lang': 'zh',
                        'img': img,
                        'uc': uc,
                        'floor': 800,
                    }, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Referer': base_url,
                        'accept-language': 'zh-CN',
                    }, timeout=10)
                    
                    if resp.status_code == 200:
                        # Parse the HTML table response
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(resp.text, 'html.parser')
                        rows = soup.find_all('tr')
                        
                        for tr in rows:
                            tds = tr.find_all('a')
                            if len(tds) >= 3:
                                title = tds[0].text.strip()
                                link = tds[0].get('href', '')
                                size_str = tds[1].text.strip() if len(tds) > 1 else ''
                                
                                if link and link.startswith('magnet:'):
                                    size_bytes = parse_size(size_str)
                                    magnets.append({
                                        'link': link,
                                        'size_str': size_str,
                                        'size_bytes': size_bytes,
                                        'title': title
                                    })
                        
                        print(f"✅ API returned {len(magnets)} magnets", file=sys.stderr)
                except Exception as e:
                    print(f"⚠️ API request failed: {e}", file=sys.stderr)
    
    # Deduplicate by link
    seen = set()
    unique = []
    for m in magnets:
        if m['link'] not in seen:
            seen.add(m['link'])
            unique.append(m)
    
    return unique


def select_magnets_to_archive(magnets):
    """
    Select magnet links to archive.
    Rules:
    1. Always select the largest magnet
    2. Also select any magnet with '-U' suffix in title (uncensored version)
    3. If the largest is also -U, only save one
    
    Returns list of selected magnet dicts.
    """
    if not magnets:
        return []
    
    if len(magnets) == 1:
        return [magnets[0]]
    
    # Sort by size_bytes descending
    sorted_magnets = sorted(magnets, key=lambda x: x['size_bytes'], reverse=True)
    
    print(f"📊 Found {len(magnets)} magnet links:", file=sys.stderr)
    for i, m in enumerate(sorted_magnets[:5], 1):
        size_display = m['size_str'] or f"{m['size_bytes']} bytes"
        title = m['title'][:50] if m['title'] else 'N/A'
        u_flag = " [U]" if title.rstrip().endswith('-U') else ""
        print(f"  {i}. {size_display} - {title}{u_flag}", file=sys.stderr)
    
    selected = []
    
    # 1. Select largest
    largest = sorted_magnets[0]
    selected.append(largest)
    print(f"✅ Selected largest: {largest['size_str'] or 'unknown size'} - {largest['title'][:50]}", file=sys.stderr)
    
    # 2. Check for -U version (if not already the largest)
    largest_is_u = largest['title'] and largest['title'].rstrip().endswith('-U')
    
    if not largest_is_u:
        # Find any -U version
        for m in sorted_magnets[1:]:
            if m['title'] and m['title'].rstrip().endswith('-U'):
                selected.append(m)
                print(f"✅ Also selected -U version: {m['size_str'] or 'unknown size'} - {m['title'][:50]}", file=sys.stderr)
                break
    
    return selected


def archive_magnets_to_file(magnets_list, source_url=None):
    """
    Append multiple magnet links to the archive file.
    Uses the same logic as archive_links.py for consistency.
    Each link on its own line, no extra info.
    
    Returns:
        (file_path, list_of_added_links, list_of_skipped_links)
    """
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    magnet_file = ARCHIVE_DIR / "磁链.md"
    now = datetime.now()
    
    added = []
    skipped = []
    
    # Build content to append
    new_links_content = []
    
    for magnet in magnets_list:
        magnet_link = magnet['link'] if isinstance(magnet, dict) else magnet
        
        if magnet_file.exists():
            existing = magnet_file.read_text(encoding='utf-8')
            if magnet_link in existing:
                skipped.append(magnet)
                print(f"⚠️ Magnet already exists, skipping: {magnet_link[:60]}...", file=sys.stderr)
                continue
        
        new_links_content.append(magnet_link)
        added.append(magnet)
    
    if not new_links_content:
        return str(magnet_file), added, skipped
    
    # Join all new links
    magnet_content = '\n'.join(new_links_content)
    
    if magnet_file.exists():
        # Append to existing file
        existing = magnet_file.read_text(encoding='utf-8')
        existing = existing.rstrip()
        if existing:
            new_content = existing + '\n' + magnet_content + '\n'
        else:
            new_content = magnet_content + '\n'
    else:
        # Create new file with header
        new_content = f"""---
title: 磁链存档
created: {now.isoformat()}
---

# 磁链存档

> 收集的磁力链接，按添加时间顺序排列

{magnet_content}
"""
    
    magnet_file.write_text(new_content, encoding='utf-8')
    print(f"✅ 已保存 {len(new_links_content)} 个磁链到: {magnet_file}", file=sys.stderr)
    
    return str(magnet_file), added, skipped


def extract_from_url(url):
    """
    Main function: extract magnet from URL and archive it.
    
    Returns:
        dict: {'success': bool, 'magnet': str or None, 'file': str or None, 'message': str}
    """
    # Fetch page
    html = fetch_page(url)
    if not html:
        return {
            'success': False,
            'magnet': None,
            'file': None,
            'message': f"Failed to fetch page: {url}"
        }
    
    # Extract magnet links
    magnets = extract_magnet_links(html, url)
    
    if not magnets:
        return {
            'success': False,
            'magnet': None,
            'file': None,
            'message': f"No magnet links found on page: {url}"
        }
    
    # Select magnets to archive (largest + -U version if different)
    selected_magnets = select_magnets_to_archive(magnets)
    
    if not selected_magnets:
        return {
            'success': False,
            'magnet': None,
            'file': None,
            'message': "Failed to select magnet link"
        }
    
    # Archive them
    file_path, added, skipped = archive_magnets_to_file(selected_magnets, url)
    
    if not added:
        return {
            'success': True,
            'magnet': selected_magnets[0]['link'],
            'file': file_path,
            'message': "All magnets already exist in archive"
        }
    
    # Build notification message
    added_info = []
    for m in added:
        size_display = m['size_str'] or "unknown size"
        u_flag = " [U]" if m['title'] and m['title'].rstrip().endswith('-U') else ""
        added_info.append(f"{size_display}{u_flag}: {m['link'][:60]}...")
    
    # Notify
    gotify_notify(
        "网页磁链提取完成",
        f"URL: {url}\nSaved {len(added)} magnet(s):\n" + "\n".join(added_info),
        priority=5
    )
    
    # Trigger NAS sync
    trigger_nas_sync()
    
    return {
        'success': True,
        'magnet': selected_magnets[0]['link'],
        'file': file_path,
        'message': f"Archived {len(added)} magnet(s) from {url}"
    }


def main():
    parser = argparse.ArgumentParser(description='Extract magnet links from web pages')
    parser.add_argument('url', help='URL to extract magnet from')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be archived without saving')
    
    args = parser.parse_args()
    
    result = extract_from_url(args.url)
    
    if result['success']:
        print(f"SUCCESS:{result['magnet']}")
        print(f"FILE:{result['file']}")
        print(f"MESSAGE:{result['message']}")
    else:
        print(f"ERROR:{result['message']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
