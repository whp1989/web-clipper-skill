---
name: web-clipper
description: Clip web articles to local Markdown files with images. Use when the user provides a URL and wants to save the article content as a Markdown file in the syncthing folder. Also use when the user says "剪藏", "保存链接", "clip this", "save this article", or any request to archive a web page to local storage. Automatically extracts text and images, converts to Markdown, and saves to ~/.openclaw/workspace/syncthing/raw/YYYY-MM-DD/. For user content archiving (not URLs), use the archive sub-skill when user says "归档".
---

# Web Clipper Skill

## Sub-Skills

| Trigger | Skill | Script | Purpose |
|---------|-------|--------|---------|
| URL provided | Main clipper | `clipper.py` | Fetch and save web articles |
| "归档" keyword | Archive | `archive.py` | Save user-provided content |
| "稍后读" keyword | Read Later | `archive.py --read-later` | Append to read later list (MUST use --read-later flag) |
| magnet:/ed2k: links | Link Archive | `archive_links.py` | Save magnet and ed2k links |
| "网页链接提取" keyword | Web Magnet Extractor | `extract_web_magnet.py` | Extract magnet links from web pages |
| "雪球" or "xueqiu" keyword | Xueqiu Stock | `xueqiu_camofox.py` | Fetch stock discussions from xueqiu.com |

## Web Magnet Extractor Sub-Skill

When user says "网页链接提取" or provides a URL for magnet extraction:

```bash
python3 ~/.openclaw/skills/web-clipper/scripts/extract_web_magnet.py "<URL>"
```

**Behavior:**
- Fetches the web page (supports both requests and playwright)
- Extracts all magnet links from the page
- If multiple magnets found, selects the one with **largest file size**
- Archives the selected magnet to `syncthing/raw/归档/磁链.md`
- Includes source URL and timestamp
- Triggers NAS sync and Gotify notification

**Supported Sites:**
- **javbus.com** (and mirrors) - detects `gid`/`uc` params, uses API if available
- Generic sites with magnet links in `<a>` tags

**Auto-Trigger:**
- Message contains "网页链接提取" keyword
- User provides a URL explicitly for magnet extraction

See `ARCHIVE.md` for full documentation.

## Xueqiu Stock Sub-Skill

When user says "雪球" or "xueqiu" or requests stock information:

```bash
python3 ~/.openclaw/skills/web-clipper/scripts/xueqiu_camofox.py \
  --symbol "STOCK_CODE" \
  --name "STOCK_NAME"
```

**Note:** Requires camofox-browser service running. See `XUEQIU.md` for details.

## Archive Sub-Skill

When user says "归档" or provides content to save (not a URL):

```bash
python3 ~/.openclaw/skills/web-clipper/scripts/archive.py "<content>" "<title>" "<source>"
```

See `ARCHIVE.md` for full documentation.

## Purpose

Save web articles as Markdown files with images to a local syncthing-synced folder.

## Workflow

When triggered by a URL (or explicit clip request):

1. **Check link type** — if magnet or ed2k, use `archive_links.py`
2. **Fetch** the URL using `urllib.request`
3. **Extract** article title and content using site-specific parsers or generic HTML parser
4. **Download** images referenced in the article
5. **Convert** HTML content to Markdown
6. **Save** to `~/.openclaw/workspace/syncthing/raw/YYYY-MM-DD/`

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

## Task Completion Verification & Auto-Retry

All sub-skills include built-in task completion verification and automatic retry mechanisms:

### Completion Check Framework

