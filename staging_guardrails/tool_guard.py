"""
Tool Guard

Inspects LLM output for embedded tool-invocation instructions and validates them
against an allowlist.  Blocks or redacts instructions that:

  - Invoke tools not on the tenant allowlist
  - Pass arguments matching dangerous patterns (path traversal, shell injection, etc.)
  - Request privileged or system-level operations
  - Contain encoded / obfuscated payloads

The guard operates entirely on text – it does *not* execute any tool call.

Typical output formats handled:
  - JSON blobs: {"tool": "bash", "args": {"cmd": "..."}}
  - Markdown code fences tagged ``tool_call`` or ``function_call``
  - Plain-text invocations: ``run_command("rm -rf /")``
  - OpenAI-style function call syntax
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------

#: Tools that are always allowed regardless of tenant configuration.
DEFAULT_SAFE_TOOLS: Set[str] = {
    "search_web",
    "retrieve_document",
    "calculator",
    "get_weather",
    "read_file",
    "list_files",
    "send_message",
    "get_time",
}

#: Tools that are never allowed (universal blocklist).
BLOCKED_TOOLS: Set[str] = {
    "bash",
    "shell",
    "exec",
    "run_command",
    "system",
    "eval",
    "python",
    "powershell",
    "cmd",
    "terminal",
    "subprocess",
    "os_command",
    "code_exec",
    "execute_code",
    "run_code",
    "file_delete",
    "file_write",
    "db_execute",
    "sql_query",
    "network_scan",
    "port_scan",
}

# Argument patterns that are suspicious regardless of tool
_DANGEROUS_ARG_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("path_traversal",      re.compile(r"\.\./|\.\.\\|%2e%2e", re.IGNORECASE)),
    ("shell_injection",     re.compile(r"[;&|`$(){}\[\]]")),
    ("null_byte",           re.compile(r"\\x00|\x00|%00")),
    ("cmd_substitution",    re.compile(r"\$\(|`[^`]+`")),
    ("pipe_redirection",    re.compile(r"\s[|><&]\s")),
    ("rm_rf",               re.compile(r"rm\s+-[rf]|del\s+/[fqs]", re.IGNORECASE)),
    ("encoded_payload",     re.compile(r"(?:[A-Za-z0-9+/]{40,}={0,2})")),  # long base64
    ("url_injection",       re.compile(r"(file|dict|ftp|gopher)://", re.IGNORECASE)),
    ("ssrf_hint",           re.compile(r"(169\.254\.|127\.|0\.0\.0\.0|localhost)", re.IGNORECASE)),
    ("privilege_escalation",re.compile(r"(sudo|su\s+-|runas|chmod\s+[0-7]*7[0-7])", re.IGNORECASE)),
]

# Regex patterns to detect candidate tool-call regions in text
_TOOL_CALL_PATTERNS: List[re.Pattern] = [
    # Markdown code block tagged as function/tool call
    re.compile(r'```(?:tool_call|function_call|json)\s*\n?(.*?)```', re.DOTALL | re.IGNORECASE),
    # Plain text invocations: tool_name(arg) or tool_name("arg")
    re.compile(r'\b([a-z][a-z0-9_]+)\s*\(\s*(?:["\']([^"\']{0,200})["\']|({[^}]{0,400}})?)\s*\)'),
]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ToolGuardResult:
    safe: bool
    blocked_tools: List[str] = field(default_factory=list)
    suspicious_args: List[str] = field(default_factory=list)
    tool_calls_found: List[Dict[str, Any]] = field(default_factory=list)
    risk_contribution: float = 0.0        # 0–1, added to overall risk

    def to_dict(self) -> dict:
        return {
            "safe": self.safe,
            "blocked_tools": self.blocked_tools,
            "suspicious_args": self.suspicious_args,
            "tool_calls_detected": len(self.tool_calls_found),
            "risk_contribution": round(self.risk_contribution, 4),
        }


# ---------------------------------------------------------------------------
# ToolGuard
# ---------------------------------------------------------------------------

class ToolGuard:
    """
    Validates tool invocation instructions embedded in LLM outputs.

    Usage::

        guard = ToolGuard(allowed_tools={"search_web", "calculator"})
        result = guard.inspect(llm_output)
        if not result.safe:
            # sanitize or block
    """

    def __init__(
        self,
        allowed_tools: Optional[Set[str]] = None,
        strict_mode: bool = False,
    ) -> None:
        """
        Args:
            allowed_tools: Explicit set of permitted tool names.
                           If None, DEFAULT_SAFE_TOOLS is used.
            strict_mode:   Treat *any* detected tool call as suspicious if
                           the tool is not in the explicit allowlist.
        """
        self.allowed_tools: Set[str] = (
            allowed_tools if allowed_tools is not None else set(DEFAULT_SAFE_TOOLS)
        )
        self.strict_mode = strict_mode

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def inspect(self, text: str) -> ToolGuardResult:
        """
        Scan ``text`` for tool invocations and validate each one.

        Returns:
            ToolGuardResult – ``safe=True`` means no blocked calls found.
        """
        t0 = time.perf_counter()

        tool_calls = self._extract_tool_calls(text)
        blocked: List[str] = []
        suspicious_args: List[str] = []
        risk = 0.0

        for call in tool_calls:
            tool_name = call.get("tool_name", "").lower().strip()
            args_obj  = call.get("args", {})
            # Serialise only for passing to _validate_args
            args_text = json.dumps(args_obj) if isinstance(args_obj, dict) else str(args_obj)

            # Check blocklist
            if tool_name in BLOCKED_TOOLS:
                blocked.append(tool_name)
                risk = min(1.0, risk + 0.70)
                continue

            # Check not on allowlist
            if self.strict_mode and tool_name not in self.allowed_tools:
                blocked.append(tool_name)
                risk = min(1.0, risk + 0.50)
                continue

            # Validate arguments
            arg_issues = self._validate_args(args_text)
            if arg_issues:
                suspicious_args.extend(arg_issues)
                risk = min(1.0, risk + 0.35 * len(arg_issues))

        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.debug(
            f"ToolGuard: {len(tool_calls)} calls found, {len(blocked)} blocked  ({elapsed_ms:.1f}ms)"
        )

        safe = not (blocked or suspicious_args)
        return ToolGuardResult(
            safe=safe,
            blocked_tools=list(dict.fromkeys(blocked)),
            suspicious_args=list(dict.fromkeys(suspicious_args)),
            tool_calls_found=tool_calls,
            risk_contribution=min(1.0, risk),
        )

    # ------------------------------------------------------------------
    # JSON brace-matching extractor
    # ------------------------------------------------------------------

    @staticmethod
    def _find_json_blobs(text: str) -> List[str]:
        """
        Extract all top-level JSON object strings from ``text`` using a
        stack-based brace parser.  Handles arbitrary nesting depth.
        """
        blobs: List[str] = []
        depth = 0
        start = -1
        in_string = False
        escape = False

        for i, ch in enumerate(text):
            if escape:
                escape = False
                continue
            if ch == '\\' and in_string:
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start != -1:
                    blobs.append(text[start: i + 1])
                    start = -1

        return blobs

    @staticmethod
    def _parse_json_blob(blob: str) -> Optional[Dict[str, Any]]:
        """Try to parse a JSON blob and extract tool invocation details."""
        try:
            data = json.loads(blob)
        except (json.JSONDecodeError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        tool_name = (
            data.get("tool") or data.get("function") or
            data.get("name") or data.get("tool_name") or ""
        )
        if not tool_name:
            return None
        return {"tool_name": str(tool_name).lower(), "args": data, "raw": blob[:200]}

    # ------------------------------------------------------------------
    # Regex-based extraction
    # ------------------------------------------------------------------

    def _extract_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """Pull all candidate tool invocations out of ``text``."""
        calls: List[Dict[str, Any]] = []

        # Primary: brace-matched JSON blobs (handles nested structures)
        for blob in self._find_json_blobs(text):
            call = self._parse_json_blob(blob)
            if call:
                calls.append(call)

        # Secondary: regex-based patterns (fenced blocks, function calls)
        for pat in _TOOL_CALL_PATTERNS:
            for match in pat.finditer(text):
                call = self._parse_match(match, pat.pattern)
                if call:
                    calls.append(call)

        # Deduplicate by tool_name + raw representation
        seen: Set[str] = set()
        unique: List[Dict[str, Any]] = []
        for c in calls:
            key = f"{c.get('tool_name', '')}:{str(c.get('args', ''))[:60]}"
            if key not in seen:
                seen.add(key)
                unique.append(c)

        return unique

    def _parse_match(self, match: re.Match, pattern_source: str) -> Optional[Dict[str, Any]]:
        """Try to extract a structured call from a regex match."""
        raw = match.group(0)

        # Attempt JSON parse first
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                tool_name = (
                    data.get("tool") or data.get("function") or
                    data.get("name") or data.get("tool_name") or ""
                )
                return {"tool_name": str(tool_name).lower(), "args": data, "raw": raw[:200]}
        except (json.JSONDecodeError, ValueError):
            pass

        # Try to parse fenced code block content
        groups = match.groups()
        if groups:
            for grp in groups:
                if grp and len(grp) > 2:
                    try:
                        data = json.loads(grp.strip())
                        if isinstance(data, dict):
                            tool_name = (
                                data.get("tool") or data.get("function") or
                                data.get("name") or ""
                            )
                            return {"tool_name": str(tool_name).lower(), "args": data, "raw": raw[:200]}
                    except (json.JSONDecodeError, ValueError):
                        pass
                    # Plain text function call: function_name(arg)
                    if re.match(r'^[a-z][a-z0-9_]+$', grp.strip(), re.IGNORECASE):
                        return {"tool_name": grp.strip().lower(), "args": {}, "raw": raw[:200]}

        # Last resort – grab first group as function name
        if groups and groups[0]:
            name_candidate = groups[0].strip()
            if re.match(r'^[a-z][a-z0-9_]+$', name_candidate, re.IGNORECASE):
                return {"tool_name": name_candidate.lower(), "args": {}, "raw": raw[:200]}

        return None

    # ------------------------------------------------------------------
    # Argument validation
    # ------------------------------------------------------------------

    def _validate_args(self, args_text: str) -> List[str]:
        """
        Check argument VALUES for dangerous patterns.

        We inspect only the string values extracted from the serialised args
        so that JSON structural characters ({, }, [, ]) do not produce false
        positives.
        """
        # Extract string values from JSON if possible, else fall back to raw text
        value_texts: List[str] = []
        try:
            data = json.loads(args_text)
            if isinstance(data, dict):
                value_texts = self._collect_string_values(data)
        except (json.JSONDecodeError, ValueError):
            pass

        # Fall back: use the whole args_text if no values extracted
        if not value_texts:
            value_texts = [args_text]

        issues: List[str] = []
        for value in value_texts:
            for tag, pat in _DANGEROUS_ARG_PATTERNS:
                if pat.search(value):
                    issues.append(f"suspicious_arg:{tag}")

        return list(dict.fromkeys(issues))  # deduplicate, order-preserving

    @staticmethod
    def _collect_string_values(obj: Any, depth: int = 0) -> List[str]:
        """Recursively collect all string values from a dict/list structure."""
        if depth > 6:
            return []
        results: List[str] = []
        if isinstance(obj, str):
            results.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                results.extend(ToolGuard._collect_string_values(v, depth + 1))
        elif isinstance(obj, list):
            for item in obj:
                results.extend(ToolGuard._collect_string_values(item, depth + 1))
        return results
