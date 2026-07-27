#!/usr/bin/env bash
# =====================================================================
#           DELL DRAKE INFRASTRUCTURE COMMAND CENTER - STARTUP (LINUX)
# =====================================================================
# Automated startup orchestrator for local development environment.
# Sets up environment variables, launches servers, and verifies health.
# =====================================================================

# Shift context to project root
cd "$(dirname "$0")/.." || exit 1

export PYTHONIOENCODING="utf-8"

# Colors
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

tick="✓"
warn="⚠"
cross="✗"

clear
echo -e "${CYAN}=====================================================================${NC}"
echo -e "${CYAN}         DELL DRAKE - INFRASTRUCTURE COMMAND CENTER LAUNCHER         ${NC}"
echo -e "${CYAN}=====================================================================${NC}"
echo -e " Starting local development services...\n"

# Cleanup trap to kill background processes on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down background services...${NC}"
    jobs -p | xargs -r kill
}
trap cleanup EXIT

# Helper function to check port
check_port() {
    nc -z 127.0.0.1 $1 >/dev/null 2>&1
}

# ---------------------------------------------------------------------
# Step 1: Environment File Configuration
# ---------------------------------------------------------------------
echo -e "${YELLOW}[1/7] Configuring Environment Files...${NC}"
if [ ! -f .env ]; then
    echo -e "  -> No .env found. Copying .env.example..."
    cp .env.example .env
