"""
web_agent_api.py
================
FastAPI backend for the Drake AI Agent Web Interface.

Mirrors the logic of interactive_agent.py but exposes it as a REST API.
Does NOT modify or import the display functions — instead uses the same
underlying executors (run_cli_tool, session.call_tool) directly.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import traceback
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Project root path adjustment
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPTS_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from scripts.cli_tool_registry import CLI_TOOLS, as_llm_schema, get_tool
from scripts.cli_executor import run_cli_tool, validate_cli_arguments
from scripts.interactive_agent import (
    _MCP_AVAILABLE,
    MCP_PROXY_URL,
    MODEL_NAME,
    OLLAMA_BASE_URL,
    ToolSelection,
    _fuzzy_correct_name,
    _normalize_mcp_arguments,
    validate_mcp_arguments,
    decide_tool_with_llm,
)

if _MCP_AVAILABLE:
    from mcp import ClientSession
    from mcp.client.sse import sse_client

try:
    from openai import AsyncOpenAI
    import instructor
except ImportError:
    print("[FATAL] Missing dependencies. Run: pip install openai instructor")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Global State
# ---------------------------------------------------------------------------
class AgentState:
    mcp_online: bool = False
    mcp_session: Optional[Any] = None
    available_mcp_tools: List[dict] = []
    llm_client: Optional[Any] = None
    _exit_stack: Optional[Any] = None

state = AgentState()


# ---------------------------------------------------------------------------
# Lifespan (replaces deprecated on_event)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    # Initialize LLM Client
    state.llm_client = instructor.from_openai(
        AsyncOpenAI(
            base_url=OLLAMA_BASE_URL,
            api_key="ollama",
        ),
        mode=instructor.Mode.JSON,
    )
    print(f"[WEB-AGENT] LLM client ready ({MODEL_NAME} @ {OLLAMA_BASE_URL})")
    print(f"[WEB-AGENT] CLI tools available: {len(CLI_TOOLS)}")

    # Initialize MCP Session
    if _MCP_AVAILABLE:
        print(f"[WEB-AGENT] Connecting to MCP proxy ({MCP_PROXY_URL})...")
        try:
            from contextlib import AsyncExitStack
            state._exit_stack = AsyncExitStack()

            _sse_ctx = sse_client(MCP_PROXY_URL)

            async with asyncio.timeout(5):
                _streams = await state._exit_stack.enter_async_context(_sse_ctx)

            _read, _write = _streams
            _session_ctx = ClientSession(_read, _write)

            async with asyncio.timeout(5):
                state.mcp_session = await state._exit_stack.enter_async_context(_session_ctx)
                await state.mcp_session.initialize()

            tools_response = await state.mcp_session.list_tools()
            for t in tools_response.tools:
                state.available_mcp_tools.append({
                    "name": t.name,
                    "description": t.description or "No description",
                    "inputSchema": t.inputSchema,
                })
            state.mcp_online = True
            print(f"[WEB-AGENT] MCP ONLINE — {len(state.available_mcp_tools)} workflow tools loaded.")

        except Exception as e:
            print(f"[WEB-AGENT] MCP unavailable ({type(e).__name__}: {e}). CLI-only mode.")
    else:
        print("[WEB-AGENT] MCP package not installed. CLI-only mode.")

    yield  # --- APP RUNS ---

    # --- SHUTDOWN ---
    if state._exit_stack:
        await state._exit_stack.aclose()
    print("[WEB-AGENT] Shutdown complete.")


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(title="Drake Web Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    agent_response: str
    reasoning: str
    tool_type: str
    tool_name: str
    arguments: dict
    execution_output: str
    is_error: bool = False


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "mcp_online": state.mcp_online,
        "mcp_tools": len(state.available_mcp_tools),
        "cli_tools": len(CLI_TOOLS),
    }


# ---------------------------------------------------------------------------
# Chat endpoint
# ---------------------------------------------------------------------------
@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Empty message")

    cli_tools_schema = as_llm_schema()

    # ── Step 1: Ask LLM to decide ─────────────────────────────────────────
    try:
        selection = await decide_tool_with_llm(
            state.llm_client, request.message, state.available_mcp_tools, cli_tools_schema
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Error: {e}")

    tool_type = selection.tool_type.lower().strip()
    tool_name = selection.selected_tool_name.strip()

    # Auto-correct tool_type based on actual tool category
    mcp_names = [t["name"] for t in state.available_mcp_tools]
    cli_names = [t["name"] for t in CLI_TOOLS]

    if tool_name in mcp_names:
        tool_type = "mcp"
    elif tool_name in cli_names:
        tool_type = "cli"

    execution_output = ""
    is_error = False

    # ── Step 2: Execute ───────────────────────────────────────────────────
    if tool_type == "none" or tool_name.upper() == "NONE":
        execution_output = ""

    elif tool_type == "cli":
        # Fuzzy correct
        if tool_name not in cli_names:
            corrected = _fuzzy_correct_name(tool_name, cli_names)
            if corrected:
                tool_name = corrected
                selection.selected_tool_name = corrected
            else:
                execution_output = f"CLI tool '{tool_name}' not found."
                is_error = True

        if not is_error and tool_name in cli_names:
            # Validate
            valid, msg = validate_cli_arguments(tool_name, selection.arguments)
            if not valid:
                execution_output = f"Validation failed: {msg}"
                is_error = True
            else:
                # Run the CLI tool via subprocess (no stdin needed)
                result = run_cli_tool(tool_name, selection.arguments)
                if result.success:
                    if result.parsed is not None:
                        execution_output = json.dumps(result.parsed, indent=2)
                    else:
                        execution_output = result.stdout or "(Command completed with no output)"
                else:
                    execution_output = result.summary_for_agent()
                    is_error = True

    elif tool_type == "mcp":
        if not state.mcp_online or state.mcp_session is None:
            execution_output = "MCP proxy is offline. Cannot execute MCP tools. Start the backend with 'drake server start' and restart the web agent."
            is_error = True
        else:
            # Fuzzy correct
            if tool_name not in mcp_names:
                corrected = _fuzzy_correct_name(tool_name, mcp_names)
                if corrected:
                    tool_name = corrected
                    selection.selected_tool_name = corrected
                else:
                    execution_output = f"MCP tool '{tool_name}' not found."
                    is_error = True

            if not is_error and tool_name in mcp_names:
                # Normalize arguments
                arguments = _normalize_mcp_arguments(
                    selection.arguments, state.available_mcp_tools, tool_name
                )

                # Validate
                valid, msg = validate_mcp_arguments(tool_name, arguments, state.available_mcp_tools)
                if not valid:
                    # Try filling from schema defaults - strip unexpected keys
                    schema = next(
                        (t["inputSchema"] for t in state.available_mcp_tools if t["name"] == tool_name),
                        {}
                    )
                    valid_keys = set(schema.get("properties", {}).keys()) | {"override_policy"}
                    for k in list(arguments.keys()):
                        if k not in valid_keys:
                            arguments.pop(k)
                    valid, msg = validate_mcp_arguments(tool_name, arguments, state.available_mcp_tools)

                if not valid:
                    execution_output = f"MCP validation failed: {msg}"
                    is_error = True
                else:
                    try:
                        result = await state.mcp_session.call_tool(tool_name, arguments=arguments)

                        # Check for policy block
                        is_blocked = any(
                            c.type == "text" and "Execution blocked: confidence score" in c.text
                            for c in result.content
                        )

                        if is_blocked:
                            # Auto-override in web mode
                            arguments["override_policy"] = "WARN_ONLY"
                            result = await state.mcp_session.call_tool(tool_name, arguments=arguments)

                        # Parse result
                        output_parts = []
                        has_error = getattr(result, "isError", False)
                        for content in result.content:
                            if content.type == "text":
                                try:
                                    parsed = json.loads(content.text)
                                    if isinstance(parsed, dict) and "error" in parsed:
                                        output_parts.append(f"[ERROR] {parsed['error']}")
                                        is_error = True
                                    else:
                                        output_parts.append(json.dumps(parsed, indent=2))
                                except (json.JSONDecodeError, TypeError):
                                    output_parts.append(content.text)
                                    if has_error:
                                        is_error = True
                            else:
                                output_parts.append(f"[{content.type}]: {content}")
                        execution_output = "\n".join(output_parts)

                    except Exception as mcp_err:
                        execution_output = f"MCP execution error: {mcp_err}"
                        is_error = True
    else:
        execution_output = f"Unknown tool_type '{tool_type}' returned by LLM."
        is_error = True

    return ChatResponse(
        agent_response=selection.agent_response,
        reasoning=selection.reasoning,
        tool_type=tool_type,
        tool_name=tool_name,
        arguments=selection.arguments,
        execution_output=execution_output,
        is_error=is_error,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_agent_api:app", host="0.0.0.0", port=8002, reload=True)
