# MISSING DEPENDENCIES (SKIPPED FILES)

The following files were deliberately skipped during staging because their dependency count is too high, they rely on heavy Machine Learning frameworks, or they are too tightly coupled to non-MCP features.

### `backend/intelligence/output_security/validator.py`
* **Reason:** Imports `numpy` and conditionally invokes heavy `transformers` pipelines (Zero-Shot Classification). This creates massive latency, bloated memory constraints, and complex runtime requirements.
* **Action:** IGNORED. Only static regex features should be used in MCP.

### `backend/intelligence/output_security/sanitizer.py`
* **Reason:** Highly dependent on `ValidationResult` and `_LEAK_PATTERNS` structures imported directly from `validator.py`.
* **Action:** IGNORED. Tightly coupled code.

### `backend/intelligence/output_security/output_engine.py`
* **Reason:** It serves as an orchestrator that explicitly instantiates the skipped `OutputValidator` and `OutputSanitizer`.
* **Action:** IGNORED. DELL_MCP should build its own lightweight orchestrator utilizing `tool_guard.py` instead.

### `backend/intelligence/intelligence_api.py`
* **Reason:** Designed specifically to accept a `fusion_score` from a PyTorch `FusionMLP` network.
* **Action:** IGNORED. It is better to use the individual engines (`RiskEngine`, `PolicyEngine`) separately in DELL_MCP.

### `backend/integrated_system.py`
* **Reason:** The core orchestrator for heavy AI dependencies (LSTM, FAISS, PyTorch).
* **Action:** IGNORED completely.
