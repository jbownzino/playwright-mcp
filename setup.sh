#!/bin/bash

# Setup script for Python 3.12 environment

set -e

echo "Setting up Python 3.12 environment..."

# Check if Python 3.12 is available
if ! command -v python3.12 &> /dev/null; then
    echo "Python 3.12 not found. Checking pyenv..."
    
    if command -v pyenv &> /dev/null; then
        echo "Installing Python 3.12.9 via pyenv..."
        pyenv install 3.12.9
        pyenv local 3.12.9
    else
        echo "Error: Python 3.12 not found and pyenv is not available."
        echo "Please install Python 3.12 manually or install pyenv."
        exit 1
    fi
fi

# Create virtual environment
echo "Creating virtual environment..."
python3.12 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies if requirements.txt exists and is not empty
if [ -f requirements.txt ] && [ -s requirements.txt ]; then
    echo "Installing dependencies from requirements.txt..."
    pip install -r requirements.txt
else
    echo "No dependencies to install (requirements.txt is empty or doesn't exist)."
fi

echo ""
echo "Setup complete! Virtual environment is ready."
echo ""
echo "To activate the virtual environment in the future, run:"
echo "  source venv/bin/activate"
echo ""
echo "To deactivate, run:"
echo "  deactivate"
