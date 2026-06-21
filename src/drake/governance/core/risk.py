from typing import Dict, Any, List, Optional

import yaml
from pathlib import Path

def _load_gov_config() -> Dict[str, Any]:
    try:
        path = Path(__file__).resolve().parent.parent / "config" / "governance_config.yaml"
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

class RiskAssessor:  # noqa: E302
    """Classifies risk levels of workflows based on actions and keywords."""

    def __init__(self, policy_config: Dict[str, Any]):
        self.gov_config = _load_gov_config()
        
        self.config = policy_config.get("risk_classification", {})
        self.high_risk_methods = set(self.config.get("high_risk_methods", ["DELETE", "PATCH", "PUT"]))
        self.high_risk_keywords = set(self.gov_config.get("keyword_weights", {"reboot": 40.0, "power": 40.0, "firmware": 40.0, "reset": 40.0, "format": 40.0}).keys())
        self.read_only_methods = set(self.config.get("read_only_methods", ["GET", "HEAD"]))

    def assess_risk(self, endpoints: List[Dict[str, Any]], fleet_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyzes a list of endpoints and determines the risk level, risk score, and governance score.
        Incorporates Relative Impact Analysis by calculating dynamic blast radius.
        Returns a dict with 'risk_level', 'is_read_only', 'risk_score', 'governance_score', 'risk_explanation'.
        """
        fleet_context = fleet_context or {}
        if not endpoints:
            return {
                "risk_level": "LOW",
                "is_read_only": True,
                "risk_score": 0.0,
                "governance_score": 100.0,
                "risk_explanation": "Empty workflow"
            }

        risk_score = 0.0
        explanations = []
        has_schemas = True

        for ep in endpoints:
            method = ep.get("method", "").upper()
            url = ep.get("url", "").lower()

            # Simple check for schemas if available (for governance score)
            if "request_schema" in ep and not ep.get("request_schema") and not ep.get("response_schema"):  # noqa: E501
                has_schemas = False

            risk_weights = self.gov_config.get("risk_weights", {})
            if method == "DELETE":
                val = risk_weights.get("DELETE", 50.0)
                risk_score += val
                explanations.append(f"Contains DELETE method for {url} (+{val})")
            elif method in ["PATCH", "PUT"]:
                val = risk_weights.get("PATCH", 30.0)
                risk_score += val
                explanations.append(f"Contains {method} method for {url} (+{val})")
            elif method in ["POST"]:
                val = risk_weights.get("POST", 20.0)
                risk_score += val
                explanations.append(f"Contains POST method for {url} (+{val})")
                
            keyword_weights = self.gov_config.get("keyword_weights", {})
            for keyword in self.high_risk_keywords:
                if keyword in url:
                    val = keyword_weights.get(keyword, 40.0)
                    risk_score += val
                    explanations.append(f"Contains high-risk keyword '{keyword}' in {url} (+{val})")

        # Feature 2: Relative Impact Analysis (Blast Radius)
        targets = []
        for ep in endpoints:
            url_str = ep.get("url") or ep.get("endpoint") or ""
            parts = [p for p in url_str.split("/") if p]
            if len(parts) >= 2:
                targets.append(parts[-1])
                
        unique_targets = len(set(targets))
        blast_config = self.gov_config.get("blast_radius", {})
        total_assets = fleet_context.get("total_assets", blast_config.get("default_total_assets", 100))
        
        blast_radius_ratio = min(1.0, unique_targets / max(1, total_assets))
        blast_multiplier = 1.0 + (blast_radius_ratio * blast_config.get("multiplier_coefficient", 3.0))
        
        if unique_targets > 1:
            explanations.append(f"Blast radius: {unique_targets} targets (multiplier: {blast_multiplier:.2f}x)")
            
        risk_score *= blast_multiplier

        risk_levels = self.gov_config.get("risk_levels", {})
        
        # Cap risk score at cap
        risk_score = min(risk_score, risk_levels.get("cap", 100.0))
        methods = {ep.get("method", "").upper() for ep in endpoints}
        is_read_only = all(m in self.read_only_methods for m in methods)

        if is_read_only:
            risk_level = "LOW"
            if risk_score == 0.0:
                explanations.append("Workflow is read-only")
        elif risk_score >= risk_levels.get("critical_min", 80.0):
            risk_level = "CRITICAL"
        elif risk_score >= risk_levels.get("high_min", 50.0):
            risk_level = "HIGH"
        elif risk_score >= risk_levels.get("medium_min", 20.0):
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        # Governance Score (0-100)
        # Base is 100. Deduct for high risk. Deduct if missing schemas. Add for well documented.
        gov_rules = self.gov_config.get("governance_score", {})
        gov_score = 100.0 - (risk_score * gov_rules.get("risk_deduction_coefficient", 0.5))
        if not has_schemas:
            pen = gov_rules.get("missing_schema_penalty", 20.0)
            gov_score -= pen
            explanations.append(f"Missing request/response schemas (-{pen} gov score)")
            # Alternate config block removed
        if is_read_only:
            gov_score = min(gov_score + gov_rules.get("read_only_bonus", 10.0), 100.0)

        gov_score = max(0.0, min(100.0, gov_score))

        return {
            "risk_level": risk_level,
            "is_read_only": is_read_only,
            "risk_score": risk_score,
            "governance_score": gov_score,
            "risk_explanation": "; ".join(explanations)
        }
