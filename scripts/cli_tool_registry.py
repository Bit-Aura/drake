"""
cli_tool_registry.py
====================
Static registry of all drake CLI commands exposed to the AI agent as tools.

Each entry defines:
  - name          : Unique snake_case identifier the LLM uses to select this tool.
  - description   : Human-intent description used by the LLM for tool selection.
  - command       : Base argv list (after the python invocation), e.g. ["cluster", "run"].
  - args          : List of argument descriptors understood by build_cli_command().

Argument descriptor schema:
  {
    "name"       : str   — flag name (e.g. "--specs") or positional placeholder (no "--" prefix).
    "positional" : bool  — True → value is inserted as a bare positional arg (not flagged).
    "flag"       : str   — (optional) override the CLI flag string when it differs from name.
    "type"       : str   — "str" | "int" | "bool" (informational, for LLM schema).
    "required"   : bool  — Whether the LLM must provide this arg.
    "default"    : any   — Default used when LLM omits an optional arg (None = omit entirely).
    "help"       : str   — Description of the argument for LLM understanding.
  }
"""

from __future__ import annotations
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------
ArgDef = Dict[str, Any]
ToolDef = Dict[str, Any]

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
CLI_TOOLS: List[ToolDef] = [

    # -----------------------------------------------------------------------
    # OVERVIEW / HEALTH
    # -----------------------------------------------------------------------
    {
        "name": "drake_overview",
        "description": (
            "Display the executive overview dashboard of the entire Drake platform, "
            "showing total workflows, approvals, rejections, and system status at a glance."
        ),
        "command": ["overview"],
        "args": [],
    },
    {
        "name": "drake_health",
        "description": (
            "Show the platform subsystem health status matrix. Checks database, "
            "FastMCP proxy, compatibility engine, and Ollama connectivity."
        ),
        "command": ["health"],
        "args": [],
    },

    # -----------------------------------------------------------------------
    # CLUSTER
    # -----------------------------------------------------------------------
    {
        "name": "drake_cluster_run",
        "description": (
            "Ingest one or more OpenAPI specification files and run the full AI clustering "
            "pipeline. Discovers logical workflow groups from raw API endpoints using Leiden "
            "community detection and semantic embeddings. Saves results to governance.db."
        ),
        "command": ["cluster", "run"],
        "args": [
            {
                "name": "specs",
                "flag": "--specs",
                "positional": False,
                "type": "str",
                "required": False,
                "default": None,
                "help": "Path(s) to OpenAPI spec files or directories (e.g. openapi.json).",
            },
        ],
    },
    {
        "name": "drake_cluster_summary",
        "description": (
            "Display high-level operational statistics on discovered workflow clusters, "
            "including total endpoint count, number of clusters, and average confidence scores."
        ),
        "command": ["cluster", "summary"],
        "args": [],
    },
    {
        "name": "drake_cluster_graph",
        "description": (
            "Print relationship node and edge totals for the derived API relationship graph "
            "used by the Leiden clustering algorithm."
        ),
        "command": ["cluster", "graph"],
        "args": [],
    },

    # -----------------------------------------------------------------------
    # PIPELINE (full ingest → cluster → serve in one shot)
    # -----------------------------------------------------------------------
    {
        "name": "drake_pipeline",
        "description": (
            "Run the complete end-to-end Drake pipeline for a given OpenAPI spec: "
            "Ingest → Cluster → (optionally) auto-approve READ_ONLY workflows. "
            "This is the fastest way to onboard a new API specification."
        ),
        "command": ["pipeline"],
        "args": [
            {
                "name": "spec",
                "positional": True,
                "type": "str",
                "required": True,
                "default": None,
                "help": "Path to the OpenAPI spec file (YAML or JSON).",
            },
            {
                "name": "auto_approve",
                "flag": "--auto-approve",
                "positional": False,
                "type": "bool",
                "required": False,
                "default": None,
                "help": "If true, automatically approve all READ_ONLY (safe) workflows.",
            },
        ],
    },

    # -----------------------------------------------------------------------
    # GOVERNANCE
    # -----------------------------------------------------------------------
    {
        "name": "drake_governance_pending",
        "description": (
            "List all workflows that are awaiting human review and approval "
            "before they can be used as MCP tools by AI agents."
        ),
        "command": ["governance", "pending"],
        "args": [],
    },
    {
        "name": "drake_governance_approved",
        "description": (
            "List all certified and approved workflows that are currently "
            "registered and available for AI agent execution via MCP."
        ),
        "command": ["governance", "approved"],
        "args": [],
    },
    {
        "name": "drake_governance_rejected",
        "description": (
            "List all workflows that have been rejected by operators and "
            "are blocked from execution."
        ),
        "command": ["governance", "rejected"],
        "args": [],
    },
    {
        "name": "drake_governance_review",
        "description": (
            "Review detailed information about a specific workflow, including its "
            "constituent API steps, HTTP methods, URL paths, and parameters."
        ),
        "command": ["governance", "review"],
        "args": [
            {
                "name": "workflow_id",
                "positional": True,
                "type": "str",
                "required": True,
                "default": None,
                "help": "The unique ID of the workflow to review (e.g. wf_abc123).",
            },
        ],
    },
    {
        "name": "drake_governance_approve",
        "description": (
            "Approve a pending workflow by its ID, certifying it for runtime execution "
            "and registering it as an available MCP tool for AI agents."
        ),
        "command": ["governance", "approve"],
        "args": [
            {
                "name": "workflow_id",
                "positional": True,
                "type": "str",
                "required": True,
                "default": None,
                "help": "The unique ID of the workflow to approve.",
            },
        ],
    },
    {
        "name": "drake_governance_reject",
        "description": (
            "Reject a pending workflow by its ID, blocking it from execution and "
            "recording a safety reason in the governance audit ledger."
        ),
        "command": ["governance", "reject"],
        "args": [
            {
                "name": "workflow_id",
                "positional": True,
                "type": "str",
                "required": True,
                "default": None,
                "help": "The unique ID of the workflow to reject.",
            },
            {
                "name": "reason",
                "flag": "--reason",
                "positional": False,
                "type": "str",
                "required": False,
                "default": None,
                "help": "Human-readable reason for the rejection.",
            },
        ],
    },

    # -----------------------------------------------------------------------
    # COMPATIBILITY
    # -----------------------------------------------------------------------
    {
        "name": "drake_compatibility_validate",
        "description": (
            "Perform pre-flight compatibility verification of a workflow against a specific "
            "target server IP. Returns compatibility score, risk score, blast radius, and "
            "a pass/fail verdict (ALLOW/WARN/BLOCK)."
        ),
        "command": ["compatibility", "validate"],
        "args": [
            {
                "name": "workflow_id",
                "positional": True,
                "type": "str",
                "required": True,
                "default": None,
                "help": "The workflow ID to validate.",
            },
            {
                "name": "target_ip",
                "flag": "--target-ip",
                "positional": False,
                "type": "str",
                "required": False,
                "default": None,
                "help": "Target server iDRAC IP address (default: 192.168.0.120).",
            },
        ],
    },
    {
        "name": "drake_compatibility_dashboard",
        "description": (
            "Render the full compatibility decision cockpit for a workflow against a target "
            "server. Shows device facts, validation scores, violations, prerequisite dependency "
            "tree, and a final SAFE TO EXECUTE or BLOCK EXECUTION verdict."
        ),
        "command": ["compatibility", "dashboard"],
        "args": [
            {
                "name": "workflow_id",
                "positional": True,
                "type": "str",
                "required": True,
                "default": None,
                "help": "The workflow ID to check.",
            },
            {
                "name": "target_ip",
                "flag": "--target-ip",
                "positional": False,
                "type": "str",
                "required": False,
                "default": None,
                "help": "Target server iDRAC IP address.",
            },
        ],
    },
    {
        "name": "drake_compatibility_explain",
        "description": (
            "Render the topological DAG dependency tree of all compatibility rules "
            "that are evaluated when checking this workflow."
        ),
        "command": ["compatibility", "explain"],
        "args": [
            {
                "name": "workflow_id",
                "positional": True,
                "type": "str",
                "required": True,
                "default": None,
                "help": "The workflow ID to explain.",
            },
        ],
    },
    {
        "name": "drake_compatibility_rules",
        "description": (
            "Print the complete active compatibility rules catalog that governs "
            "pre-flight validation checks."
        ),
        "command": ["compatibility", "rules"],
        "args": [],
    },

    # -----------------------------------------------------------------------
    # RUNTIME
    # -----------------------------------------------------------------------
    {
        "name": "drake_runtime_tools",
        "description": (
            "List all dynamic MCP tools currently registered and exposed by the FastMCP "
            "proxy server, including their risk level and step count."
        ),
        "command": ["runtime", "tools"],
        "args": [],
    },
    {
        "name": "drake_runtime_reload",
        "description": (
            "Trigger a hot-reload of the FastMCP tool catalog, refreshing the available "
            "tools from the governance database without restarting the server."
        ),
        "command": ["runtime", "reload"],
        "args": [],
    },
    {
        "name": "drake_runtime_execute",
        "description": (
            "Manually execute a specific registered workflow directly against a target server "
            "IP, bypassing the AI agent selection step. Useful for testing workflows."
        ),
        "command": ["runtime", "execute"],
        "args": [
            {
                "name": "workflow_id",
                "positional": True,
                "type": "str",
                "required": True,
                "default": None,
                "help": "The workflow system name to execute.",
            },
            {
                "name": "target_ip",
                "flag": "--target-ip",
                "positional": False,
                "type": "str",
                "required": False,
                "default": None,
                "help": "Target server IP address.",
            },
            {
                "name": "params",
                "flag": "--params",
                "positional": False,
                "type": "str",
                "required": False,
                "default": None,
                "help": "JSON string of execution parameters, e.g. '{\"key\": \"value\"}'.",
            },
        ],
    },

    # -----------------------------------------------------------------------
    # AUDIT
    # -----------------------------------------------------------------------
    {
        "name": "drake_audit_events",
        "description": (
            "Print the governance security audit log — a ledger of all administrative "
            "events such as workflow approvals, rejections, and policy changes."
        ),
        "command": ["audit", "events"],
        "args": [],
    },
    {
        "name": "drake_audit_executions",
        "description": (
            "Print the complete historical workflow execution ledger, showing which workflows "
            "ran, against which servers, their status, and timestamps."
        ),
        "command": ["audit", "executions"],
        "args": [],
    },
    {
        "name": "drake_audit_summary",
        "description": (
            "Show a high-level compliance summary with aggregate counts of approvals, "
            "rejections, total executions, and security blocks triggered."
        ),
        "command": ["audit", "summary"],
        "args": [],
    },

    # -----------------------------------------------------------------------
    # ANSIBLE
    # -----------------------------------------------------------------------
    {
        "name": "drake_ansible_preview",
        "description": (
            "Render the enriched Ansible YAML playbook for a workflow with syntax highlighting. "
            "Shows the Infrastructure-as-Code representation of the workflow steps."
        ),
        "command": ["ansible", "preview"],
        "args": [
            {
                "name": "workflow_id",
                "positional": True,
                "type": "str",
                "required": True,
                "default": None,
                "help": "The workflow ID to generate the playbook for.",
            },
        ],
    },
    {
        "name": "drake_ansible_export",
        "description": (
            "Export the enriched Ansible playbook for a workflow to a local file on disk."
        ),
        "command": ["ansible", "export"],
        "args": [
            {
                "name": "workflow_id",
                "positional": True,
                "type": "str",
                "required": True,
                "default": None,
                "help": "The workflow ID to export.",
            },
            {
                "name": "output",
                "flag": "--output",
                "positional": False,
                "type": "str",
                "required": False,
                "default": None,
                "help": "File path to write the YAML playbook to (e.g. playbooks/deploy.yml).",
            },
        ],
    },

    # -----------------------------------------------------------------------
    # DIAGNOSTICS
    # -----------------------------------------------------------------------
    {
        "name": "drake_diagnostics_db",
        "description": (
            "Run database health check and integrity diagnostics for the governance SQLite "
            "database, verifying table presence, rules count, and index validity."
        ),
        "command": ["diagnostics", "db"],
        "args": [],
    },
    {
        "name": "drake_diagnostics_api",
        "description": (
            "Run API gateway network connection diagnostics, verifying port binding and "
            "FastAPI/FastMCP server availability."
        ),
        "command": ["diagnostics", "api"],
        "args": [],
    },
    {
        "name": "drake_diagnostics_compatibility",
        "description": (
            "Run compatibility engine diagnostics — checks table indexes, cached device facts, "
            "and rule catalog integrity."
        ),
        "command": ["diagnostics", "compatibility"],
        "args": [],
    },
    {
        "name": "drake_diagnostics_runtime",
        "description": (
            "Run FastMCP runtime diagnostics — lists registered MCP tools, total workflows, "
            "and API endpoint status."
        ),
        "command": ["diagnostics", "runtime"],
        "args": [],
    },

    # -----------------------------------------------------------------------
    # SYSTEM
    # -----------------------------------------------------------------------
    {
        "name": "drake_system_topology",
        "description": (
            "Print the complete datacenter subsystem topology and dependency mapping "
            "hierarchy — governance, compatibility, runtime, and executor layers."
        ),
        "command": ["system", "topology"],
        "args": [],
    },
]

