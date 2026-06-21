"""
interactive_agent.py  (v2 — Dual-Mode: MCP + CLI)
===================================================
Drake AI Agent Terminal powered by Ollama + Model Context Protocol.

Architecture
------------
The agent has TWO namespaces of tools available to the LLM:

  1. MCP WORKFLOW TOOLS
     Registered workflows in the governance DB, exposed via the FastMCP SSE
     proxy server. Used for executing infrastructure operations (firmware
     updates, configuration changes, rollbacks, etc.) against Redfish targets.
     Invoked via: session.call_tool() over SSE.

  2. CLI ADMIN TOOLS
     Drake CLI commands from scripts/cli_tool_registry.py.
     Used for platform management: ingest specs, cluster workflows, approve
     or reject governance decisions, view audit logs, run diagnostics.
     Invoked via: subprocess (scripts/cli_executor.py → drake --json <cmd>).

The LLM (Ollama + instructor) selects tool_type ("mcp" | "cli" | "none")
and the appropriate tool name + arguments from a unified system prompt that
describes both tool sets. Execution is then routed to the correct backend.

Fallback Behaviour
------------------
- If the MCP server is offline, the agent starts in CLI-ONLY mode and notifies
  the user. All CLI tools remain fully available.
- If the LLM selects a tool that doesn't exist, fuzzy matching corrects typos.
- If required arguments are missing, the agent prompts the user interactively.
"""

from __future__ import annotations

import asyncio
import difflib
import json
import os
import sys
import traceback
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Optional imports — fail with helpful messages
# ---------------------------------------------------------------------------
try:
    from openai import AsyncOpenAI
    import instructor
except ImportError:
    print("[FATAL] Missing dependencies. Run: pip install openai instructor")
    sys.exit(1)

try:
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False

# ---------------------------------------------------------------------------
# Project root path adjustment (so scripts/ can import from src/)
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPTS_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from scripts.cli_tool_registry import CLI_TOOLS, as_llm_schema, get_tool
from scripts.cli_executor import run_cli_tool, validate_cli_arguments

# ---------------------------------------------------------------------------
# Configuration (from .env)
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434") + "/v1"
MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:14b")
MCP_PROXY_URL = os.getenv("MCP_PROXY_URL", "http://127.0.0.1:8001/mcp/sse")

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ToolSelection(BaseModel):
    tool_type: str = Field(
        ...,
        description=(
            "MUST be exactly one of: 'mcp', 'cli', 'none'. "
            "Use 'mcp' for infrastructure workflow execution tools. "
            "Use 'cli' for platform administration (cluster, governance, audit, diagnostics). "
            "Use 'none' if no tool is needed and you are responding conversationally."
        ),
    )
    selected_tool_name: str = Field(
        ...,
        description=(
            "The exact registered name of the tool to use, or 'NONE' if tool_type is 'none'. "
            "Must be an exact match from the tool lists provided."
        ),
    )
    arguments: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Arguments to pass to the selected tool. Keys must exactly match the tool's "
            "schema properties. Pass an empty dict {} if the tool takes no arguments."
        ),
    )
    reasoning: str = Field(
        ...,
        description="Brief internal reasoning: why this tool was chosen and how arguments were resolved.",
    )
    agent_response: str = Field(
        ...,
        description="Natural language response to communicate to the user about what you are doing.",
    )


# ---------------------------------------------------------------------------
# MCP tool argument validation
# ---------------------------------------------------------------------------

def validate_mcp_arguments(
    tool_name: str, arguments: Dict[str, Any], tools: List[dict]
) -> tuple[bool, str]:
    """Validate LLM-selected arguments against the MCP tool's actual schema."""
    tool = next((t for t in tools if t["name"] == tool_name), None)
    if not tool:
        return False, f"MCP tool '{tool_name}' not found in registry."

    schema = tool.get("inputSchema", {})
    valid_props = set(schema.get("properties", {}).keys())
    required_props = set(schema.get("required", []))
    given_props = set(arguments.keys())

    unexpected = given_props - valid_props
    if unexpected:
        return False, (
            f"Invalid arguments {unexpected} for MCP tool '{tool_name}'.\n"
            f"  Valid: {valid_props or '(none)'}\n"
            f"  Required: {required_props or '(none)'}"
        )

    missing = required_props - given_props
    if missing:
        return False, (
            f"Missing required arguments {missing} for MCP tool '{tool_name}'.\n"
            f"  Required: {required_props}"
        )

    return True, "OK"


# ---------------------------------------------------------------------------
# LLM decision function
# ---------------------------------------------------------------------------

