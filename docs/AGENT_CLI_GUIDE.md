# Drake AI Agent — CLI Tool Integration Guide

## Overview

The Drake AI Agent Terminal (`scripts/interactive_agent.py`) is powered by **Ollama** and supports **two modes of tool execution** simultaneously:

| Mode | Tool Type | What it does | Backend |
|---|---|---|---|
| **MCP** | `mcp` | Execute infrastructure workflows (firmware, BIOS, rollbacks) | FastMCP SSE proxy (`/mcp/sse`) |
| **CLI** | `cli` | Platform administration (ingestion, governance, audit, diagnostics) | `subprocess` → `drake --json <cmd>` |

The LLM decides which mode to use based on the user's natural-language request — no manual mode-switching required.

---

## Architecture

```
User Prompt (natural language)
        │
        ▼
  Ollama + instructor
  (ToolSelection model)
        │
        ├─── tool_type = "mcp" ───► FastMCP SSE proxy → DB workflows → Prism/iDRAC
        │
        ├─── tool_type = "cli" ───► subprocess(drake --json <subcommand>) → stdout JSON
        │
        └─── tool_type = "none" ──► Conversational reply only
```

### Key Files

| File | Purpose |
|---|---|
| [`scripts/interactive_agent.py`](../scripts/interactive_agent.py) | Main agent loop — dual-mode routing |
| [`scripts/cli_tool_registry.py`](../scripts/cli_tool_registry.py) | Static registry of 29 CLI tools with argument schemas |
| [`scripts/cli_executor.py`](../scripts/cli_executor.py) | Subprocess executor — builds `drake --json` commands, returns `CLIResult` |

---

## Quickstart

### Option A — Via `start.ps1` (Recommended)

```powershell
.\start.ps1
# At the prompt: "Do you want to start the Interactive AI Agent terminal here? (Y/N)"
# Type Y
```

### Option B — Manual Launch

```powershell
# 1. Activate venv
.venv\Scripts\Activate.ps1

# 2. Start the backend (if not already running)
drake server start

# 3. Launch agent (in a new terminal)
python scripts/interactive_agent.py
```

### Option C — CLI-Only Mode (no backend needed)

The agent automatically detects if the MCP proxy is offline and starts in **CLI-only mode**. All 29 CLI admin tools remain fully available:

```powershell
python scripts/interactive_agent.py
# Output: "MCP unavailable. Starting in CLI-only mode."
```

---

## What You Can Ask

### Platform Status
```
> what is the platform health?
> show me an overview dashboard
> run diagnostics on the database
> check if the API gateway is online
> show the system topology
```

### Workflow Clustering (Ingestion Pipeline)
```
> ingest openapi.json and discover workflows
> run the clustering pipeline on specs/idrac.yaml
> show clustering statistics
> run the full pipeline on openapi.json and auto-approve safe workflows
```

### Governance
```
> list all pending workflows for review
> show approved workflows
> review workflow wf_abc123
> approve workflow wf_abc123
> reject workflow wf_bad --reason "Missing rollback strategy"
> how many workflows are rejected?
```

### Pre-Flight Compatibility
```
> validate workflow wf_abc against 192.168.1.50
> show the compatibility cockpit for wf_abc
> explain the compatibility rules for wf_abc
> list all active compatibility rules
```

### Audit & Compliance
```
> show the audit event log
> show the execution history
> give me a compliance summary
```

### Infrastructure Execution (MCP tools — requires backend online)
```
> execute the firmware update workflow
> revert the last action on server 192.168.1.10
> check workflow compatibility for wf_abc on 10.0.0.5
> get the proxy status
```

### Ansible IaC Export
```
> preview the ansible playbook for workflow wf_abc
> export the playbook for wf_abc to playbooks/idrac.yml
```

### Runtime Management
```
> list all MCP tools currently registered
> reload the tool catalog
```

---

## Startup Modes

