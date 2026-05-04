#!/usr/bin/env python3
"""
Web Clipper - Save web articles as Markdown with images.
Supports site-specific parsers + fallback to generic HTML parsing.
"""

import urllib.request
import urllib.error
import urllib.parse
import re
import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path
from html.parser import HTMLParser

# Configuration
OUTPUT_BASE = Path("~/.openclaw/workspace/syncthing/raw").expanduser()
USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"

# Site-specific parsers registry
SITE_PARSERS = {}
PARSER_HEALTH = {}  # Track parser success/failure rates

def register_parser(domain):
    """Decorator to register a site-specific parser."""
    def decorator(func):
        SITE_PARSERS[domain] = func
        PARSER_HEALTH[domain] = {'success': 0, 'failure': 0, 'last_error': None}
        return func
    return decorator


def check_parser_health(domain, result):
    """Check if parser is working correctly."""
    if domain not in PARSER_HEALTH:
        return
    
    health = PARSER_HEALTH[domain]
    
    # Check for failure conditions
    if result is None:
        health['failure'] += 1
        health['last_error'] = 'Parser returned None'
    elif not result.get('title') or result.get('title') in ('', 'Untitled'):
        health['failure'] += 1
        health['last_error'] = 'Empty title'
    elif not result.get('content') and not result.get('audio_url'):
        health['failure'] += 1
        health['last_error'] = 'No content or audio'
    else:
        health['success'] += 1
    
    # Log health status
    total = health['success'] + health['failure']
    if total > 0:
        success_rate = health['success'] / total
        print(f"📊 Parser health for {domain}: {success_rate:.1%} ({health['success']}/{total})", file=sys.stderr)
        
        # Warn if failure rate is high
        if total >= 3 and success_rate < 0.5:
            print(f"⚠️ WARNING: Parser for {domain} has low success rate! Last error: {health['last_error']}", file=sys.stderr)
            print(f"🔧 Consider checking website structure or updating parser", file=sys.stderr)


def diagnose_failure(url, html, result, error=None):
    """Diagnose why parsing failed and suggest fixes."""
    diagnosis = {
        'url': url,
        'html_length': len(html),
        'has_title': bool(result and result.get('title')),
        'has_content': bool(result and result.get('content') and len(result.get('content', '')) > 100),
        'has_audio': bool(result and result.get('audio_url')),
        'error': error,
        'suggestions': []
    }
    
    # Check for common issues
    if len(html) < 5000:
        diagnosis['suggestions'].append('HTML too short - may need JavaScript rendering (Playwright/Selenium)')
    
    if 'window.__INITIAL_STATE__' in html or 'window.__DATA__' in html:
        diagnosis['suggestions'].append('Found embedded JSON data - check JSON parsing logic')
    
    if 'anti-bot' in html.lower() or 'captcha' in html.lower():
        diagnosis['suggestions'].append('Anti-bot protection detected - may need cookie/session handling')
    
    if result and not result.get('title'):
        diagnosis['suggestions'].append('Title extraction failed - check title selectors')
    
    if result and not result.get('content') and not result.get('audio_url'):
        diagnosis['suggestions'].append('Content/audio extraction failed - check content container selectors')
    
    # Check for structure changes
    if html and not diagnosis['has_content'] and not diagnosis['has_audio']:
        # Look for common content containers
        containers = ['article', 'main', '.content', '.post', '.entry']
        found = []
        for container in containers:
            if container.startswith('.'):
                pattern = f'class="[^"]*{container[1:]}[^"]*"'
            else:
                pattern = f'<{container}[\\s>]'
            if re.search(pattern, html, re.IGNORECASE):
                found.append(container)
        if found:
            diagnosis['suggestions'].append(f'Found potential containers: {found}')
    
    return diagnosis


def save_evolution_report(url, html, result, error=None, output_dir=None):
    """Save failure details for later analysis and parser evolution."""
    if output_dir is None:
        output_dir = OUTPUT_BASE / 'evolution-reports'
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate report filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    domain = get_domain(url).replace('.', '_')
    report_file = output_dir / f"{timestamp}_{domain}_report.json"
    
    # Build report
    report = {
        'timestamp': datetime.now().isoformat(),
        'url': url,
        'domain': domain,
        'html_length': len(html),
        'html_sample': html[:5000] if html else '',  # First 5000 chars for analysis
        'result': {
            'has_title': bool(result and result.get('title')),
            'title': result.get('title', '') if result else '',
            'content_length': len(result.get('content', '')) if result else 0,
            'content_sample': result.get('content', '')[:500] if result else '',
            'image_count': len(result.get('images', [])) if result else 0,
        },
        'error': error,
        'parser_health': PARSER_HEALTH.get(domain, {}),
        'diagnosis': diagnose_failure(url, html, result, error) if not (result and result.get('content') and len(result.get('content', '')) > 100) else None,
    }
    
    # Save report
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"📋 Evolution report saved: {report_file}", file=sys.stderr)
    return report_file
    """Diagnose why parsing failed and suggest fixes."""
    diagnosis = {
        'url': url,
        'html_length': len(html),
        'has_title': bool(result and result.get('title')),
        'has_content': bool(result and result.get('content') and len(result.get('content', '')) > 100),
        'error': error,
        'suggestions': []
    }
    
    # Check for common issues
    if len(html) < 5000:
        diagnosis['suggestions'].append('HTML too short - may need JavaScript rendering (Playwright/Selenium)')
    
    if 'window.__INITIAL_STATE__' in html or 'window.__DATA__' in html:
        diagnosis['suggestions'].append('Found embedded JSON data - check JSON parsing logic')
    
    if 'anti-bot' in html.lower() or 'captcha' in html.lower():
        diagnosis['suggestions'].append('Anti-bot protection detected - may need cookie/session handling')
    
    if result and not result.get('title'):
        diagnosis['suggestions'].append('Title extraction failed - check title selectors')
    
    if result and not result.get('content'):
        diagnosis['suggestions'].append('Content extraction failed - check content container selectors')
    
    # Check for structure changes
    if html and not diagnosis['has_content']:
        # Look for common content containers
        containers = ['article', 'main', '.content', '.post', '.entry']
        found = []
        for container in containers:
            if container.startswith('.'):
                pattern = f'class="[^"]*{container[1:]}[^"]*"'
            else:
                pattern = f'<{container}[\\s>]'
            if re.search(pattern, html, re.IGNORECASE):
                found.append(container)
        if found:
            diagnosis['suggestions'].append(f'Found potential containers: {found}')
    
    return diagnosis