async def decide_tool_with_llm(
    client: instructor.AsyncInstructor,
    prompt: str,
    mcp_tools: List[dict],
    cli_tools: List[dict],
) -> ToolSelection:
    """
    Ask Ollama (via instructor) to decide which tool to invoke and with what arguments.

    The system prompt presents both MCP workflow tools and CLI admin tools,
    instructing the LLM to set tool_type accordingly.
    """
    print(f"  [Agent] Consulting LLM ({MODEL_NAME} @ {OLLAMA_BASE_URL})...")

    # --- Format MCP tools section ---
    mcp_names = [t["name"] for t in mcp_tools]
    mcp_section_lines = []
    for t in mcp_tools:
        schema = json.loads(json.dumps(t["inputSchema"]))
        # Strip override_policy — internal field not for LLM
        if "properties" in schema and "override_policy" in schema["properties"]:
            schema["properties"].pop("override_policy")
        mcp_section_lines.append(
            f"  - {t['name']}: {t['description']}\n    Schema: {json.dumps(schema)}"
        )
    mcp_section = "\n".join(mcp_section_lines) if mcp_section_lines else "  (none available — MCP server offline)"

    # --- Format CLI tools section ---
    cli_names = [t["name"] for t in cli_tools]
    cli_section_lines = []
    for t in cli_tools:
        cli_section_lines.append(
            f"  - {t['name']}: {t['description']}\n    Schema: {json.dumps(t['inputSchema'])}"
        )
    cli_section = "\n".join(cli_section_lines)

    system_prompt = (
        "You are an advanced AI Infrastructure Agent for Dell Enterprise systems.\n"
        "You have TWO categories of tools:\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "CATEGORY 1 — MCP WORKFLOW TOOLS (tool_type = 'mcp')\n"
        "Use these to EXECUTE infrastructure operations (firmware, BIOS, rollbacks, etc.)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{mcp_section}\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "CATEGORY 2 — CLI ADMIN TOOLS (tool_type = 'cli')\n"
        "Use these for platform management: clustering, governance, audit, diagnostics.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{cli_section}\n\n"

        "RULES YOU MUST FOLLOW:\n"
        f"1. tool_type MUST be exactly 'mcp', 'cli', or 'none'.\n"
        f"2. For MCP tools, selected_tool_name must be one of: {mcp_names}.\n"
        f"3. For CLI tools, selected_tool_name must be one of: {cli_names}.\n"
        "4. Arguments must ONLY contain keys that exist in the chosen tool's schema. "
        "If a tool has no properties, pass an empty dict {}.\n"
        "5. Choose 'mcp' for actual infrastructure execution (firmware, power, config changes).\n"
        "6. Choose 'cli' for admin tasks (ingest specs, list workflows, approve, diagnose, audit).\n"
        "7. Choose 'none' if the question is conversational and no tool is needed.\n"
        "8. Always verify your argument keys against the schema before responding.\n"
    )

    selection = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        response_model=ToolSelection,
        max_retries=3,
    )
    return selection


# ---------------------------------------------------------------------------
# Fuzzy name correction
# ---------------------------------------------------------------------------

def _fuzzy_correct_name(selected: str, valid_names: List[str]) -> Optional[str]:
    """Return the closest matching name above 0.75 cutoff, or None."""
    matches = difflib.get_close_matches(selected, valid_names, n=1, cutoff=0.75)
    return matches[0] if matches else None


# ---------------------------------------------------------------------------
# Interactive prompt for missing required args
# ---------------------------------------------------------------------------

def _fill_missing_args(
    arguments: Dict[str, Any],
    required_keys: List[str],
    tool_name: str,
) -> Dict[str, Any]:
    """Prompt the user interactively for any missing required arguments."""
    filled = dict(arguments)
    for key in required_keys:
        if filled.get(key) is None:
            val = input(f"  [INPUT] Please provide value for '{key}' (required by '{tool_name}'): ").strip()
            if val:
                filled[key] = val
    return filled


# ---------------------------------------------------------------------------
# CLI execution handler
# ---------------------------------------------------------------------------

