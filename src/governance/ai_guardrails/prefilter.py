"""
Fast Pre-Filter
================
Lightweight first-pass filter that runs BEFORE the heavy ML pipeline.
Detects obvious injection / jailbreak attempts in under 5 ms using
pre-compiled regular expressions only — no model inference required.

If a pattern matches the request is immediately blocked; the threat-analysis
pipeline and LLM are never invoked.
"""
from __future__ import annotations

import logging
import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
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

# ---------------------------------------------------------------------------
# Pattern catalogue
# ---------------------------------------------------------------------------

_RAW_PATTERNS: List[Tuple[str, int, str]] = [
    # Instruction override
    (r"ignore\s+(all\s+)?(the\s+)?(previous\s+|prior\s+)?(above\s+)?(instructions?|directives?|prompts?|rules?)", re.I, "instruction_override"),
    (r"forget\s+(all\s+|every\s+|the\s+above|previous|prior)\b", re.I, "instruction_override"),
    (r"disregard\s+(all\s+(prior\s+|previous\s+)?|any\s+|previous\s+|prior\s+)(instructions?|rules?|guidelines?)", re.I, "instruction_override"),
    (r"comply\s+(without|with\s+no)\s+(limits?|restrictions?|rules?|guidelines?)", re.I, "instruction_override"),
    (r"override\s+(your\s+)?(instructions?|directives?|safety|programming|training)", re.I, "instruction_override"),

    # System-prompt extraction
    (r"(what|show|reveal|print|output|tell me|repeat)\s+(me\s+)?(is\s+)?your\s+(system\s+prompt|initial\s+prompt|original\s+instructions?|hidden\s+instructions?|base\s+instructions?|secret\s+prompt)", re.I, "system_prompt_extraction"),
    (r"(repeat|output|print|write out|say)\s+(exactly|verbatim|literally|word\s+for\s+word)\s+(what|the|your)\s+(above|system|initial|first)", re.I, "system_prompt_extraction"),
    (r"(system\s+prompt|initial\s+prompt|base\s+instructions?|hidden\s+instructions?).{0,60}\b(exactly|verbatim|word\s+for\s+word)\b", re.I, "system_prompt_extraction"),
    (r"what\s+(prompt\s+)?(have\s+you\s+been|were\s+you)\s+(given|instructed|told|trained)", re.I, "system_prompt_extraction"),
    (r"what\s+.{0,40}(you\s+were|you\'ve\s+been)\s+(given|told|instructed|trained)", re.I, "system_prompt_extraction"),

    # DAN / jailbreak frames
    (r"\bDAN\b", re.I, "jailbreak_dan"),
    (r"do\s+anything\s+now", re.I, "jailbreak_dan"),
    (r"jailbreak\b", re.I, "jailbreak_general"),
    (r"you\s+are\s+now\s+(?:a\s+|an\s+)(free|unfiltered|uncensored|evil|unrestricted|dangerous|hacker|harmful|malicious)", re.I, "jailbreak_general"),
    (r"(pretend|imagine|act)\s+(that\s+)?(you\s+)?(have\s+no\s+(restrictions?|limits?|rules?|ethics?|morals?)|are\s+(?:an?\s+)?(evil|unrestricted|uncensored|malicious|hacker))", re.I, "jailbreak_persona"),
    (r"(switch\s+to|enable|activate|enter)\s+.{0,30}(mode|protocol)\s*[:=]?\s*(developer|jailbreak|god|bypass|unrestricted|evil|unsafe)", re.I, "jailbreak_mode"),
    (r"as\s+an?\s+(AI|LLM|language\s+model)\s+(without|with\s+no)\s+(restrictions?|limits?|filters?|safety|ethics?)", re.I, "jailbreak_general"),

    # Role/identity override
    (r"your\s+(real|true|hidden|actual)\s+(name|identity|self|purpose)\s+is\b", re.I, "identity_override"),
    (r"(you\s+are\s+not\s+|you\'re\s+not\s+)(bound\s+by|limited\s+by|restricted\s+by|an?\s+AI)", re.I, "identity_override"),

    # Tool / code exploitation
    (r"\beval\s*\(",  re.I, "tool_exploit"),
    (r"\bexec\s*\(",  re.I, "tool_exploit"),
    (r"\bos\.system\s*\(",    re.I, "tool_exploit"),
    (r"\bsubprocess\.(run|call|Popen|check_output)\s*\(",  re.I, "tool_exploit"),
    (r"\b__import__\s*\(",    re.I, "tool_exploit"),
    (r"base64\s*\.\s*b64decode\s*\(",  re.I, "tool_exploit"),
    (r"powershell\s+(-[a-z]+\s+)*(-enc|-nop|-w\s+hidden)",  re.I, "tool_exploit"),
    (r"cmd(\.exe)?\s+/c\s+",  re.I, "tool_exploit"),

    # Prompt injection separators
    (r"</?(s|system|human|assistant|user|inst)\s*>",   0, "injection_separator"),
    (r"###\s*(Human|User|System|Assistant|Instruction)\s*:", 0, "injection_separator"),
    (r"\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>",            0, "injection_separator"),
    (r"<\|im_start\|>|<\|im_end\|>|<\|endoftext\|>",    0, "injection_separator"),

    # Adversarial / bypass language
    (r"for\s+(educational|research|academic|demo)\s+purposes?\s+only\s*[,.]?\s*(how\s+to|explain\s+how\s+to|describe\s+how\s+to|show\s+me\s+how\s+to)\s+(hack|exploit|bypass|crack|break\s+into|steal|phish)", re.I, "adversarial_bypass"),
    (r"hypothetically\s+(speaking\s+)?if\s+you\s+(had\s+no|could\s+ignore|were\s+allowed)", re.I, "adversarial_bypass"),
    (r"(please\s+)?pretend\s+(this\s+is\s+)?fiction\s+(and\s+)?(write|tell|explain|describe)\s+(how\s+to|a\s+way\s+to|steps\s+to)\s+(hack|exploit|steal|attack)", re.I, "adversarial_bypass"),
]

