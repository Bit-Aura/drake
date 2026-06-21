# Hardcoded Governance Constants Report

This report identifies all hardcoded constants discovered in the governance and guardrails stack of the DELL_MCP codebase.

## 1. `src/governance/core/risk.py`

| Item | Line | Current Value | Purpose | Runtime Impact |
| --- | --- | --- | --- | --- |
| DELETE Method Weight | 41 | `50.0` | Adds high risk to destructive requests | Escalates deletion workflows to HIGH/CRITICAL |
| PATCH/PUT Method Weight | 44 | `30.0` | Adds moderate risk to modification requests | Pushes modifications to MEDIUM/HIGH |
| POST Method Weight | 47 | `20.0` | Adds low-moderate risk to creation requests | Pushes creations to MEDIUM |
| High Risk Keyword Weight | 52 | `40.0` | Adds severe risk to sensitive keywords | Flags operations involving 'firmware', 'reboot' |
| Default Total Assets | 64 | `100` | Fallback size of the fleet if context missing | Affects blast-radius severity multiplier |
| Blast Multiplier Coefficient | 67 | `3.0` | Scales blast radius up to 4x total impact | Greatly inflates risk for multi-target attacks |
| Risk Cap | 75 | `100.0` | Ceilings the risk score | Prevents unbounded score growth |
| Critical Risk Threshold | 84 | `80.0` | Classifies workflow as CRITICAL | Enforces HARD_DENY or strict APPROVAL |
| High Risk Threshold | 86 | `50.0` | Classifies workflow as HIGH | Requires APPROVAL |
| Medium Risk Threshold | 88 | `20.0` | Classifies workflow as MEDIUM | May require APPROVAL depending on policy |
| Governance Score Coeff | 95 | `0.5` | Risk deduction from base governance score | High risk directly degrades governance score |
| Schema Missing Penalty | 97 | `20.0` | Penalizes poor OpenAPI documentation | Promotes well-defined APIs |
| Read Only Bonus | 101 | `10.0` | Rewards safe, idempotent GET requests | Improves governance standing |

## 2. `src/governance/runtime/workflow_campaign_tracker.py`

| Item | Line | Current Value | Purpose | Runtime Impact |
| --- | --- | --- | --- | --- |
| Cumulative Risk Coeff | 86 | `0.3` | Weight given to total session risk | Accounts for repeated dangerous requests |
| Density Coeff | 86 | `30.0` | Weight given to proportion of destructive actions | Flags sessions with high destructive ratio |
| Similarity Coeff | 86 | `20.0` | Weight given to repetitive request signatures | Identifies brute-force / scripted loops |
| Velocity Coeff | 86 | `2.0` | Weight given to speed of execution | Flags automated tool spam |
| Campaign Threshold | 90 | `0.65` | Cut-off for classifying session as a Campaign | Immediately upgrades risk to CRITICAL |

## 3. `src/governance/ai_guardrails/prefilter.py`

| Item | Line | Current Value | Purpose | Runtime Impact |
| --- | --- | --- | --- | --- |
| Prefilter Pattern Catalog | 26 | `_RAW_PATTERNS` | Hardcoded regex injection definitions | Determines what triggers the AI Guardrail |

## 4. `src/governance/ai_guardrails/tool_guard.py`

| Item | Line | Current Value | Purpose | Runtime Impact |
| --- | --- | --- | --- | --- |
| Default Safe Tools | 24 | `DEFAULT_SAFE_TOOLS` | Allowlist of harmless native capabilities | Unknown tools are penalized in strict mode |
| Blocked Tools | 35 | `BLOCKED_TOOLS` | Denylist of hazardous RCE/shell tools | Immediately blocks ToolGuard validation |
| Dangerous Arg Patterns | 42 | `_DANGEROUS_ARG_PATTERNS` | Regex definitions of shell injection & path traversal | Rejects dangerous parameter payloads |
| Blocked Tool Risk Weight | 110 | `0.70` | Risk added if a blocked tool is seen | Greatly contributes to session risk |
| Unallowed Tool Risk Weight | 115 | `0.50` | Risk added if an unknown tool is seen | Penalizes rogue tool creation |
| Suspicious Arg Risk Coeff | 121 | `0.35` | Risk added per suspicious parameter | Accumulates based on injection severity |