```python
class TaskVerifier:
    """Verifies task completion and triggers auto-retry on failure"""
    
    def __init__(self, max_retries=3, retry_delay=5):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.attempt = 0
    
    def verify_and_retry(self, task_func, *args, **kwargs):
        """Execute task with automatic retry on failure"""
        while self.attempt < self.max_retries:
            try:
                result = task_func(*args, **kwargs)
                if self.verify_completion(result):
                    return result
                else:
                    self.attempt += 1
                    if self.attempt < self.max_retries:
                        time.sleep(self.retry_delay)
                        continue
            except Exception as e:
                self.attempt += 1
                if self.attempt < self.max_retries:
                    self.log_error(e)
                    self.apply_fix(e)
                    time.sleep(self.retry_delay)
                    continue
                else:
                    raise
        
        raise MaxRetryExceeded(f"Task failed after {self.max_retries} attempts")
    
    def verify_completion(self, result):
        """Override in subclass to verify task-specific completion"""
        return result is not None
    
    def log_error(self, error):
        """Log error for analysis"""
        log_path = f"~/.openclaw/workspace/logs/clipper_errors_{datetime.now().strftime('%Y%m%d')}.log"
        with open(os.path.expanduser(log_path), 'a') as f:
            f.write(f"[{datetime.now()}] Error: {str(error)}\n")
    
    def apply_fix(self, error):
        """Apply automatic fix based on error type"""
        error_str = str(error).lower()
        
        if "network" in error_str or "connection" in error_str:
            # Network error: wait and retry
            time.sleep(self.retry_delay * 2)
        elif "permission" in error_str or "access" in error_str:
            # Permission error: check file permissions
            self.fix_permissions()
        elif "parse" in error_str or "html" in error_str:
            # Parse error: switch to fallback parser
            self.enable_fallback_parser()
        elif "timeout" in error_str:
            # Timeout: increase timeout and retry
            self.increase_timeout()
        elif "api" in error_str or "500" in error_str:
            # API error: switch to alternative API or wait
            self.switch_api_endpoint()
    
    def fix_permissions(self):
        """Fix file permission issues"""
        os.system("chmod -R 755 ~/.openclaw/workspace/syncthing/raw/")
    
    def enable_fallback_parser(self):
        """Enable fallback HTML parser"""
        os.environ['CLIPPER_FALLBACK_PARSER'] = '1'
    
    def increase_timeout(self):
        """Increase request timeout"""
        os.environ['CLIPPER_TIMEOUT'] = '60'
    
    def switch_api_endpoint(self):
        """Switch to alternative API endpoint"""
        # Implemented in API-specific sub-skills
        pass

class MaxRetryExceeded(Exception):
    pass
```

### Sub-Skill Verification Rules

| Sub-Skill | Completion Criteria | Auto-Fix Strategy | Max Retries |
|:---|:---|:---|:---|
| Main clipper | File exists, size > 0, content valid | Switch parser, fix encoding | 3 |
| Archive | File exists, title correct, content saved | Fix path, regenerate title | 3 |
| Link archive | Links appended, no duplicates | Deduplicate, fix format | 3 |
| Xueqiu stock | Data fetched, table complete | Extend timeout, retry page | 3 |
| Audio transcribe | Audio extracted, text generated | Switch API, split segments | 3 |
| NAS sync | Files uploaded, no errors | Retry sync, check connection | 3 |
| Gotify notify | HTTP 200 response | Retry send, log failure | 2 |

### Error Recovery Flow

```
Task Start
    ↓
Attempt Execution
    ↓
Success? → Yes → Verify Output → Valid? → Yes → Task Complete
    ↓ No                        ↓ No
Retry Loop ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ←
    ↓
Max Retries Reached?
    ↓ Yes
Log Failure → Notify User → Escalate to Manual Fix
    ↓ No
Analyze Error → Apply Auto-Fix → Retry
```

### Implementation in Scripts

All scripts in `scripts/` directory implement the verification framework:

