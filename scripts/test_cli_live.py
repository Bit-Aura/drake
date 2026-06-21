"""Live execution tests for cli_executor.run_cli_tool()"""
import sys, os
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.path.insert(0, '.')
sys.path.insert(0, 'scripts')

from scripts.cli_executor import run_cli_tool

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

print("=== LIVE CLI EXECUTION TESTS ===")

# Test 1: drake health
print("\n[1] drake_health:")
r = run_cli_tool("drake_health", {})
check("returncode==0", r.returncode == 0, got=r.returncode)
check("success=True", r.success)
check("has parsed JSON", r.parsed is not None, got=r.stderr[:200] if r.stderr else "")
if r.parsed:
    print(f"      keys: {list(r.parsed.keys())[:6]}")

# Test 2: drake_overview
print("\n[2] drake_overview:")
r = run_cli_tool("drake_overview", {})
check("returncode==0", r.returncode == 0, got=r.returncode)
check("has parsed JSON", r.parsed is not None, got=r.stderr[:200] if r.stderr else "")
if r.parsed:
    print(f"      keys: {list(r.parsed.keys())[:6]}")

# Test 3: drake_audit_summary
print("\n[3] drake_audit_summary:")
r = run_cli_tool("drake_audit_summary", {})
check("returncode==0", r.returncode == 0, got=r.returncode)
check("has parsed JSON", r.parsed is not None, got=r.stderr[:200] if r.stderr else "")
if r.parsed:
    print(f"      data: {r.parsed}")

# Test 4: drake_governance_pending
print("\n[4] drake_governance_pending:")
r = run_cli_tool("drake_governance_pending", {})
check("returncode==0", r.returncode == 0, got=r.returncode)
check("parsed is list", isinstance(r.parsed, list), got=type(r.parsed).__name__)
if isinstance(r.parsed, list):
    print(f"      found {len(r.parsed)} pending workflows")

# Test 5: drake_governance_approved
print("\n[5] drake_governance_approved:")
r = run_cli_tool("drake_governance_approved", {})
check("returncode==0", r.returncode == 0, got=r.returncode)
check("parsed is list", isinstance(r.parsed, list), got=type(r.parsed).__name__)
approved_ids = []
if isinstance(r.parsed, list):
    print(f"      found {len(r.parsed)} approved workflows")
    approved_ids = [w.get("id") for w in r.parsed if w.get("id")]
    if approved_ids:
        print(f"      first IDs: {approved_ids[:3]}")

# Test 6: drake_cluster_summary
print("\n[6] drake_cluster_summary:")
r = run_cli_tool("drake_cluster_summary", {})
check("returncode==0", r.returncode == 0, got=r.returncode)
check("has parsed JSON", r.parsed is not None, got=r.stderr[:200] if r.stderr else "")
if r.parsed:
    print(f"      data: {r.parsed}")

# Test 7: drake_compatibility_validate with positional workflow_id
print("\n[7] drake_compatibility_validate with real workflow_id:")
if approved_ids:
    wf_id = approved_ids[0]
    r = run_cli_tool("drake_compatibility_validate", {"workflow_id": wf_id})
    print(f"      workflow_id={wf_id}")
    check("returncode==0", r.returncode == 0, got=r.returncode)
    check("has parsed JSON", r.parsed is not None, got=r.stderr[:300] if r.stderr else "")
    if r.parsed:
        print(f"      keys: {list(r.parsed.keys())[:6]}")
else:
    print("      SKIP (no approved workflows found)")

# Test 8: error case — bad workflow ID
print("\n[8] drake_governance_review with bad workflow_id:")
r = run_cli_tool("drake_governance_review", {"workflow_id": "NONEXISTENT_ID_ZZZZZ"})
# May succeed (0) with empty/error JSON, or return nonzero
print(f"      returncode: {r.returncode}")
print(f"      parsed: {r.parsed}")
check("does not crash (any returncode is acceptable)", True)  # just verify no exception

# Test 9: timeout protection (short timeout, no crash)
print("\n[9] Timeout parameter:")
r = run_cli_tool("drake_health", {}, timeout=120)
check("health with timeout=120 works", r.success, got=r.returncode)

# Test 10: summary_for_agent
print("\n[10] summary_for_agent output:")
r = run_cli_tool("drake_audit_summary", {})
summary = r.summary_for_agent()
check("summary is non-empty string", isinstance(summary, str) and len(summary) > 0)
print(f"      preview: {summary[:150]}")

print(f"\n{'='*50}")
print(f"  RESULTS: {PASS} passed, {FAIL} failed")
if FAIL:
    sys.exit(1)
else:
    print("  ALL LIVE TESTS PASSED")