fi
# Load env variables safely
if [ -f .env ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        # Strip leading and trailing whitespace
        line=$(echo "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
        # Skip empty lines and comment lines
        if [[ -z "$line" || "$line" =~ ^# ]]; then
            continue
        fi
        # Strip inline comments
        line=$(echo "$line" | cut -d'#' -f1 | sed -e 's/[[:space:]]*$//')
        if [[ -n "$line" ]]; then
            export "$line"
        fi
    done < .env
fi

if [ ! -f frontend/.env.local ]; then
    echo -e "  -> No frontend/.env.local found. Copying frontend/.env.example..."
    if [ -f frontend/.env.example ]; then
        cp frontend/.env.example frontend/.env.local
    else
        echo "NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001" > frontend/.env.local
    fi
fi
echo -e "  ${GREEN}$tick Environment files verified.${NC}\n"

# ---------------------------------------------------------------------
# Step 2: Check uv and Setup Virtual Environment
# ---------------------------------------------------------------------
echo -e "${YELLOW}[2/7] Preparing Python Virtual Environment...${NC}"
if ! command -v uv &> /dev/null; then
    echo -e "  -> uv not detected in PATH. Attempting to install uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Determine if we should sync dependencies
SYNC_DEPS=false
if [ ! -d .venv ]; then
    echo -e "  -> Virtual environment not found. Creating .venv..."
    if command -v uv &> /dev/null; then
        uv venv
    else
        python3 -m venv .venv
    fi
    SYNC_DEPS=true
fi

# Check for --sync option
for arg in "$@"; do
    if [ "$arg" = "--sync" ]; then
        SYNC_DEPS=true
    fi
done

if [ "$SYNC_DEPS" = true ]; then
    echo -e "  -> Syncing dependencies..."
    if command -v uv &> /dev/null; then
        uv sync
        uv pip install -e .
    else
        .venv/bin/pip install -r requirements.txt
        .venv/bin/pip install -e .
    fi
    echo -e "  ${GREEN}$tick Virtual environment dependencies synced & package installed in editable mode.${NC}\n"
else
    echo -e "  -> Skipping dependency sync (run with --sync or delete .venv to update)."
    # Quick register of local packages in editable mode without reinstalling dependencies
    if command -v uv &> /dev/null; then
        uv pip install -e . --no-deps >/dev/null 2>&1 || true
    else
        .venv/bin/pip install -e . --no-deps >/dev/null 2>&1 || true
    fi
    echo -e "  ${GREEN}$tick Virtual environment ready.${NC}\n"
fi

# ---------------------------------------------------------------------
# Step 3: Check local LLM Engine (Ollama)
# ---------------------------------------------------------------------
echo -e "${YELLOW}[3/7] Checking LLM Engine (Ollama)...${NC}"
OLLAMA_HOST=${OLLAMA_HOST:-http://localhost:11434}
OLLAMA_MODEL=${OLLAMA_MODEL:-qwen2.5-coder:14b}

if ! check_port 11434; then
    echo -e "  ${RED}$warn Ollama is NOT running on port 11434!${NC}"
    if command -v ollama &> /dev/null; then
        echo -e "  -> Attempting to start Ollama application in background..."
        ollama serve > /dev/null 2>&1 &
        sleep 3
    else
        echo -e "  ${RED}[CRITICAL] Ollama executable not found in PATH.${NC}"
        echo -e "             Please install Ollama from https://ollama.com and run 'ollama run llama3'.${NC}"
    fi
fi

if check_port 11434; then
    echo -e "  ${GREEN}$tick Ollama is running.${NC}"
    if curl -s "$OLLAMA_HOST/api/tags" | grep -q "$OLLAMA_MODEL"; then
        echo -e "  ${GREEN}$tick Found LLM model: $OLLAMA_MODEL${NC}"
    else
        echo -e "  ${YELLOW}$warn Model '$OLLAMA_MODEL' not found in local Ollama repository!${NC}"
        echo -e "  -> Attempting to pull '$OLLAMA_MODEL' in background..."
        echo -e "     (This might take some time depending on your connection. You can continue work.)"
        ollama pull "$OLLAMA_MODEL" &
    fi
fi
echo ""

# ---------------------------------------------------------------------
# Step 4: Check & Start Mock API Server (Prism)
# ---------------------------------------------------------------------
echo -e "${YELLOW}[4/7] Checking Mock API Server (Prism)...${NC}"
if check_port 4010; then
    echo -e "  ${GREEN}$tick Mock API server is already running on port 4010.${NC}"
else
    if command -v docker &> /dev/null; then
        echo -e "  -> Launching Mock API container via Docker Compose..."
        if command -v docker-compose &> /dev/null; then
            docker-compose up -d --build
        else
            docker compose up -d --build
        fi
        
        # Wait for boot
        for i in {1..5}; do
            if check_port 4010; then break; fi
            sleep 1
        done
        
        if check_port 4010; then
            echo -e "  ${GREEN}$tick Mock API server started on port 4010.${NC}"
        else
            echo -e "  ${YELLOW}$warn Mock API container launched but not yet responding on port 4010.${NC}"
        fi
    else
        echo -e "  ${YELLOW}$warn Docker is not installed or not running. Cannot start mock Redfish server.${NC}"
        echo -e "     If you have a manual Mock API setup, please ensure it listens on port 4010.${NC}"
    fi
fi
echo ""

# ---------------------------------------------------------------------
# Step 5: Verify AI Guardrail & Governance Engine Integrity
# ---------------------------------------------------------------------
echo -e "${YELLOW}[5/7] Verifying AI Guardrail & Governance Engine...${NC}"
echo -e "  -> Running AI Guardrail security verification suite..."

PYTHON_BIN=$([ -f .venv/bin/python ] && echo ".venv/bin/python" || echo "python3")
$PYTHON_BIN tests/security/GOVERNANCE_HARDENING_TEST_V2.py >/dev/null 2>&1

if [ $? -eq 0 ]; then
    echo -e "  ${GREEN}$tick AI Guardrails successfully verified (Evasion, Obfuscation, and Campaign blocks operational).${NC}"
else
    echo -e "  ${YELLOW}$warn Warning: AI Guardrail security tests failed or completed with warnings.${NC}"
fi
echo ""

# ---------------------------------------------------------------------
# Step 6: Start FastAPI + FastMCP Backend
# ---------------------------------------------------------------------
echo -e "${YELLOW}[6/7] Starting FastMCP & FastAPI Proxy Server...${NC}"
if check_port 8001; then
    echo -e "  ${YELLOW}$warn Port 8001 is already in use! Backend may already be running.${NC}"
else
    echo -e "  -> Launching FastAPI Server in background..."
    mkdir -p logs
    $PYTHON_BIN -m uvicorn drake.proxy.server:app --port 8001 --host 127.0.0.1 > logs/backend.log 2>&1 &
    
    # Wait for backend
    for i in {1..10}; do
        if check_port 8001; then break; fi
        sleep 1
    done
    
    if check_port 8001; then
        echo -e "  ${GREEN}$tick FastMCP/FastAPI backend successfully started on port 8001.${NC}"
    else
        echo -e "  ${YELLOW}$warn Backend server process started, but not yet responding on port 8001.${NC}"
    fi
fi
echo ""

# ---------------------------------------------------------------------
# Step 6.5: Start Web Agent API Server
# ---------------------------------------------------------------------
echo -e "${YELLOW}[6.5/7] Starting Web Agent API Server...${NC}"
if check_port 8002; then
    echo -e "  ${YELLOW}$warn Port 8002 is already in use! Web Agent API may already be running.${NC}"
else
    echo -e "  -> Launching Web Agent API Server in background..."
    mkdir -p logs
    $PYTHON_BIN scripts/web_agent_api.py > logs/web_agent.log 2>&1 &
    
    # Wait for Web Agent API
    for i in {1..10}; do
        if check_port 8002; then break; fi
        sleep 1
    done
    
    if check_port 8002; then
        echo -e "  ${GREEN}$tick Web Agent API successfully started on port 8002.${NC}"
    else
        echo -e "  ${YELLOW}$warn Web Agent API process started, but not yet responding on port 8002.${NC}"
    fi
fi
echo ""

# ---------------------------------------------------------------------
# Step 7: Start Next.js Frontend Console
# ---------------------------------------------------------------------
echo -e "${YELLOW}[7/7] Starting Next.js Governance Console...${NC}"
if check_port 3000; then
    echo -e "  ${YELLOW}$warn Port 3000 is already in use! Frontend Console may already be running.${NC}"
else
    if command -v npm &> /dev/null; then
        if [ ! -d "frontend/node_modules" ]; then
            echo -e "  -> First time run: Installing frontend dependencies..."
            cd frontend && npm install && cd ..
        fi
        
        echo -e "  -> Launching Next.js development server in background..."
        cd frontend
        export PORT=3000
        npm run dev > ../logs/frontend.log 2>&1 &
        cd ..
        
        # Wait for frontend
        for i in {1..10}; do
            if check_port 3000; then break; fi
            sleep 1
        done
        
        if check_port 3000; then
            echo -e "  ${GREEN}$tick Next.js frontend console running on port 3000.${NC}"
        else
            echo -e "  ${YELLOW}$warn Next.js server spawned but not yet responding on port 3000.${NC}"
        fi
    else
        echo -e "  ${RED}$warn npm/Node.js is not installed. Unable to run Next.js frontend.${NC}"
    fi
fi
echo ""

# ---------------------------------------------------------------------
# Final Summary and Launching Agent Terminal
# ---------------------------------------------------------------------
echo -e "${CYAN}=====================================================================${NC}"
echo -e "${CYAN}                      SERVICES SYSTEM SUMMARY                        ${NC}"
echo -e "${CYAN}=====================================================================${NC}"
echo -e "  ${GREEN}- Next.js Web Governance Console : http://localhost:3000${NC}"
echo -e "  ${GREEN}- FastAPI REST Subsystems        : http://127.0.0.1:8001/docs${NC}"
echo -e "  ${GREEN}- FastMCP SSE Proxy Endpoint     : http://127.0.0.1:8001/mcp/sse${NC}"
echo -e "  ${GREEN}- Web Agent API Server           : http://127.0.0.1:8002/docs${NC}"
echo -e "  ${GREEN}- Mock Redfish Server (Prism)    : http://localhost:4010${NC}"
echo -e "  ${GREEN}- Local Ollama Service           : http://localhost:11434${NC}"
echo -e "${CYAN}=====================================================================${NC}\n"

read -p "Do you want to start the Interactive AI Agent terminal here? (Y/N) " agentChoice
if [[ "$agentChoice" =~ ^[Yy]es|[Yy]$ ]]; then
    echo -e "${CYAN}Launching AI Agent Terminal...${NC}"
    $PYTHON_BIN scripts/interactive_agent.py
else
    echo -e "${GRAY}Startup complete! You can run the interactive agent later using:${NC}"
    echo -e "${CYAN}  source .venv/bin/activate${NC}"
    echo -e "${CYAN}  python scripts/interactive_agent.py${NC}\n"
    
    echo -e "${YELLOW}Press Ctrl+C to terminate all background services (FastAPI & Next.js).${NC}"
    # Wait indefinitely until SIGINT (Ctrl+C) kills the background processes via trap
    while true; do sleep 86400; done
fi
