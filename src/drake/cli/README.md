# Enterprise Pipeline Control Plane (CLI)

This document details the production-ready architecture underpinning our **Enterprise Control Plane** located in `src/drake/cli`. We have evolved beyond fragmented scripts and disjointed deployment utilities to deliver a **Unified CLI Orchestrator**. By combining a robust command router, real-time rich telemetry, and headless CI/CD integration, we achieve what standard tooling fails to: **single-pane-of-glass operability, zero-friction developer experience, and fully automated pipeline execution.**

Our mission is to maximize Developer Experience (DX), Observability, and Operational Control across the entire MCP Workflow Proxy lifecycle.

---

## 1. The Flaw in Legacy Architectures

Most AI orchestration tools fall into operational traps during deployment. Below is a comparison of how our control plane overcomes these industry-standard flaws:

| Legacy Architecture Flaw | The Drake Solution |
| :--- | :--- |
| **Fragmented Scripting:** Operators are forced to run disjointed scripts (`parse.py` → `cluster.py`). This manual chaining leads to human error, missed flags, and broken state transfers. | **Unified Command Routing:** A centralized Typer CLI orchestrates the entire lifecycle (`drake pipeline`) with strict argument validation and deterministic state passing. |
| **Black-Box Execution:** The pipeline runs silently. When a cycle or hardware error occurs, operators receive cryptic stack traces instead of actionable insights. | **Real-Time Telemetry & UI:** The CLI renders live Rich matrices (`drake health`, `drake overview --watch`), explicitly exposing subsystem health, risk scores, and DAG integrity visually. |

Our architecture abandons these silos. We employ a **Centralized Command Interface** that abstracts complexity while providing military-grade observability into the underlying engine.

---

## 2. The 4-Stage Control Plane Architecture

### Stage 1: Unified Command Routing
The CLI acts as the entry point for all subsystems (`cluster`, `governance`, `compatibility`, `runtime`, `ansible`, `audit`, etc.).
- **Mechanism:** Powered by Typer/Click, it provides strict argument validation and dependency injection via the `CLIContainer`.
- **Output:** A standardized interface (`drake <command> <subcommand>`) that eliminates configuration drift.

### Stage 2: One-Click Orchestration
We automate the entire end-to-end lifecycle.
- **The Pipeline Command:** The `drake pipeline` command autonomously orchestrates the exact sequence of ingestion → clustering → dependency mapping → governance validation → proxy serving.
- **Resilience:** Passes state deterministically between stages without requiring intermediate manual steps.

### Stage 3: Real-Time Telemetry & Dashboards
The CLI is not just a command runner; it is a live monitoring tool.
- **Overview & Health:** Commands like `drake overview --watch` and `drake health` render real-time Rich terminal UI matrices detailing subsystem health, active workflows, and risk scores.
- **Output:** Operators can visually monitor the cluster and proxy performance without needing external APM dashboards.

### Stage 4: CI/CD Automation & Headless Mode
Every visual component can be bypassed for automation.
- **JSON Mode:** By appending the `--json` flag, all rich UI tables and banners are suppressed, and the CLI outputs pure machine-readable JSON.
- **Integration:** Allows native integration into GitHub Actions, Jenkins, or Ansible Tower pipelines for automated enterprise deployments.

---

## 3. Execution Resilience & Stateful Orchestration

At the operational layer, our CLI guarantees enterprise reliability:
- **Crash Shielding:** The CLI uses a centralized error handler. Unexpected exceptions are intercepted, suppressed into clean error messages (`DellCLIError`), and formatted with clear "Cause", "Impact", and "Action" recommendations.
- **Debug Traceability:** Running with `--debug` immediately exposes the raw Python traceback for developer-level triage without polluting the standard operator view.

---

## 4. Demonstrating the CLI Interface (Examples)

Below are practical demonstrations of how the CLI orchestrates the enterprise pipeline, designed to give you a clear grasp of the control plane's capabilities.

### Example 1: Full Pipeline Execution
Instead of running disparate scripts, operators can trigger the entire lifecycle in one command:
```bash
# Ingests the OpenAPI spec, clusters the endpoints, and boots the FastMCP proxy
$ drake pipeline --spec iDRAC_OpenAPI.yaml
```

### Example 2: Real-Time Telemetry Dashboards
Operators can monitor the health and throughput of the proxy natively in the terminal using Rich UI matrices:
```bash
# Renders a continuously updating visual dashboard
$ drake overview --watch --interval 5

# Displays system diagnostics and DAG integrity
$ drake health
```

### Example 3: Subsystem Granular Control
If an operator needs to manually intervene or test a specific pipeline stage, the CLI routes directly to decoupled subsystems:
```bash
# Run clustering with a specific Leiden resolution parameter
$ drake cluster run --threshold 0.72

# Review the audit ledger for any intercepted AI payloads
$ drake audit show-events --limit 100
```

### Example 4: CI/CD & Headless Integration
For Jenkins or GitHub Actions, the visual elements can be bypassed completely:
```bash
# Executes the pipeline but outputs pure machine-readable JSON for jq parsing
$ drake pipeline --spec target.json --json
```

---

## 5. Enterprise Governance, Risk & Security

The CLI is the interface for human-in-the-loop governance.
- **Audit & Compliance:** The `drake audit` and `drake governance` subcommands allow operators to view execution histories, inspect blocked payloads, and manually approve or reject clustered workflows before they are exposed to the LLM.
- **Configuration Management:** The `drake config` command manages the secure `.env` states and execution policies, ensuring the proxy boots with mathematically proven rulesets.

---

## 6. Maximum Explainability & AI Capabilities

Our engine communicates exactly what it is doing at all times.
- **Semantic Theming:** The `theme.py` module enforces a standardized visual language (e.g., Red for critical Risk, Yellow for warnings, Green for approved edges).
- **Graph Explainability:** The CLI can visually render the execution DAGs and semantic communities directly in the terminal, bridging the gap between raw data and human understanding.

---

## 7. Performance & Scalability Target

We designed the CLI for zero-overhead execution.
- **Sub-Second Boot Times:** By leveraging lazy imports in Typer, the CLI loads in milliseconds, making it ideal for rapid automation scripting.
- **Extensibility:** The `plugins` architecture allows the Dell enterprise to dynamically drop in new subcommands (e.g., custom firmware validation tools) without touching the core CLI source code.