# ========== Audio Extraction Functions ==========
def extract_audio_url(html, url):
    """Extract audio URL from podcast pages (e.g., Xiaoyuzhou FM)."""
    audio_patterns = [
        r'"mp3Url"[:\s]*"([^"]+)"',
        r'"audioUrl"[:\s]*"([^"]+)"',
        r'"mediaUrl"[:\s]*"([^"]+)"',
        r'"playUrl"[:\s]*"([^"]+)"',
        r'"url"[:\s]*"([^"]+\.(?:mp3|m4a|aac|ogg))"',
        r'https?://[^"\'<>\s]+\.(?:mp3|m4a|aac|ogg)',
    ]
    
    for pattern in audio_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0]
            if match and match.startswith('http'):
                return match
    
    return None


def download_audio(url, output_path, timeout=120):
    """Download audio file to local path."""
    try:
        headers = {'User-Agent': USER_AGENT}
        req = urllib.request.Request(url, headers=headers)
        
        print(f"🎵 Downloading audio: {url[:60]}...", file=sys.stderr)
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read()
            
            if len(data) < 1000:
                print(f"  ⚠️ Audio file too small: {len(data)} bytes", file=sys.stderr)
                return False
            
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(data)
            
            size_mb = len(data) / (1024 * 1024)
            print(f"  ✅ Audio saved: {output_path} ({size_mb:.1f} MB)", file=sys.stderr)
            return True
    
    except Exception as e:
        print(f"  ❌ Audio download failed: {e}", file=sys.stderr)
        return False


# ========== Xiaoyuzhou FM Parser ==========
@register_parser("xiaoyuzhoufm.com")
def parse_xiaoyuzhou(html, url):
    """Parse Xiaoyuzhou FM episode page and extract audio."""
    result = {
        'title': None,
        'content': '',
        'description': '',
        'images': [],
        'audio_url': None,
        'audio_file': None,
    }
    
    # Extract title
    title_match = re.search(r'<title>(.*?)</title>', html, re.DOTALL)
    if title_match:
        title = title_match.group(1).strip()
        # Remove site name suffix
        title = re.sub(r'\s*[-|]\s*小宇宙.*$', '', title)
        title = re.sub(r'\s*[-|]\s*听播客.*$', '', title)
        result['title'] = title
    
    # Extract description from meta
    description = extract_meta_content(html, 'description')
    if description:
        result['description'] = description
        result['content'] = description
    
    # Extract audio URL
    audio_url = extract_audio_url(html, url)
    if audio_url:
        result['audio_url'] = audio_url
        print(f"🎵 Found audio URL: {audio_url[:60]}...", file=sys.stderr)
    
    return result


