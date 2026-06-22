# =====================================================================
#           DELL DRAKE INFRASTRUCTURE COMMAND CENTER - STARTUP
# =====================================================================
# Automated startup orchestrator for local development environment.
# Sets up environment variables, launches servers, and verifies health.
# =====================================================================

# Enable UTF-8 encoding for Unicode characters (warnings, checkmarks)
$env:PYTHONIOENCODING="utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Shift context to project root since script is now in windows_scripts/
$PSScriptRoot = Split-Path -Parent -MyInvocation.MyCommand.Definition
Set-Location -Path "$PSScriptRoot\.."

# Define unicode symbols programmatically to avoid file encoding parser issues
$tick  = [char]0x2714
$warn  = [char]0x26A0
$cross = [char]0x2717

Clear-Host
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "         DELL DRAKE - INFRASTRUCTURE COMMAND CENTER LAUNCHER" -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host " Starting local development services..." -ForegroundColor White
Write-Host ""

# Helper function to check if a port is open
function Test-PortOpen ($port) {
    $connection = New-Object System.Net.Sockets.TcpClient
    try {
        $connection.Connect("127.0.0.1", $port)
        $connection.Close()
        return $true
    } catch {
        return $false
    }
}

# Helper function to load env variables from .env
function Load-Env {
    if (Test-Path ".env") {
        Get-Content ".env" | ForEach-Object {
            $line = $_.Trim()
            if ($line -and !$line.StartsWith("#") -and $line.Contains("=")) {
                $key, $value = $line.Split("=", 2)
                $key = $key.Trim()
                $value = $value.Trim()
                if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                    $value = $value.Substring(1, $value.Length - 2)
                }
                [System.Environment]::SetEnvironmentVariable($key, $value)
            }
        }
    }
}

# ---------------------------------------------------------------------
# Step 1: Environment File Configuration
# ---------------------------------------------------------------------
Write-Host "[1/7] Configuring Environment Files..." -ForegroundColor Yellow
if (!(Test-Path ".env")) {
    Write-Host "  -> No .env found. Copying .env.example..." -ForegroundColor Gray
    Copy-Item ".env.example" ".env"
}
Load-Env

if (!(Test-Path "frontend/.env.local")) {
    Write-Host "  -> No frontend/.env.local found. Copying frontend/.env.example..." -ForegroundColor Gray
    if (Test-Path "frontend/.env.example") {
        Copy-Item "frontend/.env.example" "frontend/.env.local"
    } else {
        Set-Content -Path "frontend/.env.local" -Value "NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001"
    }
}
Write-Host "  $tick Environment files verified." -ForegroundColor Green
Write-Host ""

# ---------------------------------------------------------------------
# Step 2: Check uv and Setup Virtual Environment
# ---------------------------------------------------------------------
Write-Host "[2/7] Preparing Python Virtual Environment..." -ForegroundColor Yellow

$hasUv = $false
if (Get-Command uv -ErrorAction SilentlyContinue) {
    $hasUv = $true
}

if (!(Test-Path ".venv")) {
    Write-Host "  -> Virtual environment not found. Creating .venv..." -ForegroundColor Gray
    if ($hasUv) {
        & uv venv
    } else {
        Write-Host "  -> uv not detected in PATH. Attempting to install uv..." -ForegroundColor Gray
        try {
            powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
            $env:Path += ";$($env:USERPROFILE)\.local\bin"
            if (Get-Command uv -ErrorAction SilentlyContinue) {
                $hasUv = $true
                & uv venv
            } else {
                throw "uv install succeeded but not found in PATH."
            }
        } catch {
            Write-Host "  -> Fallback: Creating .venv with standard python -m venv..." -ForegroundColor Gray
            & python -m venv .venv
        }
    }
}

# Sync dependencies
Write-Host "  -> Syncing dependencies..." -ForegroundColor Gray
if ($hasUv) {
    & uv sync
    & uv pip install -e .
} else {
    # Install with pip directly from venv to ensure isolation
    & .venv\Scripts\pip.exe install -r requirements.txt
    & .venv\Scripts\pip.exe install -e .
}
Write-Host "  $tick Virtual environment dependencies synced & package installed in editable mode." -ForegroundColor Green
Write-Host ""

# ---------------------------------------------------------------------
# Step 3: Check local LLM Engine (Ollama)
# ---------------------------------------------------------------------
Write-Host "[3/7] Checking LLM Engine (Ollama)..." -ForegroundColor Yellow

$ollamaHost = $env:OLLAMA_HOST
if (!$ollamaHost) {
    $ollamaHost = "http://localhost:11434"
}
$expectedModel = $env:OLLAMA_MODEL
if (!$expectedModel) {
    $expectedModel = "qwen2.5-coder:14b"
}