def execute_cli_tool_and_display(selection: ToolSelection) -> None:
    """Run the chosen CLI tool and print results to the terminal."""
    tool_name = selection.selected_tool_name
    arguments = selection.arguments

    # Validate args
    valid, msg = validate_cli_arguments(tool_name, arguments)
    if not valid:
        # Try to fill missing required args interactively
        tool_def = get_tool(tool_name)
        if tool_def:
            required_keys = [
                a["name"].lstrip("-").replace("-", "_")
                for a in tool_def.get("args", [])
                if a.get("required", False)
            ]
            missing_keys = [
                k for k in required_keys
                if arguments.get(k) is None and arguments.get(a_name := f"--{k}") is None
            ]
            if missing_keys:
                print(f"\n  [SYSTEM] Missing required arguments: {missing_keys}")
                arguments = _fill_missing_args(arguments, missing_keys, tool_name)
                valid, msg = validate_cli_arguments(tool_name, arguments)

    if not valid:
        print(f"\n  [VALIDATION FAILED] {msg}")
        print("  [SYSTEM] Skipping CLI execution.")
        return

    print(f"\n[SYSTEM] Executing CLI tool '{tool_name}'...")
    print(f"  - Arguments: {json.dumps(arguments, indent=2)}")
    print("  - Mode: JSON (machine-readable output)")
    print()

    result = run_cli_tool(tool_name, arguments)

    if result.success:
        print("[SYSTEM] CLI Execution Complete:")
        print("─" * 70)
        if result.parsed is not None:
            # Pretty-print JSON with clear formatting
            _display_parsed_json(result.parsed, tool_name)
        else:
            # Plain text output (e.g. success messages)
            print(result.stdout if result.stdout else "(No output)")
        print("─" * 70)
    else:
        print(f"[ERROR] CLI command failed (exit code {result.returncode}):")
        print("─" * 70)
        if result.stderr:
            print(f"  Stderr: {result.stderr[:1000]}")
        if result.stdout:
            print(f"  Stdout: {result.stdout[:500]}")
        print("─" * 70)


def _display_parsed_json(data: Any, tool_name: str) -> None:
    """
    Display parsed JSON in a readable format.
    Handles lists (tables of items) and dicts differently for clarity.
    """
    if isinstance(data, list):
        if not data:
            print("  (empty list — no results found)")
            return
        print(f"  Found {len(data)} result(s):\n")
        for i, item in enumerate(data[:20], 1):   # cap at 20 for readability
            if isinstance(item, dict):
                print(f"  [{i}]")
                for k, v in item.items():
                    print(f"      {k}: {v}")
                print()
            else:
                print(f"  [{i}] {item}")
        if len(data) > 20:
            print(f"  ... and {len(data) - 20} more items.")
    elif isinstance(data, dict):
        # Check for error key
        if "error" in data:
            print(f"  [ERROR] {data['error']}")
            if "details" in data:
                print(f"  Details: {data['details']}")
            return
        # Flat dict — print as key: value table
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                print(f"  {k}:")
                print(f"    {json.dumps(v, indent=4)}")
            else:
                print(f"  {k}: {v}")
    else:
        print(str(data))


# ---------------------------------------------------------------------------
# MCP execution handler (existing path, preserved)
# ---------------------------------------------------------------------------

async def execute_mcp_tool_and_display(
    session: "ClientSession",
    selection: ToolSelection,
    available_mcp_tools: List[dict],
) -> None:
    """Execute the chosen MCP tool via the SSE proxy session."""
    tool_name = selection.selected_tool_name
    arguments = selection.arguments

    # Validate
    valid, msg = validate_mcp_arguments(tool_name, arguments, available_mcp_tools)
    if not valid:
        # Fill missing required
        schema = next((t["inputSchema"] for t in available_mcp_tools if t["name"] == tool_name), {})
        required = list(schema.get("required", []))
        missing_required = [k for k in required if k not in arguments and k != "override_policy"]
        if missing_required:
            print(f"\n  [SYSTEM] Missing required arguments: {missing_required}")
            for prop in missing_required:
                val = input(f"  Please provide value for '{prop}': ").strip()
                if val:
                    arguments[prop] = val
            valid, msg = validate_mcp_arguments(tool_name, arguments, available_mcp_tools)

    if not valid:
        print(f"\n  [VALIDATION FAILED] {msg}")
        print("  [SYSTEM] Skipping MCP execution.")
        return

    print(f"\n[SYSTEM] Executing MCP tool '{tool_name}'...")
    print(f"  - Parameters: {json.dumps(arguments, indent=2)}")

    result = await session.call_tool(tool_name, arguments=arguments)

    # Handle policy block
    is_blocked = any(
        c.type == "text" and "Execution blocked: confidence score" in c.text
        for c in result.content
    )

    if is_blocked:
        print("\n  [SYSTEM] Proxy blocked execution due to low confidence score.")
        override = input("  Override and execute anyway? (yes/no): ").strip().lower()
        if override in ("y", "yes"):
            arguments["override_policy"] = "WARN_ONLY"
            print(f"\n[SYSTEM] Re-executing '{tool_name}' with override...")
            result = await session.call_tool(tool_name, arguments=arguments)
        else:
            print("  [SYSTEM] Execution aborted by user.")
            return

    print("\n[SYSTEM] MCP Tool Execution Complete:")
    print("─" * 70)
    for content in result.content:
        if content.type == "text":
            try:
                parsed = json.loads(content.text)
                print(json.dumps(parsed, indent=2))
            except Exception:
                print(content.text)
        else:
            print(f"  [{content.type}]: {content}")
    print("─" * 70)


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

