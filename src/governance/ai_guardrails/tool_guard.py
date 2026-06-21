"""
Tool Guard

Inspects LLM output for embedded tool-invocation instructions and validates them
against an allowlist.  Blocks or redacts instructions that:
  - Invoke tools not on the tenant allowlist
  - Pass arguments matching dangerous patterns (path traversal, shell injection, etc.)
  - Request privileged or system-level operations
  - Contain encoded / obfuscated payloads
"""
from __future__ import annotations

import json
import logging
import re
import time
import base64
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml
from pathlib import Path

def _load_gov_config() -> Dict[str, Any]:
    try:
        path = Path(__file__).resolve().parent.parent.parent / "config" / "governance_config.yaml"
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

logger = logging.getLogger(__name__)

# Fallbacks in case config fails
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

BLOCKED_TOOLS: Set[str] = {
    "bash", "shell", "exec", "run_command", "system", "eval", "python", 
    "powershell", "cmd", "terminal", "subprocess", "os_command", "code_exec", 
    "execute_code", "run_code", "file_delete", "file_write", "db_execute", 
    "sql_query", "network_scan", "port_scan"
}

_DANGEROUS_ARG_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("path_traversal",      re.compile(r"\.\./|\.\.\\|%2e%2e", re.IGNORECASE)),
    ("shell_injection",     re.compile(r"[;&|`$(){}\[\]]")),
    ("null_byte",           re.compile(r"\\x00|\x00|%00")),
    ("cmd_substitution",    re.compile(r"\$\(|`[^`]+`")),
    ("pipe_redirection",    re.compile(r"\s[|><&]\s")),
    ("rm_rf",               re.compile(r"rm\s+-[rf]|del\s+/[fqs]", re.IGNORECASE)),
    ("encoded_payload",     re.compile(r"(?:[A-Za-z0-9+/]{40,}={0,2})")),
    ("url_injection",       re.compile(r"(file|dict|ftp|gopher)://", re.IGNORECASE)),
    ("ssrf_hint",           re.compile(r"(169\.254\.|127\.|0\.0\.0\.0|localhost)", re.IGNORECASE)),
    ("privilege_escalation",re.compile(r"(sudo|su\s+-|runas|chmod\s+[0-7]*7[0-7])", re.IGNORECASE)),
]

_TOOL_CALL_PATTERNS: List[re.Pattern] = [
    re.compile(r'```(?:tool_call|function_call|json)\s*\n?(.*?)```', re.DOTALL | re.IGNORECASE),
    re.compile(r'\b([a-z][a-z0-9_]+)\s*\(\s*(?:["\']([^"\']{0,200})["\']|({[^}]{0,400}})?)\s*\)'),
]

@dataclass
class ToolGuardResult:
    safe: bool
    blocked_tools: List[str] = field(default_factory=list)
    suspicious_args: List[str] = field(default_factory=list)
    tool_calls_found: List[Dict[str, Any]] = field(default_factory=list)
    risk_contribution: float = 0.0

    def to_dict(self) -> dict:
        return {
            "safe": self.safe,
            "blocked_tools": self.blocked_tools,
            "suspicious_args": self.suspicious_args,
            "tool_calls_detected": len(self.tool_calls_found),
            "risk_contribution": round(self.risk_contribution, 4),
        }