if (!(Test-PortOpen 11434)) {
    Write-Host "  $warn Ollama is NOT running on port 11434!" -ForegroundColor Red
    Write-Host "  -> Attempting to start Ollama application..." -ForegroundColor Gray
    if (Get-Command ollama -ErrorAction SilentlyContinue) {
        Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
        Write-Host "  -> Ollama process initiated. Waiting for startup..." -ForegroundColor Gray
        Start-Sleep -Seconds 3
    } else {
        Write-Host "  [CRITICAL] Ollama executable not found in PATH." -ForegroundColor Red
        Write-Host "             Please install Ollama from https://ollama.com and run 'ollama run llama3'." -ForegroundColor Red
    }
}

if (Test-PortOpen 11434) {
    Write-Host "  $tick Ollama is running." -ForegroundColor Green
    try {
        $response = Invoke-RestMethod -Uri "$ollamaHost/api/tags" -Method Get -TimeoutSec 2
        $models = $response.models.name
        
        $hasModel = $false
        foreach ($m in $models) {
            if ($m -like "*$expectedModel*") {
                $hasModel = $true
                break
            }
        }
        
        if ($hasModel) {
            Write-Host "  $tick Found LLM model: $expectedModel" -ForegroundColor Green
        } else {
            Write-Host "  $warn Model '$expectedModel' not found in local Ollama repository!" -ForegroundColor Yellow
            Write-Host "  -> Attempting to pull '$expectedModel' in background..." -ForegroundColor Gray
            Write-Host "     (This might take some time depending on your connection. You can continue work.)" -ForegroundColor Gray
            Start-Process ollama -ArgumentList "pull $expectedModel" -NoNewWindow
        }
    } catch {
        Write-Host "  $warn Could not query Ollama models list. Make sure the port is fully responsive." -ForegroundColor Yellow
    }
}
Write-Host ""

# ---------------------------------------------------------------------
# Step 4: Check & Start Mock API Server (Prism)
# ---------------------------------------------------------------------
Write-Host "[4/7] Checking Mock API Server (Prism)..." -ForegroundColor Yellow

if (Test-PortOpen 4010) {
    Write-Host "  $tick Mock API server is already running on port 4010." -ForegroundColor Green
} else {
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        Write-Host "  -> Launching Mock API container via Docker Compose..." -ForegroundColor Gray
        if ($hasUv) {
            Start-Process docker -ArgumentList "compose up -d --build" -NoNewWindow -Wait
        } else {
            Start-Process docker-compose -ArgumentList "up -d --build" -NoNewWindow -Wait
        }
        
        # Wait a little for boot
        for ($i=1; $i -le 5; $i++) {
            if (Test-PortOpen 4010) { break }
            Start-Sleep -Seconds 1
        }
        
        if (Test-PortOpen 4010) {
            Write-Host "  $tick Mock API server started on port 4010." -ForegroundColor Green
        } else {
            Write-Host "  $warn Mock API container launched but not yet responding on port 4010." -ForegroundColor Yellow
        }
    } else {
        Write-Host "  $warn Docker is not installed or not running. Cannot start mock Redfish server." -ForegroundColor Yellow
        Write-Host "     If you have a manual Mock API setup, please ensure it listens on port 4010." -ForegroundColor Yellow
    }
}
Write-Host ""

# ---------------------------------------------------------------------
# Step 5: Verify AI Guardrail & Governance Engine Integrity
# ---------------------------------------------------------------------
Write-Host "[5/7] Verifying AI Guardrail & Governance Engine..." -ForegroundColor Yellow
Write-Host "  -> Running AI Guardrail security verification suite..." -ForegroundColor Gray

if (Test-Path ".venv\Scripts\python.exe") {
    & .venv\Scripts\python.exe tests/security/GOVERNANCE_HARDENING_TEST_V2.py | Out-Null
} else {
    & python tests/security/GOVERNANCE_HARDENING_TEST_V2.py | Out-Null
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "  $tick AI Guardrails successfully verified (Evasion, Obfuscation, and Campaign blocks operational)." -ForegroundColor Green
} else {
    Write-Host "  $warn Warning: AI Guardrail security tests failed or completed with warnings." -ForegroundColor Yellow
}
Write-Host ""

# ---------------------------------------------------------------------
# Step 6: Start FastAPI + FastMCP Backend
# ---------------------------------------------------------------------
Write-Host "[6/7] Starting FastMCP & FastAPI Proxy Server..." -ForegroundColor Yellow