def _print_banner(mcp_online: bool, mcp_tool_count: int) -> None:
    print("=" * 70)
    print("        DRAKE — DUAL-MODE AI AGENT TERMINAL (v2)")
    print("=" * 70)
    print(f"  LLM Backend  : Ollama ({MODEL_NAME})")
    print(f"  MCP Proxy    : {'ONLINE — ' + str(mcp_tool_count) + ' workflow tools' if mcp_online else 'OFFLINE — CLI-only mode'}")
    print(f"  CLI Tools    : {len(CLI_TOOLS)} admin commands available")
    print()
    print("  Type your request in natural language.")
    print("  Examples:")
    print("    > show me pending workflows")
    print("    > run the clustering pipeline on openapi.json")
    print("    > validate workflow wf_abc against 192.168.1.50")
    print("    > what is the platform health status?")
    print("    > show audit log")
    print()
    print("  Type 'exit' or 'quit' to leave.")
    print("=" * 70)


# ---------------------------------------------------------------------------
# Main interactive loop
# ---------------------------------------------------------------------------

async def interactive_loop() -> None:
    # Build instructor client pointing to Ollama
    client = instructor.from_openai(
        AsyncOpenAI(
            base_url=OLLAMA_BASE_URL,
            api_key="ollama",
        ),
        mode=instructor.Mode.JSON,
    )

    # CLI tools schema (always available)
    cli_tools_schema = as_llm_schema()

    # -----------------------------------------------------------------------
    # Try connecting to MCP proxy
    # -----------------------------------------------------------------------
    mcp_online = False
    available_mcp_tools: List[dict] = []
    mcp_session: Optional["ClientSession"] = None

    if not _MCP_AVAILABLE:
        print("[SYSTEM] mcp package not found. Starting in CLI-only mode.")
        _print_banner(mcp_online, len(available_mcp_tools))
        # Print CLI tool summary
        print(f"\n[SYSTEM] Available CLI tools ({len(CLI_TOOLS)}):\n")
        for i, t in enumerate(CLI_TOOLS, 1):
            params = list(t.get("args", []))
            param_str = ", ".join(
                a["name"].lstrip("-").replace("-", "_") for a in params
            ) if params else "(no params)"
            print(f"  {i:3d}. {t['name']:<45s} [{param_str}]")
        print()
        await _run_prompt_loop(client, cli_tools_schema, mcp_session, available_mcp_tools, mcp_online)
        return

    from contextlib import AsyncExitStack
    async with AsyncExitStack() as stack:
        print(f"[SYSTEM] Attempting connection to FastMCP proxy ({MCP_PROXY_URL})...")
        try:
            # We use AsyncExitStack to ensure proper __aexit__ execution
            # even if interrupted by KeyboardInterrupt, avoiding anyio cancel scope issues.
            _sse_ctx = sse_client(MCP_PROXY_URL)
            if hasattr(asyncio, "timeout"):
                async with asyncio.timeout(5):
                    _streams = await stack.enter_async_context(_sse_ctx)
            else:
                _streams = await stack.enter_async_context(_sse_ctx)
                
            _read, _write = _streams
            _session_ctx = ClientSession(_read, _write)
            
            if hasattr(asyncio, "timeout"):
                async with asyncio.timeout(5):
                    mcp_session = await stack.enter_async_context(_session_ctx)
                    await mcp_session.initialize()
            else:
                mcp_session = await stack.enter_async_context(_session_ctx)
                await asyncio.wait_for(mcp_session.initialize(), timeout=5)

            tools_response = await mcp_session.list_tools()
            for t in tools_response.tools:
                available_mcp_tools.append({
                    "name": t.name,
                    "description": t.description or "No description",
                    "inputSchema": t.inputSchema,
                })
            mcp_online = True
            print(f"  -> Connected. {len(available_mcp_tools)} MCP workflow tools loaded.")

        except Exception as e:
            if isinstance(e, (asyncio.TimeoutError, TimeoutError)):
                print("  -> MCP connection timed out. Starting in CLI-only mode.")
            else:
                print(f"  -> MCP unavailable ({type(e).__name__}: {e}). Starting in CLI-only mode.")

        _print_banner(mcp_online, len(available_mcp_tools))

        # Print CLI tool summary
        print(f"\n[SYSTEM] Available CLI tools ({len(CLI_TOOLS)}):\n")
        for i, t in enumerate(CLI_TOOLS, 1):
            params = list(t.get("args", []))
            param_str = ", ".join(
                a["name"].lstrip("-").replace("-", "_") for a in params
            ) if params else "(no params)"
            print(f"  {i:3d}. {t['name']:<45s} [{param_str}]")

        if mcp_online:
            print(f"\n[SYSTEM] Available MCP workflow tools ({len(available_mcp_tools)}):\n")
            for i, t in enumerate(available_mcp_tools, 1):
                params = list(t["inputSchema"].get("properties", {}).keys())
                param_str = ", ".join(params) if params else "(no params)"
                print(f"  {i:3d}. {t['name']:<45s} [{param_str}]")
        print()

        await _run_prompt_loop(client, cli_tools_schema, mcp_session, available_mcp_tools, mcp_online)