# ---------------------------------------------------------------------------
# Helper: quick lookup by name
# ---------------------------------------------------------------------------
_REGISTRY_BY_NAME: Dict[str, ToolDef] = {t["name"]: t for t in CLI_TOOLS}


def get_tool(name: str) -> ToolDef | None:
    """Return a tool definition by its name, or None if not found."""
    return _REGISTRY_BY_NAME.get(name)


def get_all_names() -> List[str]:
    """Return a list of all registered CLI tool names."""
    return list(_REGISTRY_BY_NAME.keys())


def as_llm_schema() -> List[Dict[str, Any]]:
    """
    Return a compact representation of all CLI tools for inclusion in the
    LLM system prompt, similar to MCP tool schema format.
    """
    result = []
    for tool in CLI_TOOLS:
        props: Dict[str, Any] = {}
        required: List[str] = []
        for arg in tool["args"]:
            arg_key = arg["name"].lstrip("-").replace("-", "_")
            props[arg_key] = {
                "type": arg.get("type", "str"),
                "description": arg.get("help", ""),
            }
            if arg.get("required", False):
                required.append(arg_key)

        result.append({
            "name": tool["name"],
            "description": tool["description"],
            "inputSchema": {
                "type": "object",
                "properties": props,
                "required": required,
            },
        })
    return result
