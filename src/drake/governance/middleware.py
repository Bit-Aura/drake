import logging
from typing import Dict, Any, List

from src.drake.governance.core.policy import PolicyEngine
from src.drake.governance.core.risk import RiskAssessor
from src.drake.governance.core.validator import WorkflowValidator
from src.drake.governance.runtime.interceptor import RuntimeGovernance
from src.drake.governance.runtime.workflow_campaign_tracker import WorkflowCampaignTracker
from src.drake.governance.ai_guardrails.prefilter import FastPreFilter
from src.drake.core.database import log_audit_event

logger = logging.getLogger(__name__)

class GovernanceMiddleware:  # noqa: E302
    """Facade for the Governance Layer."""

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.policy_engine = PolicyEngine()
        self.validator = WorkflowValidator()
        self.prefilter = FastPreFilter()
        self.risk_assessor = RiskAssessor(self.policy_engine.get_config())
        self.campaign_tracker = WorkflowCampaignTracker()
        self.runtime = RuntimeGovernance(self.policy_engine.get_config())

    def process_new_workflows(self, workflows: List[Dict[str, Any]], endpoints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:  # noqa: E501
        """
        Intercepts workflows before persistence.
        Applies validation, risk assessment, and policy rules.
        Modifies the 'approved' and 'risk_level' fields in place.
        """
        # Map endpoints by operation_id for quick lookup
        endpoint_map = {ep["operation_id"]: ep for ep in endpoints}  # noqa: F841

        for wf in workflows:
            wf_id = wf.get("id")
            comm_id = wf.get("community_id", wf_id)

            # Find underlying endpoints (assuming direct map or via community_id)
            underlying = [ep for ep in endpoints if ep.get("community_id") == comm_id or ep.get("operation_id") == wf_id]  # noqa: E501

            # 1. Validation
            val_result = self.validator.validate(wf, underlying)
            if not val_result["is_valid"]:
                wf["approved"] = 2 # Rejected  # noqa: E261
                wf["rejection_reason"] = "Validation failed: " + ", ".join(val_result["errors"])
                continue

            # 1b. Prefilter (AI Guardrails)
            prompt_to_check = f"{wf.get('display_name', '')} {wf.get('generated_description', '')}"
            pf_result = self.prefilter.check(prompt_to_check)
            if pf_result.blocked:
                wf["approved"] = 2 # Rejected
                wf["rejection_reason"] = f"AI Guardrail Block: {pf_result.reason} ({pf_result.matched_pattern})"
                log_audit_event(
                    event_type="PREFILTER_BLOCK",
                    status="BLOCKED",
                    description=wf["rejection_reason"],
                    workflow_name=wf_id,
                    actor="system",
                    metadata={"violations": pf_result.violations}
                )
                logger.warning(f"Governance Middleware: Workflow {wf_id} blocked by Prefilter.")
                continue

            # 2. Risk Assessment
            risk_result = self.risk_assessor.assess_risk(underlying)
            
            # 2b. Campaign Tracking
            session_id = wf.get("session_id", "default_session")
            campaign_result = self.campaign_tracker.track(
                session_id=session_id, 
                workflow_id=wf_id, 
                endpoints=underlying, 
                risk_score=risk_result.get("risk_score", 0.0)
            )

            # Upgrade risk if campaign detected
            if campaign_result["is_campaign"]:
                risk_result["risk_level"] = "CRITICAL"
                logger.warning(f"Governance Middleware: Campaign detected! Upgraded workflow {wf_id} risk to CRITICAL.")

            wf["risk_level"] = risk_result["risk_level"]
            wf["risk_score"] = risk_result.get("risk_score", 0.0)
            wf["governance_score"] = risk_result.get("governance_score", 100.0)
            wf["campaign_risk"] = campaign_result["campaign_risk"]
            # Policy Version injection
            wf["policy_version"] = self.policy_engine.get_config().get("version", "1.0")

            # 3. Policy Evaluation
            actions = [ep.get("method", "").upper() for ep in underlying]
            context = {
                "risk_level": risk_result["risk_level"],
                "is_read_only": risk_result["is_read_only"],
                "actions": actions,
                "is_bulk": len(underlying) > 1,
            }

            policy_result = self.policy_engine.evaluate(context)

            # Only update approved status if the workflow wasn't manually set by user before
            # For new workflows, approved is likely 0 initially or not set
            if wf.get("approved", 0) == 0:
                wf["approved"] = policy_result["status"]
                wf["rejection_reason"] = policy_result["reason"] or risk_result.get("risk_explanation")  # noqa: E501

                status_str = {0: "PENDING", 1: "AUTO_APPROVED", 2: "DENIED"}.get(wf["approved"], "UNKNOWN")  # noqa: E501
                logger.info(f"Governance Middleware: Workflow {wf_id} classified as {wf['risk_level']}, state set to {status_str}")  # noqa: E501

        return workflows

    def intercept_execution(self, workflow_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runtime hook for execution.
        Raises exception if blocked, returns masked params.
        """
        logger.info(f"Governance Middleware: Intercepting execution for {workflow_name}")
        masked = self.runtime.intercept(workflow_name, params)
        return masked
