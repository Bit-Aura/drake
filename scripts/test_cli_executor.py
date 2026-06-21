"""
Hard-input test suite for cli_executor.py
Tests command building logic without running actual subprocesses.
"""
import sys, os
# Force UTF-8 output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('scripts'))

from scripts.cli_executor import build_command, validate_cli_arguments, _resolve_python
from scripts.cli_tool_registry import get_tool

PASS = 0
FAIL = 0

def check(label, condition, got=None):
    global PASS, FAIL
    if condition:
        print(f"  [PASS] {label}")
        PASS += 1
    else:
        print(f"  [FAIL] {label}  got={got!r}")
        FAIL += 1

# ─────────────────────────────────────────────────────────────────
# 1. No-arg commands
# ─────────────────────────────────────────────────────────────────
print("\n[1] No-argument commands:")
for tool_name in ["drake_health", "drake_overview", "drake_cluster_summary",
                  "drake_governance_pending", "drake_audit_events", "drake_system_topology"]:
    t = get_tool(tool_name)
    cmd = build_command(t, {})
    expected_suffix = t["command"]
    # Must end with the subcommand tokens and include --json
    check(f"{tool_name} -> ends with {expected_suffix}",
          cmd[-len(expected_suffix):] == expected_suffix and "--json" in cmd, got=cmd)

# ─────────────────────────────────────────────────────────────────
# 2. Positional-only args
# ─────────────────────────────────────────────────────────────────
print("\n[2] Positional args:")
t = get_tool("drake_governance_approve")
cmd = build_command(t, {"workflow_id": "wf_abc123"})
check("governance approve -> workflow_id positional", "wf_abc123" in cmd, got=cmd)
check("governance approve -> no --workflow_id flag", "--workflow_id" not in cmd, got=cmd)

t = get_tool("drake_governance_review")
cmd = build_command(t, {"workflow_id": "test_wf_1"})
check("governance review -> test_wf_1 in args", "test_wf_1" in cmd, got=cmd)

# ─────────────────────────────────────────────────────────────────
# 3. Flagged optional args
# ─────────────────────────────────────────────────────────────────
print("\n[3] Flagged args:")
t = get_tool("drake_compatibility_validate")
cmd = build_command(t, {"workflow_id": "wf_001", "target_ip": "10.0.0.5"})
check("compat validate -> workflow_id positional", "wf_001" in cmd, got=cmd)
check("compat validate -> --target-ip flag present", "--target-ip" in cmd, got=cmd)
check("compat validate -> IP value present", "10.0.0.5" in cmd, got=cmd)

t = get_tool("drake_governance_reject")
cmd = build_command(t, {"workflow_id": "wf_bad", "reason": "Security violation"})
check("governance reject -> wf_bad positional", "wf_bad" in cmd, got=cmd)
check("governance reject -> --reason flag", "--reason" in cmd, got=cmd)
check("governance reject -> reason value", "Security violation" in cmd, got=cmd)

# ─────────────────────────────────────────────────────────────────
# 4. Omitted optional args (should not appear in cmd)
# ─────────────────────────────────────────────────────────────────
print("\n[4] Optional args omitted when not provided:")
t = get_tool("drake_compatibility_validate")
cmd = build_command(t, {"workflow_id": "wf_001"})  # no target_ip
check("compat validate without target_ip -> --target-ip absent", "--target-ip" not in cmd, got=cmd)

t = get_tool("drake_governance_reject")
cmd = build_command(t, {"workflow_id": "wf_x"})  # no reason
check("governance reject without reason -> --reason absent", "--reason" not in cmd, got=cmd)

# ─────────────────────────────────────────────────────────────────
# 5. Boolean flag arg
# ─────────────────────────────────────────────────────────────────
print("\n[5] Boolean flags:")
t = get_tool("drake_pipeline")
cmd = build_command(t, {"spec": "openapi.json", "auto_approve": True})
check("pipeline -> spec positional", "openapi.json" in cmd, got=cmd)
check("pipeline --auto-approve -> flag present when True", "--auto-approve" in cmd, got=cmd)

cmd2 = build_command(t, {"spec": "openapi.json", "auto_approve": False})
check("pipeline --auto-approve -> flag absent when False", "--auto-approve" not in cmd2, got=cmd2)

cmd3 = build_command(t, {"spec": "openapi.json"})  # not given
check("pipeline --auto-approve -> flag absent when omitted", "--auto-approve" not in cmd3, got=cmd3)

# ─────────────────────────────────────────────────────────────────
# 6. LLM key normalization (LLM sends "target_ip" not "--target-ip")
# ─────────────────────────────────────────────────────────────────
print("\n[6] LLM key normalization:")
t = get_tool("drake_compatibility_validate")
cmd = build_command(t, {"workflow_id": "wf_x", "target_ip": "192.168.1.1"})
check("underscore key -> --target-ip flag present", "--target-ip" in cmd, got=cmd)
check("underscore key -> IP value present", "192.168.1.1" in cmd, got=cmd)

# ─────────────────────────────────────────────────────────────────
# 7. validate_cli_arguments
# ─────────────────────────────────────────────────────────────────
print("\n[7] Argument validation:")
ok, msg = validate_cli_arguments("drake_governance_approve", {"workflow_id": "wf_1"})
check("validate approve with workflow_id -> OK", ok, got=msg)

ok, msg = validate_cli_arguments("drake_governance_approve", {})
check("validate approve without workflow_id -> FAIL", not ok, got=msg)

ok, msg = validate_cli_arguments("drake_health", {})
check("validate health (no args required) -> OK", ok, got=msg)

ok, msg = validate_cli_arguments("drake_pipeline", {"spec": "openapi.json"})
check("validate pipeline with spec -> OK", ok, got=msg)

ok, msg = validate_cli_arguments("drake_pipeline", {})
check("validate pipeline without spec -> FAIL", not ok, got=msg)

ok, msg = validate_cli_arguments("nonexistent_tool", {})
check("validate unknown tool -> FAIL", not ok, got=msg)

# ─────────────────────────────────────────────────────────────────
# 8. Python resolver
# ─────────────────────────────────────────────────────────────────
print("\n[8] Python resolver:")
py = _resolve_python()
check("resolver returns a string", isinstance(py, str), got=py)
check("resolver result contains 'python'", "python" in py.lower(), got=py)
print(f"  Resolved: {py}")

# ─────────────────────────────────────────────────────────────────
# 9. --json always in command
# ─────────────────────────────────────────────────────────────────
print("\n[9] --json always present:")
for tool_name in ["drake_health", "drake_cluster_run", "drake_governance_approve"]:
    t = get_tool(tool_name)
    args = {"workflow_id": "wf_1", "specs": "openapi.json"}
    cmd = build_command(t, args)
    check(f"{tool_name} -> --json in command", "--json" in cmd, got=cmd)

# ─────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"  RESULTS: {PASS} passed, {FAIL} failed")
if FAIL:
    sys.exit(1)
else:
    print("  ALL TESTS PASSED ✓")
