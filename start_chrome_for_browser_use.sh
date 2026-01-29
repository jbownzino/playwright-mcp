#!/bin/bash

# Helper script to start Chrome with remote debugging enabled
# This avoids permission issues by using your existing Chrome browser
#
# SECURITY NOTES:
# - Remote debugging is ONLY accessible from localhost (127.0.0.1) - safe for local use
# - Uses a SEPARATE profile (not your main Chrome profile) - your personal data is safe
# - Only enable when needed, close when done
# - Do NOT expose port 9222 to the network

echo "🚀 Starting Chrome with remote debugging..."
echo ""
echo "🔒 Security Info:"
echo "  - Remote debugging is ONLY accessible from localhost (safe)"
echo "  - Using separate profile (your personal Chrome data is protected)"
echo "  - Close Chrome when done to disable remote debugging"
echo ""
echo "⚠️  Make sure Chrome is completely closed before running this!"
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."

# Kill any existing Chrome instances
pkill -f "Google Chrome" 2>/dev/null || true
sleep 1

# Create isolated profile directory in project folder (more secure)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE_DIR="$SCRIPT_DIR/.chrome-debug-profile"
mkdir -p "$PROFILE_DIR"

# Start Chrome with remote debugging on port 9222
# --remote-debugging-address=127.0.0.1 ensures it's ONLY accessible from localhost
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 \
    --remote-debugging-address=127.0.0.1 \
    --user-data-dir="$PROFILE_DIR" \
    --no-first-run \
    --no-default-browser-check \
    > /dev/null 2>&1 &

echo ""
echo "✅ Chrome started with remote debugging on port 9222 (localhost only)"
echo ""
echo "🔒 Security: Only accessible from this machine (127.0.0.1)"
echo ""
echo "Now you can:"
echo "1. Set USE_CDP=true: export USE_CDP=true"
echo "2. Or add to .env: USE_CDP=true"
echo "3. Run: python quickstart.py"
echo ""
echo "⚠️  When done, close Chrome to disable remote debugging"
echo "   Or run: pkill -f 'Google Chrome'"
