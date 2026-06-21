"""
cli_executor.py
===============
Subprocess-based executor for drake CLI commands.

Architecture
------------
The agent selects a CLI tool from cli_tool_registry.py. This module:
  1. Resolves the correct Python executable (project venv → system python).
  2. Builds the full argv list from the tool definition + LLM-supplied arguments.
  3. Runs the command with PYTHONIOENCODING=utf-8 and JSON output mode
     (--json flag) so output is always machine-parseable.
  4. Returns a structured CLIResult with stdout, stderr, returncode, and
     a parsed dict if the JSON was valid.

Why JSON mode?
--------------
The drake CLI supports a global --json flag that strips all Rich colors,
tables, and panels — returning pure JSON to stdout. This lets the agent
re-format and summarise the output cleanly for the user, instead of receiving
raw ANSI escape sequences.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from scripts.cli_tool_registry import ToolDef, get_tool


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Relative to the project root (where start.ps1 lives)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

_VENV_PYTHON_WINDOWS = _PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
_VENV_PYTHON_UNIX = _PROJECT_ROOT / ".venv" / "bin" / "python"

# Timeout for CLI subprocess execution (seconds)
DEFAULT_TIMEOUT = 60


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------
class CLIResult:
    """
    Result container returned by run_cli_tool().

    Attributes
    ----------
    stdout      : Raw captured stdout string.
    stderr      : Raw captured stderr string.
    returncode  : Process exit code (0 = success).
    parsed      : Parsed JSON dict from stdout (None if not valid JSON).
    success     : True when returncode == 0.
    error_msg   : A short human-readable failure reason (empty on success).
    """

    __slots__ = ("stdout", "stderr", "returncode", "parsed", "success", "error_msg")

    def __init__(
        self,
        stdout: str,
        stderr: str,
        returncode: int,
    ) -> None:
        self.stdout = stdout.strip()
        self.stderr = stderr.strip()
        self.returncode = returncode
        self.success = returncode == 0
        self.parsed: Optional[Dict[str, Any]] = None
        self.error_msg = ""

        # Attempt JSON parse
        if self.stdout:
            try:
                self.parsed = json.loads(self.stdout)
            except json.JSONDecodeError:
                # Not JSON — treated as plain text output
                self.parsed = None

        # Build error_msg if failed
        if not self.success:
            if self.stderr:
                # Take first meaningful line from stderr
                first_err = next(
                    (ln for ln in self.stderr.splitlines() if ln.strip()),
                    self.stderr[:200],
                )
                self.error_msg = first_err
            else:
                self.error_msg = f"Process exited with code {returncode}."

    def summary_for_agent(self) -> str:
        """
        Return a clean string the agent can relay to the user.

        Priority: parsed JSON (pretty-printed) > plain stdout > stderr error.
        """
        if self.success:
            if self.parsed is not None:
                return json.dumps(self.parsed, indent=2)
            return self.stdout if self.stdout else "(Command completed with no output.)"
        else:
            parts = [f"[ERROR] Command failed (exit {self.returncode})."]
            if self.error_msg:
                parts.append(self.error_msg)
            if self.stdout:
                parts.append(f"Stdout: {self.stdout[:500]}")
            return "\n".join(parts)


# ---------------------------------------------------------------------------
# Python resolver
# ---------------------------------------------------------------------------
def _resolve_python() -> str:
    """
    Resolve the Python executable to use for CLI invocation.

    Search order:
      1. .venv/Scripts/python.exe  (Windows venv)
      2. .venv/bin/python          (Unix venv)
      3. sys.executable            (current interpreter — may already be in venv)
    """
    if _VENV_PYTHON_WINDOWS.exists():
        return str(_VENV_PYTHON_WINDOWS)
    if _VENV_PYTHON_UNIX.exists():
        return str(_VENV_PYTHON_UNIX)
    return sys.executable


# ---------------------------------------------------------------------------
# Command builder
# ---------------------------------------------------------------------------
def build_command(tool_def: ToolDef, arguments: Dict[str, Any]) -> List[str]:
    """
    Construct the full subprocess argv from a tool definition and LLM arguments.

    Returns a list like:
      ["/path/to/python", "-m", "src.cli.main", "--json",
       "cluster", "run", "--specs", "openapi.json"]

    Argument resolution rules
    -------------------------
    - Positional args: inserted in declaration order directly as bare values.
    - Flagged args (--flag): inserted as ["--flag", "value"] pairs.
    - Bool flags: inserted as bare ["--flag"] if truthy (no value appended).
    - None / missing optional args: omitted entirely.
    """
    python = _resolve_python()

    # Base: python -m src.cli.main --json <subcommand...>
    cmd: List[str] = [python, "-m", "src.cli.main", "--json"] + tool_def["command"]

    positionals: List[str] = []
    flagged: List[str] = []

    for arg_def in tool_def.get("args", []):
        arg_name = arg_def["name"]
        # Normalize LLM key: strip leading dashes, replace hyphens with underscores
        lookup_key = arg_name.lstrip("-").replace("-", "_")

        # Also try the raw name directly (LLM may use different forms)
        value = arguments.get(lookup_key) or arguments.get(arg_name)

        # Skip if not provided and not required
        if value is None:
            if arg_def.get("default") is not None:
                value = arg_def["default"]
            else:
                continue  # omit entirely

        # Positional
        if arg_def.get("positional", False):
            positionals.append(str(value))
            continue

        # Flagged
        flag = arg_def.get("flag", f"--{arg_name.lstrip('-')}")
        arg_type = arg_def.get("type", "str")

        if arg_type == "bool":
            if value and str(value).lower() not in ("false", "0", "no", ""):
                flagged.append(flag)
        else:
            flagged.extend([flag, str(value)])

    # Positionals come before flags in drake's argument parser
    cmd.extend(positionals)
    cmd.extend(flagged)
    return cmd


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run_cli_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    timeout: int = DEFAULT_TIMEOUT,
    cwd: Optional[str] = None,
) -> CLIResult:
    """
    Execute a CLI tool by name with the given arguments.

    Parameters
    ----------
    tool_name   : Exact name from CLI_TOOLS registry.
    arguments   : Dict of argument key→value from the LLM.
    timeout     : Max seconds to wait for the subprocess.
    cwd         : Working directory (defaults to project root).

    Returns
    -------
    CLIResult with stdout, stderr, returncode, and parsed JSON.

    Raises
    ------
    ValueError  : If tool_name is not found in the registry.
    """
    tool_def = get_tool(tool_name)
    if tool_def is None:
        raise ValueError(
            f"CLI tool '{tool_name}' not found in registry. "
            f"Did you mean one of: {', '.join([t for t in dir()])}"
        )

    cmd = build_command(tool_def, arguments)
    working_dir = cwd or str(_PROJECT_ROOT)

    # Inherit environment with UTF-8 encoding enforced
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    try:
        proc = subprocess.run(
            cmd,
            cwd=working_dir,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return CLIResult(
            stdout=proc.stdout,
            stderr=proc.stderr,
            returncode=proc.returncode,
        )
    except subprocess.TimeoutExpired:
        return CLIResult(
            stdout="",
            stderr=f"Command timed out after {timeout} seconds.",
            returncode=124,
        )
    except FileNotFoundError as exc:
        return CLIResult(
            stdout="",
            stderr=f"Python executable not found: {exc}",
            returncode=127,
        )
    except Exception as exc:  # pragma: no cover
        return CLIResult(
            stdout="",
            stderr=f"Unexpected error running CLI: {exc}",
            returncode=1,
        )


# ---------------------------------------------------------------------------
# Validation helper (used by agent before execution)
# ---------------------------------------------------------------------------
def validate_cli_arguments(
    tool_name: str, arguments: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    Validate that all required arguments for a CLI tool are present.

    Returns (True, "OK") on success, or (False, error_message) on failure.
    """
    tool_def = get_tool(tool_name)
    if tool_def is None:
        return False, f"Unknown CLI tool: '{tool_name}'"

    missing = []
    for arg_def in tool_def.get("args", []):
        if not arg_def.get("required", False):
            continue
        arg_name = arg_def["name"]
        lookup_key = arg_name.lstrip("-").replace("-", "_")
        if arguments.get(lookup_key) is None and arguments.get(arg_name) is None:
            missing.append(lookup_key)

    if missing:
        return False, (
            f"Missing required arguments for '{tool_name}': {missing}. "
            f"Please provide values for these fields."
        )
    return True, "OK"