# ========== Wall Street CN Parser ==========
@register_parser("wallstreetcn.com")
def parse_wallstreetcn(html, url):
    """Parse Wall Street CN articles and live news."""
    # Extract article ID from URL
    article_id = None
    id_match = re.search(r'/(?:articles|livenews)/(\d+)', url)
    if id_match:
        article_id = id_match.group(1)
    
    if not article_id:
        return None
    
    # Find the article ID in HTML
    pos = html.find(f'"id":{article_id}')
    if pos < 0:
        pos = html.find(f'"id": {article_id}')
    
    if pos < 0:
        return None
    
    # Find the article object or live_news object
    article_start = html.find('"article":{', pos)
    if article_start < 0:
        # Try livenews format (different structure)
        article_start = html.find('"live_news":{', pos)
        if article_start < 0:
            article_start = html.find('"livenews":{', pos)
    
    # If no nested object found, the data might be at the top level
    # Look for content or title directly after the ID
    if article_start < 0:
        # Try to find content or title field directly
        content_start = html.find('"content":', pos)
        title_start = html.find('"title":', pos)
        
        if content_start > 0 or title_start > 0:
            # This is a flat structure (livenews)
            # The data might be in an array element or in the top level object
            # We need to find the object that contains both "id" and "title"
            # Search backwards from pos to find the correct opening brace
            brace_start = -1
            search_limit = max(0, pos - 3000)
            
            for i in range(pos - 1, search_limit, -1):
                if html[i] == '{':
                    # Check if this brace is followed by "id" or "title" within reasonable distance
                    snippet = html[i:min(len(html), i+200)]
                    if '"id":' in snippet or '"title":' in snippet:
                        brace_start = i
                        break
            
            if brace_start > 0:
                article_json = extract_json_object(html, brace_start)
                if article_json:
                    try:
                        article_data = json.loads(article_json)
                    except json.JSONDecodeError as e:
                        print(f"  JSON decode error: {e}", file=sys.stderr)
                        return parse_wallstreetcn_legacy(html, url, pos, pos)
                else:
                    return parse_wallstreetcn_legacy(html, url, pos, pos)
            else:
                return parse_wallstreetcn_legacy(html, url, pos, pos)
        else:
            return None
    else:
        # Extract article JSON - find matching braces
        # Determine the field name
        if html[article_start:article_start+12] == '"live_news":{':
            field_len = len('"live_news":')
        elif html[article_start:article_start+11] == '"livenews":{':
            field_len = len('"livenews":')
        else:
            field_len = len('"article":')
        
        article_json = extract_json_object(html, article_start + field_len - 1)
        if not article_json:
            # Fallback: use old method
            return parse_wallstreetcn_legacy(html, url, pos, article_start)
        
        try:
            article_data = json.loads(article_json)
        except json.JSONDecodeError as e:
            print(f"  JSON decode error: {e}", file=sys.stderr)
            return parse_wallstreetcn_legacy(html, url, pos, article_start)
    
    # Extract title
    title = article_data.get('title', '')
    if not title:
        title = article_data.get('content_title', '')
    
    # Clean title
    title = title.replace('\\"', '"').strip()
    
    # Extract content
    content = article_data.get('content', '')
    if not content:
        content = article_data.get('content_text', '')
    if not content:
        content = article_data.get('text', '')
    
    # For livenews, the content might be HTML
    if content and content.startswith('<'):
        # It's HTML content, keep it as is for html_to_markdown to process
        pass
    
    # Unescape content
    if content:
        content = content.replace('\\n', '\n').replace('\\t', '\t')
        content = content.replace('\\u003C', '<').replace('\\u003c', '<')
        content = content.replace('\\u003E', '>').replace('\\u003e', '>')
        content = content.replace('\\/', '/')
        content = content.replace('\\"', '"')
        content = content.replace("\\'", "'")
    
    # Extract images from multiple possible fields
    images = []
    seen_urls = set()
    
    # 2. Check images array
    image_list = article_data.get('images', [])
    if isinstance(image_list, list):
        for img in image_list:
            if isinstance(img, dict):
                img_url = img.get('url') or img.get('src') or img.get('uri')
            elif isinstance(img, str):
                img_url = img
            else:
                img_url = None
            
            if img_url and img_url not in seen_urls:
                seen_urls.add(img_url)
                images.append((img_url, ''))
    
    # 3. Check single image field (could be dict or string)
    single_image = article_data.get('image')
    if single_image:
        if isinstance(single_image, dict):
            img_url = single_image.get('url') or single_image.get('src') or single_image.get('uri')
        elif isinstance(single_image, str):
            img_url = single_image
        else:
            img_url = None
        
        if img_url and img_url not in seen_urls:
            seen_urls.add(img_url)
            images.append((img_url, ''))
    
    # 3. Check cover_image
    cover = article_data.get('cover_image')
    if cover and isinstance(cover, dict):
        cover_url = cover.get('url') or cover.get('uri') or cover.get('src')
        if cover_url and cover_url not in seen_urls:
            seen_urls.add(cover_url)
            images.append((cover_url, '封面'))
    elif cover and isinstance(cover, str) and cover not in seen_urls:
        seen_urls.add(cover)
        images.append((cover, '封面'))
    
    # 4. Extract images from content HTML
    if content:
        content_images = re.findall(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', content)
        for img_url in content_images:
            if img_url not in seen_urls:
                seen_urls.add(img_url)
                images.append((img_url, ''))
    
    # 5. For livenews, check live_news_images field
    live_images = article_data.get('live_news_images', [])
    if isinstance(live_images, list):
        for img in live_images:
            if isinstance(img, dict):
                img_url = img.get('url') or img.get('src') or img.get('uri')
            elif isinstance(img, str):
                img_url = img
            else:
                img_url = None
            
            if img_url and img_url not in seen_urls:
                seen_urls.add(img_url)
                images.append((img_url, ''))
    
    # 6. Check for image in JSON-LD or meta
    if not images:
        # Try to find image in the full HTML
        og_image = extract_meta_content(html, 'og:image')
        if og_image and og_image not in seen_urls:
            seen_urls.add(og_image)
            images.append((og_image, ''))
    
    if not content:
        return None
    
    return {
        'title': title,
        'content': content,
        'images': images
    }


def extract_json_object(html, start_pos):
    """Extract a JSON object from HTML starting at given position."""
    # Find opening brace
    brace_start = html.find('{', start_pos)
    if brace_start < 0:
        return None
    
    # Track brace depth
    depth = 1
    in_string = False
    escape_next = False
    
    i = brace_start + 1
    while i < len(html) and depth > 0:
        char = html[i]
        
        if escape_next:
            escape_next = False
        elif char == '\\':
            escape_next = True
        elif char == '"' and not in_string:
            in_string = True
        elif char == '"' and in_string:
            in_string = False
        elif not in_string:
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
        
        i += 1
    
    if depth == 0:
        return html[brace_start:i]
    
    return None


def parse_wallstreetcn_legacy(html, url, pos, article_start):
    """Legacy parser for Wall Street CN (fallback)."""
    # Extract title from article object
    article_html = html[article_start:article_start+10000]
    titles = list(re.finditer(r'"title"\s*:\s*"([^"]*)"', article_html, re.DOTALL))
    
    title = ""
    for m in titles:
        context = article_html[max(0, m.start()-50):m.start()]
        if 'audio' in context:
            continue
        after = article_html[m.end():m.end()+100]
        if 'tags' in after or 'themes' in after:
            if m.group(1).strip():
                title = m.group(1).replace('\\"', '"')
                break
    
    if not title:
        for m in reversed(titles):
            if m.group(1).strip():
                title = m.group(1).replace('\\"', '"')
                break
    
    # Extract content
    content = ""
    content_start = html.find('"content":', pos)
    if content_start > 0:
        quote_start = html.find('"', content_start + len('"content":'))
        if quote_start > 0:
            i = quote_start + 1
            while i < len(html):
                if html[i] == '\\' and i + 1 < len(html) and html[i + 1] == '"':
                    i += 2
                elif html[i] == '"':
                    break
                else:
                    i += 1
            
            if i < len(html):
                content = html[quote_start + 1:i]
                content = content.replace('\\n', '\n').replace('\\t', '\t')
                content = content.replace('\\u003C', '<').replace('\\u003c', '<')
                content = content.replace('\\u003E', '>').replace('\\u003e', '>')
                content = content.replace('\\/', '/')
                content = content.replace('\\"', '"')
                content = content.replace("\\'", "'")
    
    if not content:
        return None
    
    return {
        'title': title,
        'content': content,
        'images': []
    }


# ========== SSPAI (少数派) Parser ==========
@register_parser("sspai.com")
def parse_sspai(html, url):
    """Parse SSPAI articles."""
    # Try to find the article content in the HTML
    # SSPAI uses Vue.js rendered content
    
    # Look for article content in the HTML directly
    # The content is in <div class="article__main__content wangEditor-txt">
    
    # Method 1: Try to extract from Vue SSR data
    # Look for __INITIAL_STATE__ or __DATA__
    for pattern in [
        r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});',
        r'window\.__DATA__\s*=\s*(\{.*?\});',
        r'<script[^>]*>window\.__INITIAL_STATE__\s*=\s*(\{.*?\})</script>',
    ]:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                # Navigate to find article content
                if 'article' in data:
                    article = data['article']
                    if isinstance(article, dict):
                        title = article.get('title', '')
                        content = article.get('content', '')
                        if content:
                            return {
                                'title': title,
                                'content': content,
                                'images': []
                            }
            except:
                pass
    
    # Method 2: Extract directly from HTML structure
    # Find article title
    title = ""
    
    # Try h1 with article class
    title_match = re.search(r'<h1[^>]*class="[^"]*article[^"]*"[^>]*>(.*?)</h1>', html, re.DOTALL | re.IGNORECASE)
    if not title_match:
        # Try any h1
        title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL | re.IGNORECASE)
    if title_match:
        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
    
    # Fallback: try meta title
    if not title:
        title_match = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"', html, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
    
    # Fallback: try title tag
    if not title:
        title_match = re.search(r'<title>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
        if title_match:
            title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
    
    # Find article content - look for the main content div
    content = ""
    content_patterns = [
        r'<div[^>]*class="article__main__content[^"]*"[^>]*>(.*?)</div>\s*<div[^>]*class="article__footer"',
        r'<div[^>]*class="article__main__content[^"]*"[^>]*>(.*?)</div>\s*</article>',
        r'<div[^>]*class="article__main__content[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>\s*</article>',
        r'<div[^>]*class="article-body[^"]*"[^>]*>(.*?)</div>\s*</article>',
        r'<article[^>]*class="normal-article[^"]*"[^>]*>.*?<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>.*?</article>',
    ]
    
    for pattern in content_patterns:
        match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
        if match:
            content = match.group(1)
            break
    
    # If still no content, try a more general approach
    if not content:
        # Find all content-like divs and pick the largest
        content_divs = re.findall(r'<div[^>]*class="[^"]*(?:content|article|post)[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL | re.IGNORECASE)
        if content_divs:
            content = max(content_divs, key=len)
    
    if not content:
        return None
    
    # Clean up the content HTML
    content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
    
    return {
        'title': title,
        'content': content,
        'images': []
    }


# ========== WeChat (微信公众号) Parser ==========
@register_parser("mp.weixin.qq.com")
def parse_wechat(html, url):
    """Parse WeChat public account articles."""
    
    # Extract title from meta or h1
    title = ""
    title_match = re.search(r'<h1[^>]*class="rich_media_title[^"]*"[^>]*>.*?<span[^>]*class="js_title_inner"[^>]*>(.*?)</span>.*?</h1>', html, re.DOTALL | re.IGNORECASE)
    if not title_match:
        title_match = re.search(r'<h1[^>]*class="rich_media_title[^"]*"[^>]*>(.*?)</h1>', html, re.DOTALL | re.IGNORECASE)
    if title_match:
        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
    
    if not title:
        title = extract_meta_content(html, 'og:title') or extract_meta_content(html, 'twitter:title') or ""
    
    # Extract author
    author = ""
    author_match = re.search(r'<span[^>]*id="profileNickname"[^>]*>(.*?)</span>', html, re.DOTALL | re.IGNORECASE)
    if author_match:
        author = re.sub(r'<[^>]+>', '', author_match.group(1)).strip()
    
    # Extract main content
    content = ""
    content_match = re.search(r'<div[^>]*id="js_content"[^>]*>(.*?)</div>\s*</div>\s*<script', html, re.DOTALL | re.IGNORECASE)
    if not content_match:
        content_match = re.search(r'<div[^>]*id="js_content"[^>]*>(.*?)</div>\s*</div>\s*<div[^>]*class="rich_media_tool', html, re.DOTALL | re.IGNORECASE)
    if content_match:
        content = content_match.group(1)
    
    # Extract images from content
    images = []
    seen_urls = set()
    if content:
        # Find all image URLs
        img_urls = re.findall(r'data-src="(https?://mmbiz\.qpic\.cn/[^"]+)"', content)
        img_urls += re.findall(r'src="(https?://mmbiz\.qpic\.cn/[^"]+)"', content)
        
        for img_url in img_urls:
            # Clean up URL - remove size parameters if any
            clean_url = re.sub(r'\bwx_fmt=[^&]+', 'wx_fmt=jpeg', img_url)
            # Skip very small images (likely icons)
            # Extract size from URL if present
            size_match = re.search(r'/([^/]+)\.(?:png|jpg|jpeg|gif)', clean_url)
            if size_match:
                size_str = size_match.group(1)
                # Skip if it's a tiny icon (usually has specific patterns)
                if any(x in size_str for x in ['icon', 'emoji', 'smiley', 'dot', 'blank']):
                    continue
            
            # Deduplicate
            if clean_url not in seen_urls:
                seen_urls.add(clean_url)
                images.append((clean_url, ''))
    
    # Clean up content HTML
    if content:
        # Remove WeChat UI elements
        content = re.sub(r'<mp-common-profile[^>]*>.*?</mp-common-profile>', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<span[^>]*class="share_notice"[^>]*>.*?</span>', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<a[^>]*class="weapp_text_link"[^>]*>.*?</a>', '', content, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove preview and interaction UI
        content = re.sub(r'预览时标签不可点', '', content)
        content = re.sub(r'微信扫一扫[^<]*', '', content)
        content = re.sub(r'关注该公众号', '', content)
        content = re.sub(r'继续滑动看下一个', '', content)
        content = re.sub(r'向上滑动看下一个', '', content)
        content = re.sub(r'轻触阅读原文', '', content)
        content = re.sub(r'轻点两下取消赞', '', content)
        content = re.sub(r'轻点两下取消在看', '', content)
        content = re.sub(r'使用小程序', '', content)
        content = re.sub(r'使用完整服务', '', content)
        content = re.sub(r'轻点两下取消[^<]*', '', content)
        
        # Replace data-src with src for images
        content = re.sub(r'data-src="', 'src="', content)
    
    # Build clean content
    content_parts = []
    if author:
        content_parts.append(f"**作者**: {author}")
    if content:
        content_parts.append(content)
    
    full_content = '\n\n---\n\n'.join(content_parts) if content_parts else "(无内容)"
    
    return {
        'title': title,
        'content': full_content,
        'images': images
    }


# ========== Bilibili Parser ==========
@register_parser("bilibili.com")
def parse_bilibili(html, url):
    """Parse Bilibili content - supports opus (图文) and video pages."""
    
    # Extract __INITIAL_STATE__ from HTML
    match = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', html, re.DOTALL)
    if not match:
        return None
    
    try:
        data = json.loads(match.group(1))
    except:
        return None
    
    # Check if it's an opus (图文动态)
    opus = data.get('opus', {})
    if opus and opus.get('detail'):
        return _parse_bilibili_opus(opus, url)
    
    # Check if it's a video page
    video_data = data.get('video', {})
    if video_data and video_data.get('videoInfo'):
        return _parse_bilibili_video(video_data, url)
    
    return None


def _parse_bilibili_opus(opus_data, url):
    """Parse Bilibili opus (图文动态) format."""
    detail = opus_data.get('detail')
    if not detail:
        return None
    
    modules = detail.get('modules', [])
    
    # Extract title
    title = ""
    for module in modules:
        if 'module_title' in module:
            title = module['module_title'].get('text', '')
            break
    
    # Fallback: use basic title
    if not title:
        basic = detail.get('basic', {})
        title = basic.get('title', 'Bilibili动态')
    
    # Extract content
    content_parts = []
    images = []
    
    for module in modules:
        # Extract images from module_top (album/cover images)
        if 'module_top' in module:
            top = module['module_top']
            display = top.get('display', {})
            album = display.get('album', {})
            pics = album.get('pics', [])
            for pic in pics:
                pic_url = pic.get('url', '')
                if pic_url:
                    if pic_url.startswith('//'):
                        pic_url = 'https:' + pic_url
                    elif pic_url.startswith('http://'):
                        pic_url = 'https://' + pic_url[7:]
                    images.append((pic_url, ''))
                    content_parts.append(f'\n![image]({pic_url})\n')
        
        # Extract content text and inline images
        if 'module_content' in module:
            content = module['module_content']
            paragraphs = content.get('paragraphs', [])
            
            for para in paragraphs:
                text_nodes = para.get('text', {}).get('nodes', [])
                para_text = []
                
                for node in text_nodes:
                    node_type = node.get('type', '')
                    
                    if node_type == 'TEXT_NODE_TYPE_WORD':
                        word = node.get('word', {})
                        text = word.get('words', '')
                        if text:
                            para_text.append(text)
                    
                    elif node_type == 'TEXT_NODE_TYPE_RICH':
                        rich = node.get('rich', {})
                        text = rich.get('text', '')
                        if text:
                            para_text.append(text)
                    
                    elif node_type == 'TEXT_NODE_TYPE_PIC':
                        pic = node.get('pic', {})
                        pic_url = pic.get('url', '')
                        if pic_url:
                            if pic_url.startswith('//'):
                                pic_url = 'https:' + pic_url
                            elif pic_url.startswith('http://'):
                                pic_url = 'https://' + pic_url[7:]
                            images.append((pic_url, ''))
                            para_text.append(f'\n![image]({pic_url})\n')
                        # Also check for pics array
                        pics = pic.get('pics', [])
                        for p in pics:
                            url = p.get('url', '')
                            if url:
                                if url.startswith('//'):
                                    url = 'https:' + url
                                elif url.startswith('http://'):
                                    url = 'https://' + url[7:]
                                images.append((url, ''))
                                para_text.append(f'\n![image]({url})\n')
                
                if para_text:
                    content_parts.append(''.join(para_text))
    
    # Extract author info
    author_name = ""
    for module in modules:
        if 'module_author' in module:
            author = module['module_author']
            author_name = author.get('name', '')
            break
    
    content = '\n\n'.join(content_parts) if content_parts else "(无文字内容)"
    
    # Add author info
    if author_name:
        content = f"**作者**: {author_name}\n\n---\n\n{content}"
    
    return {
        'title': title,
        'content': content,
        'images': images
    }


def _parse_bilibili_video(video_data, url):
    """Parse Bilibili video page."""
    # Extract video info from videoData
    video_info = video_data.get('videoInfo', {})
    
    title = video_info.get('title', '')
    description = video_info.get('desc', '')
    bvid = video_info.get('bvid', '')
    
    # Extract owner info
    owner = video_info.get('owner', {})
    author_name = owner.get('name', '')
    
    # Build content
    content_parts = []
    
    if description:
        content_parts.append(description)
    
    # Add video link
    content_parts.append(f"\n**视频链接**: {url}")
    content_parts.append(f"**BV号**: {bvid}")
    
    if author_name:
        content_parts.append(f"**UP主**: {author_name}")
    
    # Extract tags
    tags = video_info.get('tag', [])
    if tags:
        tag_names = [t.get('tag_name', '') for t in tags if t.get('tag_name')]
        if tag_names:
            content_parts.append(f"**标签**: {', '.join(tag_names)}")
    
    content = '\n\n'.join(content_parts)
    
    # Extract cover image
    images = []
    cover_url = video_info.get('pic', '')
    if cover_url:
        if cover_url.startswith('//'):
            cover_url = 'https:' + cover_url
        images.append((cover_url, '封面'))
    
    return {
        'title': title or 'Bilibili视频',
        'content': content,
        'images': images
    }
class ArticleExtractor(HTMLParser):
    """Extract article title, content, and images from generic HTML."""
    
    def __init__(self, base_url=""):
        super().__init__()
        self.base_url = base_url
        self.in_title = False
        self.in_body = False
        self.in_skip = 0
        self.body_depth = 0
        
        self.title = ""
        self.body_parts = []
        self.all_text = []
        self.images = []
        
        # Tags to skip
        self.skip_tags = {
            'script', 'style', 'nav', 'header', 'footer', 
            'aside', 'noscript', 'iframe', 'svg', 'canvas',
            'form', 'input', 'button', 'select', 'textarea', 'label'
        }
        
        # Content indicators
        self.content_classes = {
            'content', 'article', 'main', 'post', 'entry', 
            'post-content', 'article-content', 'entry-content',
            'story', 'story-body', 'article-body', 'rich-text',
            'article__content', 'content-body', 'livenews',
            'live-news', 'news-content', 'detail-content',
            'text-content', 'main-content', 'page-content',
            'article-detail', 'article_text', 'article-text',
            'article__body', 'article-body__content',
            'article__main__content', 'wangEditor-txt',
            'articleWidth-content', 'normal-article',
            'editor-content', 'ql-editor', 'trix-content',
            'post__content', 'entry__content'
        }
        self.content_ids = {
            'content', 'article', 'main', 'post', 'entry',
            'livenews', 'live-news', 'news-content', 'detail',
            'article-detail', 'articleContent', 'article-body',
            'article-content', 'post-content'
        }
        
        # Tags that indicate sidebar/related content (to exclude)
        self.sidebar_classes = {
            'sidebar', 'related', 'recommended', 'popular',
            'trending', 'more', 'read-more', 'see-also',
            'widget', 'aside-content', 'extra', 'supplement'
        }
        self.sidebar_ids = {
            'sidebar', 'related', 'recommended', 'popular',
            'trending', 'more', 'read-more'
        }
    
    def _get_attr(self, attrs, name):
        for k, v in attrs:
            if k == name:
                return v
        return ""
    
    def _resolve_url(self, url):
        if not url or url.startswith('data:'):
            return None
        if url.startswith('http://') or url.startswith('https://'):
            return url
        if url.startswith('//'):
            return 'https:' + url
        if self.base_url:
            return urllib.parse.urljoin(self.base_url, url)
        return None
    
    def _is_content_container(self, tag, attrs):
        """Check if this element is likely a content container."""
        cls = self._get_attr(attrs, 'class')
        id_ = self._get_attr(attrs, 'id')
        
        # First check if it's a sidebar/related content (exclude these)
        if cls:
            classes = set(cls.split())
            if classes & self.sidebar_classes:
                return False
        if id_ and id_ in self.sidebar_ids:
            return False
        
        # Then check if it's a content container
        if cls:
            classes = set(cls.split())
            if classes & self.content_classes:
                return True
        if id_ and id_ in self.content_ids:
            return True
        if tag in ('article', 'main'):
            return True
        return False
    
    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.in_skip += 1
            return
        
        if self.in_skip > 0:
            return
        
        if tag == 'title':
            self.in_title = True
        
        # Check if this is a content container
        is_content = self._is_content_container(tag, attrs)
        if is_content:
            self.in_body = True
            self.body_depth += 1
        elif self.in_body:
            # If we're already in body, increment depth for structural tags
            if tag in ('div', 'section', 'article', 'main', 'p', 'blockquote', 'pre', 'ul', 'ol', 'li'):
                self.body_depth += 1
        
        # Extract images
        if tag == 'img':
            src = self._resolve_url(self._get_attr(attrs, 'src'))
            if not src:
                src = self._resolve_url(self._get_attr(attrs, 'data-src'))
            if not src:
                src = self._resolve_url(self._get_attr(attrs, 'data-original'))
            if src:
                alt = self._get_attr(attrs, 'alt')
                self.images.append((src, alt))
    
    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            self.in_skip -= 1
            return
        
        if tag == 'title':
            self.in_title = False
        
        if self.in_body:
            # Decrement depth for structural tags
            if tag in ('div', 'section', 'article', 'main', 'p', 'blockquote', 'pre', 'ul', 'ol', 'li'):
                self.body_depth -= 1
                if self.body_depth <= 0:
                    self.in_body = False
                    self.body_depth = 0
    
    def handle_data(self, data):
        if self.in_skip > 0:
            return
        
        text = data.strip()
        if not text:
            return
        
        if self.in_title:
            self.title += text
        
        self.all_text.append(text)
        
        if self.in_body:
            self.body_parts.append(text)
    
    def get_result(self):
        title = self.title or "Untitled"
        
        # Try to find better title
        if title in ("", "Untitled"):
            for text in self.all_text[:30]:
                if len(text) > 10:
                    if len(text) < 100 and not text.startswith('http'):
                        title = text
                        break
        
        # Use body parts if available, otherwise all text
        if self.body_parts and len(' '.join(self.body_parts)) > 200:
            content = '\n'.join(self.body_parts)
        else:
            # Fallback: use all text, filtering out short fragments
            meaningful = [t for t in self.all_text if len(t) > 3]
            content = '\n'.join(meaningful)
        
        return {
            'title': title,
            'content': content,
            'images': self.images
        }


# ========== Playwright Fallback ==========
def fetch_with_playwright(url):
    """Use Playwright to fetch JS-rendered page content."""
    try:
        # Check if playwright is available
        import playwright
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url, wait_until="networkidle")
            
            # Wait for content to load
            page.wait_for_timeout(2000)
            
            # Get page content
            html = page.content()
            
            browser.close()
            return html
    except ImportError:
        print("Playwright not available, trying selenium...", file=sys.stderr)
        return fetch_with_selenium(url)
    except Exception as e:
        print(f"Playwright failed: {e}", file=sys.stderr)
        return None


def fetch_with_selenium(url):
    """Use Selenium to fetch JS-rendered page content."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        
        # Wait for content to load
        import time
        time.sleep(3)
        
        html = driver.page_source
        driver.quit()
        return html
    except ImportError:
        print("Selenium not available", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Selenium failed: {e}", file=sys.stderr)
        return None




def transcribe_audio_file(audio_path, whisper_url):
    """Transcribe audio using local Whisper Web UI API.
    
    Supports two URL formats:
    1. Direct whisper.cpp server: http://host:port (POST to /v1/audio/transcriptions)
    2. Preprocessing service: http://host:port (GET for info, POST may be blocked)
    
    The function will auto-detect and use the correct endpoint.
    """
    try:
        import subprocess
        import json
        
        # Convert to WAV if needed (Whisper works best with WAV)
        wav_path = audio_path.rsplit('.', 1)[0] + '.wav'
        if not os.path.exists(wav_path):
            print(f"  🔄 Converting to WAV...", file=sys.stderr)
            result = subprocess.run([
                'ffmpeg', '-i', audio_path,
                '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le',
                wav_path, '-y'
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                print(f"  ❌ FFmpeg conversion failed: {result.stderr[:200]}", file=sys.stderr)
                return None
        
        # Detect correct endpoint
        # Try direct whisper.cpp endpoint first
        api_url = f'{whisper_url}/v1/audio/transcriptions'
        
        print(f"  🎙️ Calling Whisper API at {api_url}...", file=sys.stderr)
        
        # Build multipart request manually using standard library
        boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
        
        # Read audio file
        with open(wav_path, 'rb') as f:
            audio_data = f.read()
        
        # Build multipart body
        # Format: --boundary\r\nContent-Disposition...\r\n\r\n[data]\r\n--boundary--\r\n
        parts = []
        
        # Add file field
        parts.append(f'--{boundary}'.encode())
        parts.append(b'Content-Disposition: form-data; name="file"; filename="audio.wav"')
        parts.append(b'Content-Type: audio/wav')
        parts.append(b'')  # Empty line before data
        parts.append(audio_data)
        
        # Add model field
        parts.append(f'--{boundary}'.encode())
        parts.append(b'Content-Disposition: form-data; name="model"')
        parts.append(b'')
        parts.append(b'whisper-1')
        
        # Add language field (Chinese)
        parts.append(f'--{boundary}'.encode())
        parts.append(b'Content-Disposition: form-data; name="language"')
        parts.append(b'')
        parts.append(b'zh')
        
        # Add response_format field
        parts.append(f'--{boundary}'.encode())
        parts.append(b'Content-Disposition: form-data; name="response_format"')
        parts.append(b'')
        parts.append(b'json')
        
        # Close boundary
        parts.append(f'--{boundary}--'.encode())
        parts.append(b'')  # Final CRLF
        
        body_bytes = b'\r\n'.join(parts)
        
        # Send request
        req = urllib.request.Request(
            api_url,
            data=body_bytes,
            headers={
                'Content-Type': f'multipart/form-data; boundary={boundary}',
                'Accept': 'application/json',
            },
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=600) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            # Extract transcription text
            if 'text' in result:
                return result['text']
            elif 'segments' in result:
                return ' '.join(seg.get('text', '') for seg in result['segments'])
            else:
                return str(result)
    
    except urllib.error.HTTPError as e:
        print(f"  ❌ HTTP Error {e.code}: {e.reason}", file=sys.stderr)
        try:
            error_body = e.read().decode('utf-8', errors='replace')
            print(f"     Response: {error_body[:500]}", file=sys.stderr)
        except:
            pass
        return None
    except Exception as e:
        print(f"  ❌ Transcription failed: {e}", file=sys.stderr)
        return None

# ========== Core Functions ==========
def fetch_url(url, timeout=30):
    """Fetch URL content with proper headers. Returns (html, final_url)."""
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'identity',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-cache',
    }
    
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            final_url = response.geturl()
            content_type = response.headers.get('Content-Type', '')
            charset = 'utf-8'
            
            if 'charset=' in content_type:
                match = re.search(r'charset=([^;]+)', content_type)
                if match:
                    charset = match.group(1).strip().strip('"').strip("'")
            
            raw = response.read()
            html = None
            
            for enc in [charset, 'utf-8', 'gbk', 'gb2312', 'latin-1']:
                try:
                    html = raw.decode(enc, errors='ignore')
                    break
                except:
                    continue
            
            if html is None:
                html = raw.decode('utf-8', errors='replace')
            
            return html, final_url
    
    except urllib.error.HTTPError as e:
        raise Exception(f"HTTP {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        raise Exception(f"URL Error: {e.reason}")
    except Exception as e:
        raise Exception(f"Fetch failed: {str(e)}")


def extract_meta_content(html, property_name):
    """Extract meta tag content by property or name."""
    pattern = rf'<meta[^>]+(?:property|name)=["\']{re.escape(property_name)}["\'][^>]+content=["\']([^"\']+)["\']'
    match = re.search(pattern, html, re.IGNORECASE)
    if match:
        return match.group(1)
    
    pattern = rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(property_name)}["\']'
    match = re.search(pattern, html, re.IGNORECASE)
    if match:
        return match.group(1)
    
    return None


def extract_json_ld(html):
    """Extract JSON-LD structured data for article info."""
    pattern = r'<script type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
    matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
    
    for match in matches:
        try:
            data = json.loads(match.strip())
            if isinstance(data, dict):
                if data.get('@type') in ('NewsArticle', 'Article', 'WebPage'):
                    return data
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get('@type') in ('NewsArticle', 'Article', 'WebPage'):
                        return item
        except:
            continue
    
    return None


def download_image(url, output_path, timeout=20):
    """Download an image to local path."""
    try:
        headers = {'User-Agent': USER_AGENT}
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read()
            
            if len(data) < 100:
                return False
            
            magic = data[:8]
            is_image = (
                magic[:2] == b'\xff\xd8' or
                magic[:4] == b'\x89PNG' or
                magic[:4] == b'GIF8' or
                magic[:2] == b'BM' or
                magic[:4] == b'RIFF'
            )
            
            if not is_image:
                return False
            
            output_path.write_bytes(data)
            return True
    
    except Exception as e:
        print(f"  ⚠️ Image failed: {url[:60]}... - {e}", file=sys.stderr)
        return False


def html_to_markdown(html_content):
    """Convert HTML content to Markdown."""
    # Remove script/style
    text = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<noscript[^>]*>.*?</noscript>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Headers
    text = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1\n\n', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1\n\n', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1\n\n', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<h4[^>]*>(.*?)</h4>', r'#### \1\n\n', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<h5[^>]*>(.*?)</h5>', r'##### \1\n\n', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<h6[^>]*>(.*?)</h6>', r'###### \1\n\n', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Paragraphs
    text = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Line breaks
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    
    # Lists
    text = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1\n', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'</?ul[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</?ol[^>]*>', '\n', text, flags=re.IGNORECASE)
    
    # Bold/Italic
    text = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<i[^>]*>(.*?)</i>', r'*\1*', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Blockquotes
    def quote_repl(m):
        inner = m.group(1).strip()
        lines = inner.split('\n')
        return '\n'.join('> ' + l for l in lines) + '\n\n'
    text = re.sub(r'<blockquote[^>]*>(.*?)</blockquote>', quote_repl, text, flags=re.DOTALL | re.IGNORECASE)
    
    # Code
    text = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<pre[^>]*>(.*?)</pre>', r'```\n\1\n```\n\n', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Links
    text = re.sub(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', r'[\2](\1)', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove remaining tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Clean up
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = text.strip()
    
    return text


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


def get_domain(url):
    """Extract domain from URL."""
    parsed = urllib.parse.urlparse(url)
    return parsed.netloc.lower()


def clip_article(url, test_mode=False, transcribe_audio=False, whisper_url=None):
    """Main clipping function."""
    
    print(f"📥 Fetching: {url}", file=sys.stderr)
    
    # Fetch page
    html, final_url = fetch_url(url)
    
    # Try site-specific parser first
    domain = get_domain(final_url)
    result = None
    parser_used = None
    
    # Check for exact domain match
    if domain in SITE_PARSERS:
        print(f"🔧 Using site-specific parser for {domain}", file=sys.stderr)
        parser_used = domain
        result = SITE_PARSERS[domain](html, final_url)
    else:
        # Check for partial domain match
        for parser_domain, parser_func in SITE_PARSERS.items():
            if parser_domain in domain or domain in parser_domain:
                print(f"🔧 Using site-specific parser for {parser_domain}", file=sys.stderr)
                parser_used = parser_domain
                result = parser_func(html, final_url)
                break
    
    # Check parser health if a site-specific parser was used
    if parser_used:
        check_parser_health(parser_used, result)
        
        # If parser failed, try to diagnose and fallback to generic
        if result is None or not result.get('title') or not result.get('content') or len(result.get('content', '')) < 100:
            print(f"⚠️ Site-specific parser failed, falling back to generic parser", file=sys.stderr)
            diagnosis = diagnose_failure(final_url, html, result)
            if diagnosis['suggestions']:
                print(f"💡 Suggestions:", file=sys.stderr)
                for suggestion in diagnosis['suggestions']:
                    print(f"   - {suggestion}", file=sys.stderr)
            result = None  # Force fallback
    
    # If site-specific parser fails or not found, try generic parsing
    if not result:
        print(f"🔍 Using generic HTML parser", file=sys.stderr)
        
        # Try meta tags first
        meta_title = extract_meta_content(html, 'og:title')
        if not meta_title:
            meta_title = extract_meta_content(html, 'twitter:title')
        
        # Try JSON-LD
        json_ld = extract_json_ld(html)
        
        # Parse HTML
        extractor = ArticleExtractor(base_url=url)
        try:
            extractor.feed(html)
        except Exception as e:
            print(f"⚠️ Parse warning: {e}", file=sys.stderr)
        
        parsed = extractor.get_result()
        
        title = meta_title or parsed['title']
        if not title or title in ("Untitled", ""):
            if json_ld and json_ld.get('headline'):
                title = json_ld['headline']
            else:
                title = parsed['title'] or "Untitled"
        
        content = parsed['content']
        description = ""
        if json_ld:
            description = json_ld.get('description', '')
        images = parsed['images']
        
        result = {
            'title': title,
            'content': content,
            'description': description,
            'images': images
        }
        
        # Check if generic parser also failed
        if not result.get('title') or not result.get('content') or len(result.get('content', '')) < 100:
            print(f"❌ Generic parser also failed - content may require JavaScript rendering", file=sys.stderr)
            print(f"🔧 Consider using Playwright/Selenium for this URL", file=sys.stderr)
    
    title = result.get('title', 'Untitled')
    content = result.get('content', '')
    description = result.get('description', '')
    images = result.get('images', [])
    audio_url = result.get('audio_url')
    audio_file = result.get('audio_file')
    
    # Add source prefix to title
    SOURCE_PREFIXES = {
        'wallstreetcn.com': '见闻',
        'mp.weixin.qq.com': '微信',
        'sspai.com': '少数派',
        'bilibili.com': 'B站',
        'xiaoyuzhoufm.com': '小宇宙',
    }
    
    domain = get_domain(final_url)
    source_prefix = None
    for site_domain, prefix in SOURCE_PREFIXES.items():
        if site_domain in domain or domain in site_domain:
            source_prefix = prefix
            break
    
    if source_prefix and not title.startswith(f'[{source_prefix}]'):
        title = f'[{source_prefix}] {title}'
    
    print(f"📄 Title: {title}", file=sys.stderr)
    print(f"📄 Content length: {len(content)}", file=sys.stderr)
    print(f"🖼️ Images: {len(images)}", file=sys.stderr)
    if audio_url:
        print(f"🎵 Audio URL: {audio_url[:60]}...", file=sys.stderr)
    
    # Download audio if available
    if audio_url:
        audio_filename = sanitize_filename(title) + ".m4a"
        audio_output_path = OUTPUT_BASE / "multimedia" / audio_filename
        if download_audio(audio_url, audio_output_path):
            audio_file = str(audio_output_path)
            result['audio_file'] = audio_file
            
            # Transcribe audio if requested and whisper URL provided
            if transcribe_audio and whisper_url:
                print(f"🎙️ Transcribing audio via Whisper API...", file=sys.stderr)
                transcription = transcribe_audio_file(audio_file, whisper_url)
                if transcription:
                    result['transcription'] = transcription
                    print(f"✅ Transcription complete: {len(transcription)} chars", file=sys.stderr)
    
    # Save evolution report if content is suspiciously short and no audio
    if len(content) < 200 and not audio_url:
        print(f"⚠️ Content very short - saving evolution report for analysis", file=sys.stderr)
        save_evolution_report(url, html, result)
    
    # Prepare output paths
    date_str = datetime.now().strftime("%Y-%m-%d")
    save_dir = OUTPUT_BASE / date_str
    save_dir.mkdir(parents=True, exist_ok=True)
    
    base_name = sanitize_filename(title)
    md_path = save_dir / f"{base_name}.md"
    img_dir = save_dir / f"{base_name}_images"
    
    # Download images
    downloaded_images = []
    if images:
        img_dir.mkdir(exist_ok=True)
        
        for i, img_info in enumerate(images):
            if isinstance(img_info, dict):
                img_url = img_info.get('url', img_info.get('src', ''))
                alt = img_info.get('alt', '')
            else:
                img_url, alt = img_info if len(img_info) == 2 else (img_info[0], '')
            
            if not img_url:
                continue
                
            ext = Path(urllib.parse.urlparse(img_url).path).suffix or '.jpg'
            if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'):
                ext = '.jpg'
            
            local_name = f"img_{i:03d}{ext}"
            local_path = img_dir / local_name
            
            print(f"  📥 Image {i+1}/{len(images)}: {img_url[:60]}...", file=sys.stderr)
            
            if download_image(img_url, local_path):
                downloaded_images.append((img_url, alt, local_name))
                print(f"    ✅ {local_name}", file=sys.stderr)
            else:
                print(f"    ❌ Failed", file=sys.stderr)
    
    # Convert content to Markdown
    if content:
        md_content = html_to_markdown(content)
    else:
        md_content = "(No content extracted)"
    
    # Build image references
    image_refs = ""
    if downloaded_images:
        image_refs = "\n\n## Images\n\n"
        for img_url, alt, local_name in downloaded_images:
            rel_path = f"{img_dir.name}/{local_name}"
            alt_text = alt or "image"
            image_refs += f"![{alt_text}]({rel_path})\n\n"
    
    # Build final Markdown
    markdown = f"""---
title: {title}
source: {url}
clipped: {datetime.now().isoformat()}
images_count: {len(downloaded_images)}
---

# {title}

**Source**: {url}
**Clipped**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
{'' if not description else f'**Description**: {description}'}

---

{md_content}
{image_refs}

---

*Clipped by web-clipper*
"""
    
    # Save file
    md_path.write_text(markdown, encoding='utf-8')
    
    print(f"✅ Saved: {md_path}", file=sys.stderr)
    
    if test_mode:
        return markdown
    
    return str(md_path)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 clipper.py <URL> [--test] [--transcribe] [--whisper-url <URL>]", file=sys.stderr)
        sys.exit(1)
    
    url = sys.argv[1]
    test_mode = '--test' in sys.argv
    transcribe = '--transcribe' in sys.argv
    
    # Parse whisper URL
    whisper_url = None
    if '--whisper-url' in sys.argv:
        idx = sys.argv.index('--whisper-url')
        if idx + 1 < len(sys.argv):
            whisper_url = sys.argv[idx + 1]
    
    try:
        result = clip_article(
            url, 
            test_mode=test_mode,
            transcribe_audio=transcribe,
            whisper_url=whisper_url
        )
        
        if test_mode:
            print(result)
        else:
            print(f"SUCCESS:{result}")
    
    except Exception as e:
        print(f"ERROR:{str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
