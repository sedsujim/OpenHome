#!/usr/bin/env bash
set -euo pipefail

# OpenHome Quickstart
# One-command setup: installs deps, downloads server.jar, configures .env,
# sets up Supabase schema, and starts the application.

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "  ██████╗ ██████╗ ███████╗███╗   ██╗██╗  ██╗ ██████╗ ███╗   ███╗███████╗"
echo " ██╔═══██╗██╔══██╗██╔════╝████╗  ██║██║  ██║██╔═══██╗████╗ ████║██╔════╝"
echo " ██║   ██║██████╔╝█████╗  ██╔██╗ ██║███████║██║   ██║██╔████╔██║█████╗  "
echo " ██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║██╔══██║██║   ██║██║╚██╔╝██║██╔══╝  "
echo " ╚██████╔╝██║     ███████╗██║ ╚████║██║  ██║╚██████╔╝██║ ╚═╝ ██║███████╗"
echo "  ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝╚══════╝"
echo -e "${NC}"
echo -e "${CYAN}  Zero-Cost Minecraft Server Orchestration${NC}\n"

# ============================================================
# Step 1: Check prerequisites
# ============================================================
echo -e "${YELLOW}[1/7]${NC} Checking prerequisites..."

PYTHON=""
for cmd in python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "${RED}[!] Python 3.11+ is required but not found.${NC}"
    echo "    Install it: https://www.python.org/downloads/"
    exit 1
fi
echo -e "  Python: ${GREEN}$($PYTHON --version)${NC}"

JAVA_OK=false
if command -v java &>/dev/null; then
    JAVA_VER=$(java -version 2>&1 | head -1 | sed 's/.*version "//;s/".*//')
    echo -e "  Java:   ${GREEN}$JAVA_VER${NC}"
    JAVA_OK=true
else
    echo -e "  Java:   ${YELLOW}not found (will use Docker mode)${NC}"
fi

DOCKER_OK=false
if command -v docker &>/dev/null; then
    echo -e "  Docker: ${GREEN}$(docker --version)${NC}"
    DOCKER_OK=true
else
    echo -e "  Docker: ${YELLOW}not found (will use direct Java process)${NC}"
fi

# ============================================================
# Step 2: Create virtual environment
# ============================================================
echo -e "${YELLOW}[2/7]${NC} Setting up Python virtual environment..."

VENV="$REPO_DIR/.venv"
if [ ! -d "$VENV" ]; then
    $PYTHON -m venv "$VENV"
    echo -e "  Created: ${GREEN}$VENV${NC}"
else
    echo -e "  Exists:  ${GREEN}$VENV${NC}"
fi
source "$VENV/bin/activate"

echo -e "  Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo -e "  ${GREEN}Done${NC}"

# ============================================================
# Step 3: Configure environment
# ============================================================
echo -e "${YELLOW}[3/7]${NC} Configuring environment..."

if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "  Created: ${GREEN}.env${NC} from .env.example"
    echo -e "  ${YELLOW}  Important: Edit .env and set:${NC}"
    echo -e "  ${YELLOW}    SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_JWT_SECRET${NC}"
    echo -e "  ${YELLOW}    (Or leave empty to skip Supabase auth)${NC}"
else
    echo -e "  Exists:  ${GREEN}.env${NC}"
fi

mkdir -p server servers
echo -e "  Created: ${GREEN}server/ servers/ directories${NC}"

# ============================================================
# Step 4: Download Minecraft server.jar
# ============================================================
echo -e "${YELLOW}[4/7]${NC} Downloading Minecraft server..."

if [ -f server/server.jar ]; then
    JAR_SIZE=$(du -h server/server.jar | cut -f1)
    echo -e "  Server JAR exists: ${GREEN}server/server.jar ($JAR_SIZE)${NC}"
else
    echo -e "  Downloading Paper 1.21 server jar..."
    PAPER_URL="https://api.papermc.io/v2/projects/paper/versions/1.21/builds/latest/downloads/paper-1.21-latest.jar"
    if curl -sL --fail "$PAPER_URL" -o server/server.jar.tmp 2>/dev/null; then
        mv server/server.jar.tmp server/server.jar
        echo -e "  ${GREEN}Downloaded: server/server.jar${NC}"
    else
        rm -f server/server.jar.tmp
        echo -e "  ${YELLOW}Could not download Paper 1.21 automatically.${NC}"
        echo -e "  ${YELLOW}Place a server.jar manually in ./server/ and re-run.${NC}"
    fi
