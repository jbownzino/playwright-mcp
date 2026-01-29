#!/bin/bash

# Browser-Use Installation Script
# Follows the quickstart guide from https://docs.browser-use.com

set -e

echo "Installing Browser-Use..."

# Activate virtual environment
source venv/bin/activate

# Install browser-use using uv (preferred) or pip
if command -v uv &> /dev/null; then
    echo "Using uv to install browser-use..."
    uv pip install browser-use || pip install browser-use
else
    echo "Using pip to install browser-use..."
    pip install --upgrade pip
    pip install browser-use
fi

# Install chromium browser
echo "Installing Chromium browser..."
uvx browser-use install || echo "Note: If uvx fails, chromium will be installed automatically on first run"

echo ""
echo "✅ Browser-Use installation complete!"
echo ""
echo "Next steps:"
echo "1. Add your LLM API key to the .env file (Google Gemini recommended - free tier)"
echo "2. Get Google Gemini API key: https://aistudio.google.com/app/u/1/apikey?pli=1"
echo "3. Run the quickstart: python quickstart.py"