if (Test-PortOpen 8001) {
    Write-Host "  $warn Port 8001 is already in use! Backend may already be running." -ForegroundColor Yellow
} else {
    Write-Host "  -> Launching FastAPI Server in a separate window..." -ForegroundColor Gray
    
    $backendCmd = @"
`$env:PYTHONIOENCODING='utf-8';
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;
Write-Host '=====================================================' -ForegroundColor Cyan;
Write-Host '            DELL DRAKE BACKEND PROXY SERVER' -ForegroundColor Cyan;
Write-Host '=====================================================' -ForegroundColor Cyan;
if (Test-Path ".venv\Scripts\python.exe") {
    & .venv\Scripts\python.exe -m uvicorn drake.proxy.server:app --port 8001 --host 127.0.0.1
} else {
    python -m uvicorn drake.proxy.server:app --port 8001 --host 127.0.0.1
}
Read-Host 'Press Enter to exit'
"@
    
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -WindowStyle Normal
    
    # Wait for the backend to start accepting connections
    Write-Host "  -> Waiting for backend API to initialize..." -ForegroundColor Gray
    for ($i=1; $i -le 10; $i++) {
        if (Test-PortOpen 8001) { break }
        Start-Sleep -Seconds 1
    }
    
    if (Test-PortOpen 8001) {
        Write-Host "  $tick FastMCP/FastAPI backend successfully started on port 8001." -ForegroundColor Green
    } else {
        Write-Host "  $warn Backend server process started, but not yet responding on port 8001." -ForegroundColor Yellow
        Write-Host "     Check the newly opened PowerShell window for errors." -ForegroundColor Yellow
    }
}
Write-Host ""

# ---------------------------------------------------------------------
# Step 7: Start Next.js Frontend Console
# ---------------------------------------------------------------------
Write-Host "[7/7] Starting Next.js Governance Console..." -ForegroundColor Yellow

if (Test-PortOpen 3000) {
    Write-Host "  $warn Port 3000 is already in use! Frontend Console may already be running." -ForegroundColor Yellow
} else {
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        if (!(Test-Path "frontend/node_modules")) {
            Write-Host "  -> First time run: Installing frontend dependencies..." -ForegroundColor Gray
            Push-Location frontend
            Start-Process npm -ArgumentList "install" -NoNewWindow -Wait
            Pop-Location
        }
        
        Write-Host "  -> Launching Next.js development server in a separate window..." -ForegroundColor Gray
        $frontendCmd = @"
`$env:PORT=3000;
Write-Host '=====================================================' -ForegroundColor Cyan;
Write-Host '            DELL DRAKE GOVERNANCE FRONTEND' -ForegroundColor Cyan;
Write-Host '=====================================================' -ForegroundColor Cyan;
cd frontend;
npm run dev;
Read-Host 'Press Enter to exit'
"@
        
        Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd -WindowStyle Normal
        
        # Wait for the frontend to bind to 3000
        for ($i=1; $i -le 10; $i++) {
            if (Test-PortOpen 3000) { break }
            Start-Sleep -Seconds 1
        }
        
        if (Test-PortOpen 3000) {
            Write-Host "  $tick Next.js frontend console running on port 3000." -ForegroundColor Green
        } else {
            Write-Host "  $warn Next.js server spawned but not yet responding on port 3000." -ForegroundColor Yellow
        }
    } else {
        Write-Host "  $warn npm/Node.js is not installed. Unable to run Next.js frontend." -ForegroundColor Red
        Write-Host "     Please install Node.js from https://nodejs.org." -ForegroundColor Red
    }
}
Write-Host ""

# ---------------------------------------------------------------------
# Final Summary and Launching Agent Terminal
# ---------------------------------------------------------------------
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "                      SERVICES SYSTEM SUMMARY" -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "  - Next.js Web Governance Console : http://localhost:3000" -ForegroundColor Green
Write-Host "  - FastAPI REST Subsystems        : http://127.0.0.1:8001/docs" -ForegroundColor Green
Write-Host "  - FastMCP SSE Proxy Endpoint     : http://127.0.0.1:8001/mcp/sse" -ForegroundColor Green
Write-Host "  - Mock Redfish Server (Prism)    : http://localhost:4010" -ForegroundColor Green
Write-Host "  - Local Ollama Service           : http://localhost:11434" -ForegroundColor Green
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""

$agentChoice = Read-Host "Do you want to start the Interactive AI Agent terminal here? (Y/N)"
if ($agentChoice.Trim().ToLower() -in @("y", "yes")) {
    Write-Host "Launching AI Agent Terminal..." -ForegroundColor Cyan
    if (Test-Path ".venv\Scripts\python.exe") {
        & .venv\Scripts\python.exe scripts/interactive_agent.py
    } else {
        python scripts/interactive_agent.py
    }
} else {
    Write-Host "Startup complete! You can run the interactive agent later using:" -ForegroundColor Gray
    Write-Host "  .venv\Scripts\Activate.ps1" -ForegroundColor Cyan
    Write-Host "  python scripts/interactive_agent.py" -ForegroundColor Cyan
    Write-Host ""
}