async def _run_prompt_loop(client, cli_tools_schema, mcp_session, available_mcp_tools, mcp_online):

    # -----------------------------------------------------------------------
    # Main prompt loop
    # -----------------------------------------------------------------------
    while True:
        try:
            user_prompt = input("\n[USER]> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nShutting down AI Agent terminal...")
            break

        if user_prompt.lower() in ("exit", "quit", "q"):
            print("\nShutting down AI Agent terminal...")
            break

        if not user_prompt:
            continue

        print("\n[SYSTEM] Agent is thinking...\n")

        try:
            selection = await decide_tool_with_llm(
                client, user_prompt, available_mcp_tools, cli_tools_schema
            )

            print(f"\n[AGENT]> {selection.agent_response}")
            if selection.reasoning:
                print(f"  [Internal Reasoning] {selection.reasoning}")

            tool_type = selection.tool_type.lower().strip()
            tool_name = selection.selected_tool_name.strip()

            # ── NONE: conversational, no tool needed ─────────────────────
            if tool_type == "none" or tool_name.upper() == "NONE":
                print("\n[SYSTEM] No tool invoked for this prompt.")
                continue

            # ── CLI TOOL ──────────────────────────────────────────────────
            if tool_type == "cli":
                # Fuzzy correct name
                cli_names = [t["name"] for t in CLI_TOOLS]
                if tool_name not in cli_names:
                    corrected = _fuzzy_correct_name(tool_name, cli_names)
                    if corrected:
                        print(f"  [SYSTEM] Auto-correcting: '{tool_name}' -> '{corrected}'")
                        selection.selected_tool_name = corrected
                        tool_name = corrected
                    else:
                        print(f"  [ERROR] CLI tool '{tool_name}' not found. Available:")
                        for n in cli_names:
                            print(f"    - {n}")
                        continue

                execute_cli_tool_and_display(selection)
                continue

            # ── MCP TOOL ──────────────────────────────────────────────────
            if tool_type == "mcp":
                if not mcp_online or mcp_session is None:
                    print(
                        "\n  [WARNING] MCP proxy is offline. Cannot execute MCP tools.\n"
                        "  Suggestion: Start the backend with 'drake server start' and restart the agent."
                    )
                    continue

                # Fuzzy correct name
                mcp_names = [t["name"] for t in available_mcp_tools]
                if tool_name not in mcp_names:
                    corrected = _fuzzy_correct_name(tool_name, mcp_names)
                    if corrected:
                        print(f"  [SYSTEM] Auto-correcting: '{tool_name}' -> '{corrected}'")
                        selection.selected_tool_name = corrected
                        tool_name = corrected
                    else:
                        print(f"  [ERROR] MCP tool '{tool_name}' not found. Available:")
                        for n in mcp_names:
                            print(f"    - {n}")
                        continue

                await execute_mcp_tool_and_display(mcp_session, selection, available_mcp_tools)
                continue

            # ── Unknown tool_type ─────────────────────────────────────────
            print(
                f"\n  [ERROR] LLM returned unknown tool_type='{tool_type}'. "
                "Expected 'mcp', 'cli', or 'none'. Skipping."
            )

        except KeyboardInterrupt:
            print("\n\n[SYSTEM] Interrupted. Type 'exit' to quit.")
        except Exception as llm_err:
            print(f"\n[ERROR] LLM error: {llm_err}")
            if os.getenv("DRAKE_DEBUG"):
                traceback.print_exc()
            print("  Ensure Ollama is running and the model is available.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(interactive_loop())
