# HARDCODED LOGIC AUDIT

## Objective
Detect fixed thresholds, magic numbers, or strict endpoint names that compromise dynamic adaptability.

### `WorkflowCampaignTracker` (src/governance/runtime/workflow_campaign_tracker.py)
* **Finding**: `time_window_sec = 600`, `max_events = 2000`
* **Justification**: Memory and context bounds for tracking. (Severity: **LOW**)
* **Finding**: Hardcoded HTTP methods check `{"DELETE", "PATCH", "POST", "PUT"}` to calculate density.
* **Justification**: HTTP methods are universal standards, not hardcoded custom workflow names. (Severity: **LOW**)
* **Finding**: Evaluation threshold `normalized >= 0.65`.
* **Justification**: A tuning parameter, though ideally adjustable via external config rather than class constants. (Severity: **MEDIUM**)

### `RiskAssessor` (src/governance/core/risk.py)
* **Finding**: Default asset assumption `total_assets = fleet_context.get("total_assets", 100)`.
* **Justification**: Necessary fallback if system context isn't passed, but 100 could cause over/under scaling on tiny or massive clusters. (Severity: **MEDIUM**)
* **Finding**: Risk score bump constants (`+50.0` for DELETE, `+30.0` for PATCH).
* **Justification**: Standardized scoring weights. These are overrideable via the `policy_config` dictionary injected on init. (Severity: **LOW**)
* **Finding**: Hardcoded Risk Levels `CRITICAL (>= 80)`, `HIGH (>= 50)`, `MEDIUM (>= 20)`.
* **Justification**: Bounded bucketing. (Severity: **LOW**)

## Conclusion
**Severity Level:** **LOW-MEDIUM**
No fixed workflow names (`if workflow == "DeleteServer"`) exist in the new integrations. The system categorizes actions purely by HTTP verbs (`DELETE`, `PATCH`) and scales using relative target comparisons (`unique_targets / total_assets`), ensuring it natively supports future, undiscovered workflows.