```python
# Example: clipper.py
from task_verifier import TaskVerifier

class ClipperVerifier(TaskVerifier):
    def verify_completion(self, result):
        """Verify clipper task completion"""
        if not result or 'file_path' not in result:
            return False
        
        file_path = result['file_path']
        
        # Check file exists
        if not os.path.exists(file_path):
            return False
        
        # Check file size > 0
        if os.path.getsize(file_path) == 0:
            return False
        
        # Check content validity
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if len(content) < 100:  # Minimum content threshold
                return False
            if 'title' not in content.lower():
                return False
        
        return True
    
    def apply_fix(self, error):
        """Clipper-specific fixes"""
        error_str = str(error).lower()
        
        if "empty" in error_str or "size" in error_str:
            # Content empty: switch to generic parser
            self.enable_fallback_parser()
        elif "encoding" in error_str:
            # Encoding issue: force UTF-8
            os.environ['CLIPPER_ENCODING'] = 'utf-8'
        elif "image" in error_str:
            # Image download failed: skip images
            os.environ['CLIPPER_SKIP_IMAGES'] = '1'
        else:
            super().apply_fix(error)

# Usage in main function
verifier = ClipperVerifier(max_retries=3)
result = verifier.verify_and_retry(clip_article, url)
```

### NAS Sync Verification

```python
class NasSyncVerifier(TaskVerifier):
    def verify_completion(self, result):
        """Verify NAS sync completion"""
        if not result:
            return False
        
        # Check sync log
        sync_log = result.get('sync_log', '')
        if 'error' in sync_log.lower() or 'failed' in sync_log.lower():
            return False
        
        # Verify file count matches
        local_count = result.get('local_file_count', 0)
        remote_count = result.get('remote_file_count', 0)
        if local_count != remote_count:
            return False
        
        return True
    
    def apply_fix(self, error):
        """NAS sync-specific fixes"""
        error_str = str(error).lower()
        
        if "connection" in error_str or "network" in error_str:
            # Connection issue: check mount point
            os.system("mount | grep syncthing || mount -a")
        elif "permission" in error_str:
            # Permission denied: fix SMB/NFS permissions
            os.system("chmod -R 777 /mnt/nas/ 2>/dev/null || true")
        elif "space" in error_str or "full" in error_str:
            # Disk full: alert user
            self.notify_disk_full()
        else:
            super().apply_fix(error)
```

### Notification Verification

```python
class NotifyVerifier(TaskVerifier):
    def verify_completion(self, result):
        """Verify notification sent successfully"""
        if not result:
            return False
        
        # Check HTTP status
        status_code = result.get('status_code', 0)
        if status_code != 200:
            return False
        
        return True
    
    def apply_fix(self, error):
        """Notification-specific fixes"""
        error_str = str(error).lower()
        
        if "timeout" in error_str:
            # Gotify timeout: skip notification, don't block
            os.environ['SKIP_NOTIFY'] = '1'
        elif "connection" in error_str:
            # Connection failed: queue for later
            self.queue_notification()
        else:
            # Other errors: log and continue
            self.log_error(error)
```

### Master Verification Script

A master verification script coordinates all sub-skills:

```bash
#!/bin/bash
# ~/.openclaw/skills/web-clipper/scripts/verify-task.sh

TASK_TYPE="$1"
TASK_RESULT="$2"
MAX_RETRIES=3
RETRY_COUNT=0

verify_task() {
    case "$TASK_TYPE" in
        "clip")
            python3 -c "
import sys, os
result = '$TASK_RESULT'
file_path = result.split('SUCCESS:')[-1].strip() if 'SUCCESS:' in result else ''
if file_path and os.path.exists(file_path) and os.path.getsize(file_path) > 100:
    sys.exit(0)
else:
    sys.exit(1)
"
            ;;
        "archive")
            python3 -c "
import sys, os
result = '$TASK_RESULT'
file_path = result.split('SUCCESS:')[-1].strip() if 'SUCCESS:' in result else ''
if file_path and os.path.exists(file_path):
    sys.exit(0)
else:
    sys.exit(1)
"
            ;;
        "nas_sync")
            # Check sync log for errors
            if echo "$TASK_RESULT" | grep -qi "error\|failed"; then
                return 1
            fi
            return 0
            ;;
        "notify")
            # Notification failures are non-blocking
            return 0
            ;;
        *)
            return 0
            ;;
    esac
}

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if verify_task; then
        echo "✅ Task verified: $TASK_TYPE"
        exit 0
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "⚠️ Verification failed, retry $RETRY_COUNT/$MAX_RETRIES..."
    sleep 5
done

echo "❌ Task verification failed after $MAX_RETRIES attempts: $TASK_TYPE"
exit 1
```