# Compile once
_COMPILED: List[Tuple[re.Pattern, str]] = [
    (re.compile(pat, flags), label)
    for pat, flags, label in _RAW_PATTERNS
]

@dataclass
class PreFilterResult:
    blocked: bool
    tier: str
    reason: Optional[str]
    matched_pattern: Optional[str]
    latency_ms: float
    violations: List[str] = field(default_factory=list)


class FastPreFilter:
    """
    Regex-only, zero-model pre-filter.
    """

    def __init__(self, high_confidence_threshold: int = None) -> None:
        self.gov_config = _load_gov_config()
        self.prefilter_cfg = self.gov_config.get("prefilter", {})
        
        self.threshold = high_confidence_threshold if high_confidence_threshold is not None else self.prefilter_cfg.get("threshold", 1)

    def check(self, prompt: str) -> PreFilterResult:
        """
        Screen `prompt` against all registered patterns.
        Applies Unicode NFKC normalization and casefolding.
        """
        t0 = time.perf_counter()

        # Feature 3: Unicode Normalization
        normalized_prompt = unicodedata.normalize('NFKC', prompt).casefold()
        
        # Strip all whitespace for obfuscated spaced attacks (e.g. i g n o r e)
        despaced_prompt = re.sub(r'\s+', '', normalized_prompt)

        violations: List[str] = []
        first_label: Optional[str] = None
        first_pattern_desc: Optional[str] = None

        for compiled, label in _COMPILED:
            m = compiled.search(normalized_prompt)
            if not m:
                # Fallback to check despaced version for obfuscation
                m = compiled.search(despaced_prompt)
            
            if m:
                if label not in violations:
                    violations.append(label)
                if first_label is None:
                    first_label = label
                    first_pattern_desc = m.group(0)[:80]

        latency_ms = (time.perf_counter() - t0) * 1000
        blocked = len(violations) >= self.threshold
        
        if blocked:
            logger.warning(f"FastPreFilter: Blocked prompt due to {len(violations)} violations (first: {first_label}). Latency: {latency_ms:.2f}ms")
        else:
            logger.debug(f"FastPreFilter: Prompt clean. Latency: {latency_ms:.2f}ms")

        return PreFilterResult(
            blocked=blocked,
            tier="CRITICAL" if blocked else "SAFE",
            reason="fast_filter_trigger" if blocked else None,
            matched_pattern=first_pattern_desc if blocked else None,
            latency_ms=latency_ms,
            violations=violations,
        )
