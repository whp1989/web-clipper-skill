#!/bin/bash
# Auto-push web-clipper-skill updates to GitHub
# Run this after modifying clipper.py, SKILL.md, or zsxq_crawler/*.py
# Includes retry logic for PRoot SIGTERM issues

REPO_DIR="/tmp/web-clipper-skill"
SKILL_DIR="$HOME/.openclaw/skills/web-clipper"
RETRY_COUNT=0
MAX_RETRIES=3

echo "🔄 Syncing web-clipper-skill to GitHub..."

# Copy latest files
cp "$SKILL_DIR/scripts/clipper.py" "$REPO_DIR/scripts/"
cp "$SKILL_DIR/SKILL.md" "$REPO_DIR/"

# Copy zsxq_crawler submodule
cp "$SKILL_DIR/scripts/zsxq_crawler/"*.py "$REPO_DIR/scripts/zsxq_crawler/" 2>/dev/null || true

cd "$REPO_DIR" || exit 1

# Check if there are changes
if git diff --quiet; then
    echo "✅ No changes to push"
    exit 0
fi

# Commit
git add -A
git commit -m "Auto-update: $(date '+%Y-%m-%d %H:%M:%S')

Changes:
$(git diff --stat)"

# Push with retry
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    echo "🚀 Push attempt $((RETRY_COUNT + 1))/$MAX_RETRIES..."
    
    # Use timeout to avoid hanging, run in subshell
    (timeout 20 git push origin main > /tmp/git-push-$$.log 2>&1)
    PUSH_EXIT=$?
    
    if [ $PUSH_EXIT -eq 0 ]; then
        echo "✅ Pushed to https://github.com/whp1989/web-clipper-skill"
        rm -f /tmp/git-push-$$.log
        exit 0
    else
        echo "⚠️ Push failed (exit: $PUSH_EXIT), retrying..."
        cat /tmp/git-push-$$.log 2>/dev/null
        RETRY_COUNT=$((RETRY_COUNT + 1))
        sleep 5
    fi
done

echo "❌ Push failed after $MAX_RETRIES attempts"
echo "💡 Manual push: cd /tmp/web-clipper-skill && git push origin main"
echo "📋 Changes saved locally, will retry on next update"
exit 1