### Integration with Skill Execution

All skill executions now include verification:

```bash
# Example: Main clipper execution
python3 ~/.openclaw/skills/web-clipper/scripts/clipper.py "$URL"
RESULT=$?

# Verify task completion
if [ $RESULT -eq 0 ]; then
    bash ~/.openclaw/skills/web-clipper/scripts/verify-task.sh "clip" "$OUTPUT"
    if [ $? -ne 0 ]; then
        # Auto-retry with fixes
        echo "Auto-retrying with fallback parser..."
        CLIPPER_FALLBACK=1 python3 ~/.openclaw/skills/web-clipper/scripts/clipper.py "$URL"
    fi
fi
```

### Logging & Monitoring

All verification attempts are logged:

```
~/.openclaw/workspace/logs/
├── clipper_verification_YYYYMMDD.log
├── clipper_errors_YYYYMMDD.log
└── retry_stats_YYYYMMDD.json
```

**Log format:**
```
[2026-05-12 13:08:12] Task: clip, URL: https://example.com, Attempt: 1/3, Status: success
[2026-05-12 13:08:15] Task: nas_sync, Attempt: 1/3, Status: retry (connection timeout)
[2026-05-12 13:08:25] Task: nas_sync, Attempt: 2/3, Status: success
```

## Error Handling

If `clipper.py` fails:
1. Read the error output
2. Check if it's a network issue, parsing issue, or encoding issue
3. Edit `scripts/clipper.py` to fix the problem
4. Retry the clip
5. Report what was fixed

**Auto-Retry Rules:**
- Network errors: Retry up to 3 times with exponential backoff (5s, 10s, 20s)
- Parse errors: Switch to fallback parser, retry once
- Encoding errors: Force UTF-8, retry once
- API errors (500): Wait 30s, retry up to 3 times
- Timeout errors: Increase timeout to 60s, retry once
- Permission errors: Fix permissions automatically, retry once

**Failure Escalation:**
1. Auto-retry with fixes (max 3 attempts)
2. If still failing: Log detailed error report
3. If critical: Notify user with error summary
4. If non-critical (e.g., notification): Log and continue

## Task Completion Verification & Auto-Retry

All sub-skills include built-in task completion verification and automatic retry mechanisms:

### Completion Check Framework

```python
class TaskVerifier:
    """Verifies task completion and triggers auto-retry on failure"""
    
    def __init__(self, max_retries=3, retry_delay=5):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.attempt = 0
    
    def verify_and_retry(self, task_func, *args, **kwargs):
        """Execute task with automatic retry on failure"""
        while self.attempt < self.max_retries:
            try:
                result = task_func(*args, **kwargs)
                if self.verify_completion(result):
                    return result
                else:
                    self.attempt += 1
                    if self.attempt < self.max_retries:
                        time.sleep(self.retry_delay)
                        continue
            except Exception as e:
                self.attempt += 1
                if self.attempt < self.max_retries:
                    self.log_error(e)
                    self.apply_fix(e)
                    time.sleep(self.retry_delay)
                    continue
                else:
                    raise
        
        raise MaxRetryExceeded(f"Task failed after {self.max_retries} attempts")
    
    def verify_completion(self, result):
        """Override in subclass to verify task-specific completion"""
        return result is not None
    
    def log_error(self, error):
        """Log error for analysis"""
        log_path = f"~/.openclaw/workspace/logs/clipper_errors_{datetime.now().strftime('%Y%m%d')}.log"
        with open(os.path.expanduser(log_path), 'a') as f:
            f.write(f"[{datetime.now()}] Error: {str(error)}\n")
    
    def apply_fix(self, error):
        """Apply automatic fix based on error type"""
        error_str = str(error).lower()
        
        if "network" in error_str or "connection" in error_str:
            time.sleep(self.retry_delay * 2)
        elif "permission" in error_str or "access" in error_str:
            self.fix_permissions()
        elif "parse" in error_str or "html" in error_str:
            self.enable_fallback_parser()
        elif "timeout" in error_str:
            self.increase_timeout()
        elif "api" in error_str or "500" in error_str:
            self.switch_api_endpoint()
    
    def fix_permissions(self):
        """Fix file permission issues"""
        os.system("chmod -R 755 ~/.openclaw/workspace/syncthing/raw/")
    
    def enable_fallback_parser(self):
        """Enable fallback HTML parser"""
        os.environ['CLIPPER_FALLBACK_PARSER'] = '1'
    
    def increase_timeout(self):
        """Increase request timeout"""
        os.environ['CLIPPER_TIMEOUT'] = '60'
    
    def switch_api_endpoint(self):
        """Switch to alternative API endpoint"""
        pass

class MaxRetryExceeded(Exception):
    pass
```

