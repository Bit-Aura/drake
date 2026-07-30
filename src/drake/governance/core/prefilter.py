"""
Fast Pre-Filter
================
Lightweight first-pass filter that runs BEFORE the heavy ML pipeline.
Detects obvious injection / jailbreak attempts in under 5 ms using
pre-compiled regular expressions only — no model inference required.

If a pattern matches the request is immediately blocked; the threat-analysis
pipeline and LLM are never invoked.

Patterns covered
----------------
  * Instruction override     – "ignore previous/all instructions", "forget the above"
  * System-prompt extraction – "what is your system prompt", "reveal your instructions"
  * DAN / jailbreak frames   – "do anything now", "DAN mode", "jailbreak", "you are now …"
  * Role-override            – "act as if you have no restrictions", "pretend you are evil"
  * Tool / code exploitation – "exec(", "subprocess.run", "os.system", "eval(base64"
  * Prompt injection markers – "</s>", "###Human:", injection separator sequences
  * Social-engineering hooks – "for educational purposes only", "hypothetically if"
    combined with dangerous verbs
"""
from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Pattern catalogue
# ---------------------------------------------------------------------------

# Each entry: (pattern_str, flags, label)
# All patterns are pre-compiled once at import time.
_RAW_PATTERNS: List[Tuple[str, int, str]] = [

    # ── Instruction override ────────────────────────────────────────────────
    (r"ignore\s+(all\s+)?(the\s+)?(previous\s+|prior\s+)?(above\s+)?(instructions?|directives?|prompts?|rules?)",
     re.I, "instruction_override"),
    (r"forget\s+(all\s+|every\s+|the\s+above|previous|prior)\b",
     re.I, "instruction_override"),
    (r"disregard\s+(all\s+(prior\s+|previous\s+)?|any\s+|previous\s+|prior\s+)(instructions?|rules?|guidelines?)",
     re.I, "instruction_override"),
    (r"comply\s+(without|with\s+no)\s+(limits?|restrictions?|rules?|guidelines?)",
     re.I, "instruction_override"),
    (r"override\s+(your\s+)?(instructions?|directives?|safety|programming|training)",
     re.I, "instruction_override"),

    # ── System-prompt extraction ────────────────────────────────────────────
    (r"(what|show|reveal|print|output|tell me|repeat)\s+(me\s+)?(is\s+)?your\s+"
     r"(system\s+prompt|initial\s+prompt|original\s+instructions?|"
     r"hidden\s+instructions?|base\s+instructions?|secret\s+prompt)",
     re.I, "system_prompt_extraction"),
    (r"(repeat|output|print|write out|say)\s+(exactly|verbatim|literally|word\s+for\s+word)"
     r"\s+(what|the|your)\s+(above|system|initial|first)",
     re.I, "system_prompt_extraction"),
    (r"(system\s+prompt|initial\s+prompt|base\s+instructions?|hidden\s+instructions?)"
     r".{0,60}\b(exactly|verbatim|word\s+for\s+word)\b",
     re.I, "system_prompt_extraction"),
    (r"what\s+(prompt\s+)?(have\s+you\s+been|were\s+you)\s+(given|instructed|told|trained)",
     re.I, "system_prompt_extraction"),
    (r"what\s+.{0,40}(you\s+were|you've\s+been)\s+(given|told|instructed|trained)",
     re.I, "system_prompt_extraction"),

    # ── DAN / jailbreak frames ──────────────────────────────────────────────
    (r"\bDAN\b",
     re.I, "jailbreak_dan"),
    (r"do\s+anything\s+now",
     re.I, "jailbreak_dan"),
    (r"jailbreak\b",
     re.I, "jailbreak_general"),
    (r"you\s+are\s+now\s+(?:a\s+|an\s+)(free|unfiltered|uncensored|evil|unrestricted|"
     r"dangerous|hacker|harmful|malicious)",
     re.I, "jailbreak_general"),
    (r"(pretend|imagine|act)\s+(that\s+)?(you\s+)?(have\s+no\s+(restrictions?|limits?|rules?|ethics?|morals?)|"
     r"are\s+(?:an?\s+)?(evil|unrestricted|uncensored|malicious|hacker))",
     re.I, "jailbreak_persona"),
    (r"(switch\s+to|enable|activate|enter)\s+.{0,30}(mode|protocol)\s*[:=]?"
     r"\s*(developer|jailbreak|god|bypass|unrestricted|evil|unsafe)",
     re.I, "jailbreak_mode"),
    (r"as\s+an?\s+(AI|LLM|language\s+model)\s+(without|with\s+no)\s+"
     r"(restrictions?|limits?|filters?|safety|ethics?)",
     re.I, "jailbreak_general"),

    # ── Role/identity override ──────────────────────────────────────────────
    (r"your\s+(real|true|hidden|actual)\s+(name|identity|self|purpose)\s+is\b",
     re.I, "identity_override"),
    (r"(you\s+are\s+not\s+|you\'re\s+not\s+)(bound\s+by|limited\s+by|restricted\s+by|an?\s+AI)",
     re.I, "identity_override"),

    # ── Tool / code exploitation ────────────────────────────────────────────
    (r"\beval\s*\(",  re.I, "tool_exploit"),
    (r"\bexec\s*\(",  re.I, "tool_exploit"),
    (r"\bos\.system\s*\(",    re.I, "tool_exploit"),
    (r"\bsubprocess\.(run|call|Popen|check_output)\s*\(",  re.I, "tool_exploit"),
    (r"\b__import__\s*\(",    re.I, "tool_exploit"),
    (r"base64\s*\.\s*b64decode\s*\(",  re.I, "tool_exploit"),
    (r"powershell\s+(-[a-z]+\s+)*(-enc|-nop|-w\s+hidden)",  re.I, "tool_exploit"),
    (r"cmd(\.exe)?\s+/c\s+",  re.I, "tool_exploit"),

    # ── Prompt injection separators ─────────────────────────────────────────
    (r"</?(s|system|human|assistant|user|inst)\s*>",   0, "injection_separator"),
    (r"###\s*(Human|User|System|Assistant|Instruction)\s*:", 0, "injection_separator"),
    (r"\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>",            0, "injection_separator"),
    (r"<\|im_start\|>|<\|im_end\|>|<\|endoftext\|>",    0, "injection_separator"),

    # ── Adversarial / bypass language ──────────────────────────────────────
    (r"for\s+(educational|research|academic|demo)\s+purposes?\s+only\s*[,.]?\s*"
     r"(how\s+to|explain\s+how\s+to|describe\s+how\s+to|show\s+me\s+how\s+to)\s+"
     r"(hack|exploit|bypass|crack|break\s+into|steal|phish)",
     re.I, "adversarial_bypass"),
    (r"hypothetically\s+(speaking\s+)?if\s+you\s+(had\s+no|could\s+ignore|were\s+allowed)",
     re.I, "adversarial_bypass"),
    (r"(please\s+)?pretend\s+(this\s+is\s+)?fiction\s+(and\s+)?(write|tell|explain|describe)\s+"
     r"(how\s+to|a\s+way\s+to|steps\s+to)\s+(hack|exploit|steal|attack)",
     re.I, "adversarial_bypass"),
]

