# Enterprise Governance Control Console (Frontend)

This document details the production-ready architecture underpinning our **Enterprise Human-in-the-Loop Console** located in the `frontend` directory. We have evolved beyond headless orchestration to deliver a **Visual Governance Layer**. By combining real-time Directed Acyclic Graph (DAG) rendering, strict approval gates, and live audit telemetry, we achieve what silent proxies fail to: **absolute human oversight, mathematical cluster validation, and visual threat prevention.**

Our mission is to maximize Observability, Human-in-the-Loop Governance, and Operational Transparency at an enterprise scale.

---

## 1. The Flaw in Legacy Architectures

Most orchestration platforms fall into structural traps when building control planes. Below is a comparison of how our architecture overcomes these industry-standard flaws:

| Legacy Architecture Flaw | The Drake Solution |
| :--- | :--- |
| **Blind Execution Logs:** Operators are forced to read raw terminal output or static text logs. There is no visual representation of the workflows being synthesized. | **Interactive DAG Visualization:** Integrates React Flow to dynamically map the NetworkX and Leiden clusters, allowing operators to visually trace dependency edge weights. |
| **No Human-in-the-Loop:** Systems automatically approve whatever the AI generates. If an agent hallucinates a destructive pipeline, there is no UI to intercept or reject it. | **Strict Approval Gates:** The `/workflows/pending` queue forces an operator to review the AI-generated names and endpoints before they are registered to the FastMCP server. |

Our architecture abandons these silos. We employ a **High-Fidelity React Console** that allows enterprise operators to visualize the exact endpoints, review the AI-generated names, and explicitly approve or reject workflows before they ever reach the proxy.

---

## 2. The Visual Governance Pipeline

### Stage 1: The Matrix Dashboard
The frontend provides a real-time overview of the proxy's internal state.
- **Mechanism:** Built on Next.js 15 and TanStack Query, the dashboard polls the backend `/overview` and `/metrics` APIs.
- **Output:** A single pane of glass showing total ingested endpoints, discovered clusters, approval pending states, and active execution metrics.

### Stage 2: Interactive DAG Visualization
The UI does not just list endpoints; it renders their mathematical relationships.
- **Mechanism:** Integrates React Flow to dynamically map the `NetworkX` and `Leiden` cluster outputs.
- **Output:** Operators can visually click through the dependencies to see exactly *why* five endpoints were clustered together by the algorithm.

### Stage 3: Strict Approval Gates (The Only Human Bottleneck)
This is the core of our deterministic human-in-the-loop governance.
- **The Strict Rule:** When raw endpoints (tools) are synthesized by the AI into high-level operational workflows, **this is the exact and only moment where human approval is strictly mandatory.**
- **Enforcement:** The `/workflows/pending` endpoint feeds a review queue. An operator must review the AI-generated `display_name` and the structural endpoint list. Once the operator signs off (`POST /workflows/{id}/approve`), the workflow is locked, registered into the FastMCP server, and deployed as a production-ready tool. After this boundary is certified, the LLM can execute the workflow autonomously without requiring the operator to babysit subsequent executions.

---

## 3. Execution Resilience & Stateful Orchestration

At the UI layer, our architecture guarantees enterprise reliability:
- **Deterministic Loading States:** No simulated data is hardcoded. Loading, empty, and error states are treated as first-class citizens using React Suspense boundaries, ensuring integration failures are immediately visible.
- **Client State Management:** Zustand securely manages client-side UI filters, graph node selections, and sorting preferences without polluting the global scope or relying on fragile prop-drilling.

---

## 4. Enterprise Governance, Risk & Security

Every visual component serves a governance purpose.
- **Audit Trails:** The `/audit/events` view streams the immutable ledger of every intercepted action and blocked payload directly to the operator.
- **Type-Safe Contracts:** The API client strictly enforces TypeScript interfaces matching the Python Pydantic models. If the backend schema changes unexpectedly, the UI layer catches it securely.

---

## 5. Maximum Explainability & AI Capabilities

Our engine provides deep context back to the operator.
- **Explainable Clustering:** The frontend renders the specific edge weights and semantic distances calculated during the clustering phase, proving that the workflow generation is mathematically sound, not just AI-hallucinated.
- **Hot-Reload Trigger:** Operators can trigger a `POST /mcp/reload` directly from the UI, commanding the FastMCP server to hot-swap the LLM context window with newly approved tools seamlessly.

---

## 6. Performance & Scalability Target

We designed the frontend for massive datasets.
- **Optimized Rendering:** React Flow combined with TanStack Query caching ensures that visualizing a 500-node graph does not lock up the browser's main thread.
- **Production-Ready Stack:** Leveraging Next.js 15 App Router, Tailwind CSS, and shadcn/ui components for a lightweight, accessible, and high-performance operator experience.