### Sub-Skill Verification Rules

| Sub-Skill | Completion Criteria | Auto-Fix Strategy | Max Retries |
|:---|:---|:---|:---|
| Main clipper | File exists, size > 0, content valid | Switch parser, fix encoding | 3 |
| Archive | File exists, title correct, content saved | Fix path, regenerate title | 3 |
| Link archive | Links appended, no duplicates | Deduplicate, fix format | 3 |
| Xueqiu stock | Data fetched, table complete | Extend timeout, retry page | 3 |
| Audio transcribe | Audio extracted, text generated | Switch API, split segments | 3 |
| NAS sync | Files uploaded, no errors | Retry sync, check connection | 3 |
| Gotify notify | HTTP 200 response | Retry send, log failure | 2 |

### Error Recovery Flow

```
Task Start
    ↓
Attempt Execution
    ↓
Success? → Yes → Verify Output → Valid? → Yes → Task Complete
    ↓ No                        ↓ No
Retry Loop ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ←
    ↓
Max Retries Reached?
    ↓ Yes
Log Failure → Notify User → Escalate to Manual Fix
    ↓ No
Analyze Error → Apply Auto-Fix → Retry
```

### Implementation in Scripts

All scripts in `scripts/` directory implement the verification framework:

```python
# Example: clipper.py
from task_verifier import TaskVerifier

class ClipperVerifier(TaskVerifier):
    def verify_completion(self, result):
        """Verify clipper task completion"""
        if not result or 'file_path' not in result:
            return False
        
        file_path = result['file_path']
        
        # Check file exists
        if not os.path.exists(file_path):
            return False
        
        # Check file size > 0
        if os.path.getsize(file_path) == 0:
            return False
        
        # Check content validity
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if len(content) < 100:  # Minimum content threshold
                return False
            if 'title' not in content.lower():
                return False
        
        return True
    
    def apply_fix(self, error):
        """Clipper-specific fixes"""
        error_str = str(error).lower()
        
        if "empty" in error_str or "size" in error_str:
            # Content empty: switch to generic parser
            self.enable_fallback_parser()
        elif "encoding" in error_str:
            # Encoding issue: force UTF-8
            os.environ['CLIPPER_ENCODING'] = 'utf-8'
        elif "image" in error_str:
            # Image download failed: skip images
            os.environ['CLIPPER_SKIP_IMAGES'] = '1'
        else:
            super().apply_fix(error)

# Usage in main function
verifier = ClipperVerifier(max_retries=3)
result = verifier.verify_and_retry(clip_article, url)
```

### NAS Sync Verification

```python
class NasSyncVerifier(TaskVerifier):
    def verify_completion(self, result):
        """Verify NAS sync completion"""
        if not result:
            return False
        
        # Check sync log
        sync_log = result.get('sync_log', '')
        if 'error' in sync_log.lower() or 'failed' in sync_log.lower():
            return False
        
        # Verify file count matches
        local_count = result.get('local_file_count', 0)
        remote_count = result.get('remote_file_count', 0)
        if local_count != remote_count:
            return False
        
        return True
    
    def apply_fix(self, error):
        """NAS sync-specific fixes"""
        error_str = str(error).lower()
        
        if "connection" in error_str or "network" in error_str:
            # Connection issue: check mount point
            os.system("mount | grep syncthing || mount -a")
        elif "permission" in error_str:
            # Permission denied: fix SMB/NFS permissions
            os.system("chmod -R 777 /mnt/nas/ 2>/dev/null || true")
        elif "space" in error_str or "full" in error_str:
            # Disk full: alert user
            self.notify_disk_full()
        else:
            super().apply_fix(error)
```