# Compile once
_COMPILED: List[Tuple[re.Pattern, str]] = [
    (re.compile(pat, flags), label)
    for pat, flags, label in _RAW_PATTERNS
]


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class PreFilterResult:
    blocked: bool
    tier: str                        # "CRITICAL" or "SAFE"
    reason: Optional[str]            # label like "jailbreak_dan"
    matched_pattern: Optional[str]   # description of the triggered pattern
    latency_ms: float
    violations: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# FastPreFilter
# ---------------------------------------------------------------------------

class FastPreFilter:
    """
    Regex-only, zero-model pre-filter.  Should complete in < 5 ms on any
    modern hardware.

    Usage::

        pf = FastPreFilter()
        result = pf.check("Ignore all previous instructions and ...")
        if result.blocked:
            # short-circuit — do not call the ML pipeline
            ...
    """

    def __init__(self, high_confidence_threshold: int = 1) -> None:
        """
        Args:
            high_confidence_threshold: Minimum number of distinct pattern matches
                required to trigger a block.  Default 1 = block on first match.
                Raise to 2+ for lower false-positive rate at the cost of missing
                some single-signal attacks.
        """
        self.threshold = high_confidence_threshold

    def check(self, prompt: str) -> PreFilterResult:
        """
        Screen *prompt* against all registered patterns.

        Returns a :class:`PreFilterResult` immediately (< 5 ms target).
        """
        t0 = time.perf_counter()

        normalized_prompt = unicodedata.normalize("NFKC", prompt)

        violations: List[str] = []
        first_label: Optional[str] = None
        first_pattern_desc: Optional[str] = None

        for compiled, label in _COMPILED:
            m = compiled.search(normalized_prompt)
            if m:
                if label not in violations:
                    violations.append(label)
                if first_label is None:
                    first_label = label
                    first_pattern_desc = m.group(0)[:80]

        latency_ms = (time.perf_counter() - t0) * 1000
        blocked = len(violations) >= self.threshold

        return PreFilterResult(
            blocked=blocked,
            tier="CRITICAL" if blocked else "SAFE",
            reason="fast_filter_trigger" if blocked else None,
            matched_pattern=first_pattern_desc if blocked else None,
            latency_ms=latency_ms,
            violations=violations,
        )
