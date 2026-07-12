#!/bin/bash
# AlphaStack Quick Installer
# Usage: curl -sSL https://raw.githubusercontent.com/ovalentine964/alphastack/main/install.sh | bash

set -e

echo "╔══════════════════════════════════════════╗"
echo "║       AlphaStack Installer v0.1.0        ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Detect OS
OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
    Linux*)
        echo "🐧 Detected: Linux ($ARCH)"
        echo ""
        echo "Installing AlphaStack..."
        echo ""
        
        # Install dependencies
        if command -v apt-get &> /dev/null; then
            sudo apt-get update -qq
            sudo apt-get install -y -qq python3 python3-pip python3-venv git curl
        elif command -v yum &> /dev/null; then
            sudo yum install -y python3 python3-pip git curl
        elif command -v pacman &> /dev/null; then
            sudo pacman -S --noconfirm python python-pip git curl
        fi
        
        # Clone and setup
        git clone https://github.com/ovalentine964/alphastack.git
        cd alphastack
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt 2>/dev/null || pip install pydantic redis sqlalchemy structlog prometheus-client fastapi uvicorn
        
        # Copy config
        cp config/alphastack.yaml config/alphastack.local.yaml 2>/dev/null || true
        
        echo ""
        echo "✅ AlphaStack installed!"
        echo ""
        echo "To start:"
        echo "  cd alphastack"
        echo "  source venv/bin/activate"
        echo "  python -m alphastack.main"
        echo ""
        echo "Web dashboard: http://localhost:3000"
        echo "API docs: http://localhost:8000/docs"
        ;;
        
    Darwin*)
        echo "🍎 Detected: macOS ($ARCH)"
        echo ""
        echo "Installing AlphaStack..."
        echo ""
        
        # Install dependencies
        if ! command -v brew &> /dev/null; then
            echo "Installing Homebrew..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
        
        brew install python3 git curl
        
        # Clone and setup
        git clone https://github.com/ovalentine964/alphastack.git
        cd alphastack
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt 2>/dev/null || pip install pydantic redis sqlalchemy structlog prometheus-client fastapi uvicorn
        
        # Copy config
        cp config/alphastack.yaml config/alphastack.local.yaml 2>/dev/null || true
        
        echo ""
        echo "✅ AlphaStack installed!"
        echo ""
        echo "To start:"
        echo "  cd alphastack"
        echo "  source venv/bin/activate"
        echo "  python -m alphastack.main"
        echo ""
        echo "Web dashboard: http://localhost:3000"
        echo "API docs: http://localhost:8000/docs"
        ;;
        
    MINGW*|MSYS*|CYGWIN*)
        echo "🪟 Detected: Windows"
        echo ""
        echo "For Windows, use PowerShell (Run as Administrator):"
        echo ""
        echo '  irm https://raw.githubusercontent.com/ovalentine964/alphastack/main/install.ps1 | iex'
        echo ""
        echo "Or download the desktop app installer:"
        echo "  https://github.com/ovalentine964/alphastack/releases/latest"
        ;;
        
    *)
        echo "❌ Unsupported OS: $OS"
        echo "Download manually: https://github.com/ovalentine964/alphastack/releases/latest"
        exit 1
        ;;
esac