### Notification Verification

```python
class NotifyVerifier(TaskVerifier):
    def verify_completion(self, result):
        """Verify notification sent successfully"""
        if not result:
            return False
        
        # Check HTTP status
        status_code = result.get('status_code', 0)
        if status_code != 200:
            return False
        
        return True
    
    def apply_fix(self, error):
        """Notification-specific fixes"""
        error_str = str(error).lower()
        
        if "timeout" in error_str:
            # Gotify timeout: skip notification, don't block
            os.environ['SKIP_NOTIFY'] = '1'
        elif "connection" in error_str:
            # Connection failed: queue for later
            self.queue_notification()
        else:
            # Other errors: log and continue
            self.log_error(error)
```

### Master Verification Script

A master verification script coordinates all sub-skills:

```bash
#!/bin/bash
# ~/.openclaw/skills/web-clipper/scripts/verify-task.sh

TASK_TYPE="$1"
TASK_RESULT="$2"
MAX_RETRIES=3
RETRY_COUNT=0

verify_task() {
    case "$TASK_TYPE" in
        "clip")
            python3 -c "
import sys, os
result = '$TASK_RESULT'
file_path = result.split('SUCCESS:')[-1].strip() if 'SUCCESS:' in result else ''
if file_path and os.path.exists(file_path) and os.path.getsize(file_path) > 100:
    sys.exit(0)
else:
    sys.exit(1)
"
            ;;
        "archive")
            python3 -c "
import sys, os
result = '$TASK_RESULT'
file_path = result.split('SUCCESS:')[-1].strip() if 'SUCCESS:' in result else ''
if file_path and os.path.exists(file_path):
    sys.exit(0)
else:
    sys.exit(1)
"
            ;;
        "nas_sync")
            # Check sync log for errors
            if echo "$TASK_RESULT" | grep -qi "error\|failed"; then
                return 1
            fi
            return 0
            ;;
        "notify")
            # Notification failures are non-blocking
            return 0
            ;;
        *)
            return 0
            ;;
    esac
}

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if verify_task; then
        echo "✅ Task verified: $TASK_TYPE"
        exit 0
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "⚠️ Verification failed, retry $RETRY_COUNT/$MAX_RETRIES..."
    sleep 5
done

echo "❌ Task verification failed after $MAX_RETRIES attempts: $TASK_TYPE"
exit 1
```

### Integration with Skill Execution

All skill executions now include verification:

```bash
# Example: Main clipper execution
python3 ~/.openclaw/skills/web-clipper/scripts/clipper.py "$URL"
RESULT=$?

# Verify task completion
if [ $RESULT -eq 0 ]; then
    bash ~/.openclaw/skills/web-clipper/scripts/verify-task.sh "clip" "$OUTPUT"
    if [ $? -ne 0 ]; then
        # Auto-retry with fixes
        echo "Auto-retrying with fallback parser..."
        CLIPPER_FALLBACK=1 python3 ~/.openclaw/skills/web-clipper/scripts/clipper.py "$URL"
    fi
fi
```

### Logging & Monitoring

All verification attempts are logged:

```
~/.openclaw/workspace/logs/
├── clipper_verification_YYYYMMDD.log
├── clipper_errors_YYYYMMDD.log
└── retry_stats_YYYYMMDD.json
```

**Log format:**
```
[2026-05-12 13:08:12] Task: clip, URL: https://example.com, Attempt: 1/3, Status: success
[2026-05-12 13:08:15] Task: nas_sync, Attempt: 1/3, Status: retry (connection timeout)
[2026-05-12 13:08:25] Task: nas_sync, Attempt: 2/3, Status: success
```

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

