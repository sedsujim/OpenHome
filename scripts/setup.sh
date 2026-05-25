#!/usr/bin/env bash
set -euo pipefail

# OpenHome - Zero-Cost Minecraft Server Deployment
# Prerequisites: curl, python3.11+, pip, java 17+

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

echo "[*] OpenHome Setup"
echo "=================="

# --- Java check ---
if ! command -v java &>/dev/null; then
    echo "[!] Java not found. Run scripts/install_java.sh or install manually."
    echo "    Minimum: Java 17 (OpenJDK JRE)"
fi

# --- Python check ---
PYTHON=""
for cmd in python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    echo "[!] Python 3.11+ is required."
    exit 1
fi
echo "[*] Using $($PYTHON --version)"

# --- Virtual env ---
VENV="$REPO_DIR/.venv"
if [ ! -d "$VENV" ]; then
    echo "[*] Creating virtual environment..."
    $PYTHON -m venv "$VENV"
fi
source "$VENV/bin/activate"

# --- Dependencies ---
echo "[*] Installing Python dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# --- Env file ---
if [ ! -f .env ]; then
    echo "[*] Creating .env from .env.example..."
    cp .env.example .env
    echo "[!] Edit .env with your settings before starting."
fi

# --- Prepare server directory ---
mkdir -p server

echo ""
echo "[✓] Setup complete."
echo ""
echo "    Quick start:"
echo "      1. Place server.jar in ./server/"
echo "      2. Edit .env"
echo "      3. Activate venv: source .venv/bin/activate"
echo "      4. Run: uvicorn app.main:app --reload"
echo ""
echo "    Docker:"
echo "      docker compose up -d"
echo ""