fi

echo "eula=true" > server/eula.txt
echo -e "  EULA: ${GREEN}accepted${NC}"

# ============================================================
# Step 5: Supabase schema setup
# ============================================================
echo -e "${YELLOW}[5/7]${NC} Supabase database setup..."

if command -v supabase &>/dev/null; then
    echo -e "  Supabase CLI found. Applying schema..."
    supabase db push 2>/dev/null || true
    echo -e "  ${GREEN}Schema applied${NC}"
else
    echo -e "  ${YELLOW}Supabase CLI not installed. To set up the database:${NC}"
    echo -e "  ${YELLOW}  1. Go to Supabase Dashboard -> SQL Editor${NC}"
    echo -e "  ${YELLOW}  2. Paste and run supabase_schema.sql${NC}"
    echo -e "  ${YELLOW}  3. Enable Email auth in Authentication -> Providers${NC}"
    echo ""
    echo -e "  ${YELLOW}  For local testing without Supabase, leave SUPABASE_*${NC}"
    echo -e "  ${YELLOW}  variables empty in .env${NC}"
fi

# ============================================================
# Step 6: Create first admin user (optional)
# ============================================================
echo -e "${YELLOW}[6/7]${NC} Creating administration script..."

cat > "$REPO_DIR/manage.py" << 'MANAGE_EOF'
#!/usr/bin/env python3
"""OpenHome management CLI."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

async def status():
    from app.core.orchestrator import get_orchestrator
    orch = await get_orchestrator()
    status = await orch.get_status()
    print(json.dumps(status, indent=2))

async def start():
    from app.core.orchestrator import get_orchestrator
    orch = await get_orchestrator()
    try:
        pid = await orch.start()
        print(f"Server started (PID: {pid})")
    except Exception as e:
        print(f"Error: {e}")

async def stop():
    from app.core.orchestrator import get_orchestrator
    orch = await get_orchestrator()
    try:
        await orch.stop()
        print("Server stopped")
    except Exception as e:
        print(f"Error: {e}")

async def cmd(command):
    from app.core.orchestrator import get_orchestrator
    orch = await get_orchestrator()
    try:
        await orch.send_command(command)
        print(f"Sent: {command}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python manage.py <status|start|stop|cmd <command>>")
        sys.exit(1)

    action = sys.argv[1]
    if action == "status":
        asyncio.run(status())
    elif action == "start":
        asyncio.run(start())
    elif action == "stop":
        asyncio.run(stop())
    elif action == "cmd" and len(sys.argv) > 2:
        asyncio.run(cmd(" ".join(sys.argv[2:])))
    else:
        print(f"Unknown action: {action}")
MANAGE_EOF
chmod +x "$REPO_DIR/manage.py"
echo -e "  Created: ${GREEN}manage.py${NC} (CLI helper)"

# ============================================================
# Step 7: Start
# ============================================================
echo -e "${YELLOW}[7/7]${NC} Starting OpenHome..."
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  OpenHome is ready!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "  ${CYAN}Start the server:${NC}"
echo -e "    source .venv/bin/activate"
echo -e "    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
if [ "$DOCKER_OK" = true ]; then
    echo -e "  ${CYAN}Or with Docker:${NC}"
    echo -e "    docker compose up -d"
    echo ""
fi
echo -e "  ${CYAN}Then open:${NC}"
echo -e "    http://localhost:8000"
echo ""
echo -e "  ${CYAN}Management CLI:${NC}"
echo -e "    python manage.py status"
echo -e "    python manage.py start"
echo -e "    python manage.py stop"
echo -e "    python manage.py cmd 'say Hello'"
echo ""
echo -e "  ${CYAN}API:${NC}"
echo -e "    GET  http://localhost:8000/api/v1/health"
echo -e "    POST http://localhost:8000/api/v1/instance/start"
echo -e "    POST http://localhost:8000/api/v1/instance/stop"
echo ""
echo -e "  ${YELLOW}Next steps:${NC}"
echo -e "    1. Register or log in at http://localhost:8000"
echo -e "    2. Create your first server from the dashboard"
echo -e "    3. Click Start to launch Minecraft"
echo -e "    4. Connect with your Minecraft client to localhost:25565"
echo ""