## Audio Transcription (OpenRouter + SiliconFlow Fallback)

For podcast/audio content, the skill can transcribe audio using OpenRouter API with automatic SiliconFlow fallback:

```bash
# Transcribe with OpenRouter (requires API key)
python3 ~/.openclaw/skills/web-clipper/scripts/clipper.py \
  "https://www.xiaoyuzhoufm.com/episode/xxx" \
  --transcribe \
  --whisper-url "openrouter" \
  --openrouter-key "sk-or-v1-..."
```

**Primary API: OpenRouter**
- Model: `mistralai/voxtral-small-24b-2507` (tested, supports Chinese)
- Cost: ~$0.03 per 5-minute segment
- Audio is automatically split into segments to avoid API limits

**Fallback API: SiliconFlow (自动备用)**
- Model: `FunAudioLLM/SenseVoiceSmall` (specialized for Chinese speech recognition)
- Activated automatically when OpenRouter returns 500 errors
- Uses OpenAI-compatible `/v1/audio/transcriptions` endpoint with multipart/form-data
- Supports emotion detection and audio event tagging (laughter, applause, etc.)

**Supported models:**
- `mistralai/voxtral-small-24b-2507` (OpenRouter, tested)
- `FunAudioLLM/SenseVoiceSmall` (SiliconFlow, Chinese optimized)
- Other audio-capable models on OpenRouter

## API 密钥配置（本地存储，不上传GitHub）

API keys and configuration stored in local config file:

**配置文件路径：**
- `~/.openclaw/workspace/.openclaw/api-config.json`
- `~/.openclaw/api-config.json`（备选）

**配置格式：**
```json
{
  "openrouter_api_key": "sk-or-v1-...",
  "openrouter_model": "mistralai/voxtral-small-24b-2507",
  "siliconflow_api_key": "sk-...",
  "siliconflow_model": "FunAudioLLM/SenseVoiceSmall",
  "siliconflow_base_url": "https://api.siliconflow.cn/v1",
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
| `siliconflow_api_key` | SiliconFlow API密钥 (备用) | 可选 |
| `siliconflow_model` | SiliconFlow语音模型 | `FunAudioLLM/SenseVoiceSmall` |
| `siliconflow_base_url` | SiliconFlow API地址 | `https://api.siliconflow.cn/v1` |
| `audio_segment_minutes` | 音频分段时长（分钟） | `10` |
| `gotify_server` | Gotify服务器地址 | 可选 |
| `gotify_token` | Gotify应用Token | 可选 |
| `gotify_app` | Gotify应用名称 | 可选 |

**注意：** 此配置文件包含敏感信息，请勿加入Git仓库。skill代码中通过 `load_api_config()` 函数读取此配置。

## Fallback Behavior

When OpenRouter API fails (e.g., 500 error), the skill automatically:
1. Detects the failure after max retries (3 attempts)
2. Switches to SiliconFlow API if configured
3. Uses `FunAudioLLM/SenseVoiceSmall` model via multipart/form-data upload
4. Continues transcription from where it left off

If both APIs fail, the skill will:
- Save the audio file for manual transcription later
- Log the error details
- Notify user of partial failure (audio saved but not transcribed)

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

## Link Archive Sub-Skill

When user provides magnet links (`magnet:?xt=...`) or ed2k links (`ed2k://|file|...`):

```bash
python3 ~/.openclaw/skills/web-clipper/scripts/archive_links.py "<text_content>"
```

**Behavior:**
- Magnet links → appended to `syncthing/raw/归档/磁链.md`
- ED2K links → appended to `syncthing/raw/归档/ed2k.md`
- Each link on its own line, no empty paragraphs
- Auto-triggers NAS sync and Gotify notification

See `ARCHIVE.md` for full documentation.

## Future Enhancements

- Playwright/Selenium fallback for heavy JS sites
- Automatic parser generation from evolution reports
- Cookie/session persistence for authenticated sites
- Batch URL processing
