# DEPENDENCY REPORT

This document details the dependencies of the lightweight governance and guardrail files successfully staged for the DELL_MCP environment.

### 1. `prefilter.py`
* **Original Source:** `backend/pipeline/prefilter.py`
* **Required Imports:** `re`, `time`, `dataclasses.dataclass`, `typing`
* **Missing Imports:** None
* **Adaptation Effort:** Minimal. Can be used exactly as-is.
* **Risk Level:** Very Low

### 2. `tool_guard.py`
* **Original Source:** `backend/intelligence/output_security/tool_guard.py`
* **Required Imports:** `json`, `logging`, `re`, `time`, `dataclasses.dataclass`, `typing`
* **Missing Imports:** None
* **Adaptation Effort:** Minimal. Works perfectly to ensure generated tool arguments match schemas.
* **Risk Level:** Very Low

### 3. `policy_engine.py`
* **Original Source:** `backend/intelligence/policy_engine.py`
* **Required Imports:** `typing.Tuple`
* **Missing Imports:** None
* **Adaptation Effort:** Minimal. The tier boundaries can be updated for MCP routing rules.
* **Risk Level:** Very Low

### 4. `risk_engine.py`
* **Original Source:** `backend/intelligence/risk_engine.py`
* **Required Imports:** `math`
* **Missing Imports:** None
* **Adaptation Effort:** Minimal. It relies purely on the Exponential Weighted Moving Average (EWMA) algorithm.
* **Risk Level:** Very Low

### 5. `soc_logger.py`
* **Original Source:** `backend/intelligence/soc_logger.py`
* **Required Imports:** `json`, `os`, `datetime`, `pathlib`, `typing`
* **Missing Imports:** None
* **Adaptation Effort:** Minimal. It outputs JSONL format directly.
* **Risk Level:** Very Low

### 6. `session_manager.py`
* **Original Source:** `backend/intelligence/session_manager.py`
* **Required Imports:** `datetime`, `typing`
* **Missing Imports:** None
* **Adaptation Effort:** Minimal. Simple in-memory dict tracking.
* **Risk Level:** Very Low

### 7. `escalation_engine.py`
* **Original Source:** `backend/intelligence/escalation_engine.py`
* **Required Imports:** `typing.Tuple`
* **Missing Imports:** None
* **Adaptation Effort:** Minimal.
* **Risk Level:** Very Low