class ToolGuard:
    """
    Validates tool invocation instructions embedded in LLM outputs.
    """

    def __init__(
        self,
        allowed_tools: Optional[Set[str]] = None,
        strict_mode: bool = False,
    ) -> None:
        self.gov_config = _load_gov_config()
        self.tool_guard_cfg = self.gov_config.get("tool_guard", {})
        
        cfg_safe_tools = self.tool_guard_cfg.get("default_safe_tools")
        self.allowed_tools: Set[str] = (
            allowed_tools if allowed_tools is not None 
            else (set(cfg_safe_tools) if cfg_safe_tools else set(DEFAULT_SAFE_TOOLS))
        )
        
        cfg_blocked_tools = self.tool_guard_cfg.get("blocked_tools")
        self.blocked_tools: Set[str] = set(cfg_blocked_tools) if cfg_blocked_tools else BLOCKED_TOOLS
        
        self.strict_mode = strict_mode

    def inspect(self, text: str) -> ToolGuardResult:
        """
        Scan `text` for tool invocations and validate each one.
        """
        t0 = time.perf_counter()

        tool_calls = self._extract_tool_calls(text)
        blocked: List[str] = []
        suspicious_args: List[str] = []
        risk = 0.0

        for call in tool_calls:
            tool_name = call.get("tool_name", "").lower().strip()
            args_obj  = call.get("args", {})
            args_text = json.dumps(args_obj) if isinstance(args_obj, dict) else str(args_obj)

            if tool_name in self.blocked_tools:
                blocked.append(tool_name)
                risk = min(1.0, risk + self.tool_guard_cfg.get("blocked_tool_risk", 0.70))
                continue

            if self.strict_mode and tool_name not in self.allowed_tools:
                blocked.append(tool_name)
                risk = min(1.0, risk + self.tool_guard_cfg.get("unallowed_tool_risk", 0.50))
                continue

            arg_issues = self._validate_args(args_text)
            if arg_issues:
                suspicious_args.extend(arg_issues)
                risk = min(1.0, risk + self.tool_guard_cfg.get("suspicious_arg_risk_coeff", 0.35) * len(arg_issues))

        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.debug(
            f"ToolGuard: {len(tool_calls)} calls found, {len(blocked)} blocked  ({elapsed_ms:.1f}ms)"
        )

        safe = not (blocked or suspicious_args)
        if not safe:
            logger.warning(f"ToolGuard Violation: Blocked Tools: {blocked}, Suspicious Args: {suspicious_args}")

        return ToolGuardResult(
            safe=safe,
            blocked_tools=list(dict.fromkeys(blocked)),
            suspicious_args=list(dict.fromkeys(suspicious_args)),
            tool_calls_found=tool_calls,
            risk_contribution=min(1.0, risk),
        )

    @staticmethod
    def _find_json_blobs(text: str) -> List[str]:
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

    def _extract_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        calls: List[Dict[str, Any]] = []

        for blob in self._find_json_blobs(text):
            call = self._parse_json_blob(blob)
            if call:
                calls.append(call)

        for pat in _TOOL_CALL_PATTERNS:
            for match in pat.finditer(text):
                call = self._parse_match(match, pat.pattern)
                if call:
                    calls.append(call)

        seen: Set[str] = set()
        unique: List[Dict[str, Any]] = []
        for c in calls:
            key = f"{c.get('tool_name', '')}:{str(c.get('args', ''))[:60]}"
            if key not in seen:
                seen.add(key)
                unique.append(c)

        return unique

    def _parse_match(self, match: re.Match, pattern_source: str) -> Optional[Dict[str, Any]]:
        raw = match.group(0)

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
                    if re.match(r'^[a-z][a-z0-9_]+$', grp.strip(), re.IGNORECASE):
                        return {"tool_name": grp.strip().lower(), "args": {}, "raw": raw[:200]}

        if groups and groups[0]:
            name_candidate = groups[0].strip()
            if re.match(r'^[a-z][a-z0-9_]+$', name_candidate, re.IGNORECASE):
                return {"tool_name": name_candidate.lower(), "args": {}, "raw": raw[:200]}

        return None

    def _validate_args(self, args_text: str) -> List[str]:
        value_texts: List[str] = []
        try:
            data = json.loads(args_text)
            if isinstance(data, dict):
                value_texts = self._collect_string_values(data)
        except (json.JSONDecodeError, ValueError):
            pass

        if not value_texts:
            value_texts = [args_text]

        # Expand with multi-layer decoding
        expanded_texts: List[str] = []
        for val in value_texts:
            expanded_texts.extend(self._decode_string_recursively(val))

        issues: List[str] = []
        for value in expanded_texts:
            for tag, pat in _DANGEROUS_ARG_PATTERNS:
                if pat.search(value):
                    issues.append(f"suspicious_arg:{tag}")

        return list(dict.fromkeys(issues))

    def _decode_string_recursively(self, text: str, depth: int = 0, seen: Optional[Set[str]] = None) -> List[str]:
        if seen is None:
            seen = set()
        if depth > 5 or text in seen:
            return []
        
        seen.add(text)
        results = [text]
        
        # Base64
        try:
            pad = len(text) % 4
            b64_candidate = text + ('=' * (4 - pad) if pad else '')
            decoded_bytes = base64.b64decode(b64_candidate, validate=True)
            decoded_str = decoded_bytes.decode('utf-8')
            if decoded_str and decoded_str != text:
                results.extend(self._decode_string_recursively(decoded_str, depth + 1, seen))
        except Exception:
            pass

        # URL Decode
        try:
            if '%' in text or '+' in text:
                url_decoded = urllib.parse.unquote_plus(text)
                if url_decoded and url_decoded != text:
                    results.extend(self._decode_string_recursively(url_decoded, depth + 1, seen))
        except Exception:
            pass

        # Hex Decode
        try:
            if len(text) % 2 == 0 and len(text) > 0:
                hex_decoded = bytes.fromhex(text).decode('utf-8')
                if hex_decoded and hex_decoded != text:
                    results.extend(self._decode_string_recursively(hex_decoded, depth + 1, seen))
        except Exception:
            pass

        return results

    @staticmethod
    def _collect_string_values(obj: Any, depth: int = 0) -> List[str]:
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