### Dual-Mode (Backend Online)
```
====================================================================
        DRAKE - DUAL-MODE AI AGENT TERMINAL (v2)
====================================================================
  LLM Backend  : Ollama (qwen2.5-coder:14b)
  MCP Proxy    : ONLINE - 15 workflow tools
  CLI Tools    : 29 admin commands available
```

### CLI-Only Mode (Backend Offline)
```
====================================================================
        DRAKE - DUAL-MODE AI AGENT TERMINAL (v2)
====================================================================
  LLM Backend  : Ollama (qwen2.5-coder:14b)
  MCP Proxy    : OFFLINE - CLI-only mode
  CLI Tools    : 29 admin commands available
```

---

## CLI Tool Registry

29 CLI tools are registered across 9 command groups:

| Group | Tools |
|---|---|
| Overview / Health | `drake_overview`, `drake_health` |
| Cluster | `drake_cluster_run`, `drake_cluster_summary`, `drake_cluster_graph` |
| Pipeline | `drake_pipeline` |
| Governance | `drake_governance_pending`, `drake_governance_approved`, `drake_governance_rejected`, `drake_governance_review`, `drake_governance_approve`, `drake_governance_reject` |
| Compatibility | `drake_compatibility_validate`, `drake_compatibility_dashboard`, `drake_compatibility_explain`, `drake_compatibility_rules` |
| Runtime | `drake_runtime_tools`, `drake_runtime_reload`, `drake_runtime_execute` |
| Audit | `drake_audit_events`, `drake_audit_executions`, `drake_audit_summary` |
| Ansible | `drake_ansible_preview`, `drake_ansible_export` |
| Diagnostics | `drake_diagnostics_db`, `drake_diagnostics_api`, `drake_diagnostics_compatibility`, `drake_diagnostics_runtime` |
| System | `drake_system_topology` |

---

## How CLI Tool Invocation Works

When the agent selects a CLI tool, it:

1. Looks up the tool definition in `cli_tool_registry.py`
2. Builds the full command: `python -m src.cli.main --json <subcommand> [args...]`
3. Runs it as a subprocess with `PYTHONIOENCODING=utf-8`
4. Captures stdout (always clean JSON in `--json` mode)
5. Parses the JSON and displays it in a readable format

Example — agent executing `drake_governance_pending`:
```
[SYSTEM] Executing CLI tool 'drake_governance_pending'...
  - Arguments: {}
  - Mode: JSON (machine-readable output)

[SYSTEM] CLI Execution Complete:
----------------------------------------------------------------------
  Found 33 result(s):

  [1]
      id: wf_c_d489c865
      display_name: Server Power Management
      risk_level: medium
      ...
```

---

## Configuration

All configuration is read from `.env`:

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `qwen2.5-coder:14b` | LLM model to use |
| `MCP_PROXY_URL` | `http://127.0.0.1:8001/mcp/sse` | FastMCP SSE endpoint |
| `DRAKE_DEBUG` | _(unset)_ | Set any value to enable full tracebacks |

---

## Troubleshooting

### Agent can't connect to Ollama
```
[ERROR] LLM error: Connection refused
```
**Fix**: Start Ollama — `ollama serve` or `ollama run qwen2.5-coder:14b`

### Agent says MCP is offline
```
MCP unavailable. Starting in CLI-only mode.
```
**Fix**: Start the backend — `drake server start` or re-run `start.ps1`  
CLI tools still work fully in this mode.

### LLM keeps picking wrong tool type
**Fix**: Be more explicit in your prompt:
- "run cluster command" → will prefer `cli`
- "execute the firmware workflow" → will prefer `mcp`

### CLI command returns non-zero exit
The agent displays the stderr output. Common causes:
- Invalid workflow ID (typo)
- Database not seeded (run `drake pipeline openapi.json` first)

### `DRAKE_DEBUG` mode
```powershell
$env:DRAKE_DEBUG="1"
python scripts/interactive_agent.py
```
Enables full Python tracebacks on LLM and subprocess errors.
