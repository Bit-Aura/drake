"""
Workflow Campaign Tracker
"""
from __future__ import annotations
import time
import logging
from collections import defaultdict
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

import yaml
from pathlib import Path

def _load_gov_config() -> Dict[str, Any]:
    try:
        path = Path(__file__).resolve().parent.parent / "config" / "governance_config.yaml"
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

class WorkflowCampaignTracker:
    """
    Detects when multiple individually safe workflows become collectively dangerous.
    Tracks velocity, target concentration, and destructive density over time to
    thwart workflow splitting and bulk change attacks.
    """
    def __init__(self, time_window_sec: int = None, max_events: int = None):
        self.gov_config = _load_gov_config()
        campaign_cfg = self.gov_config.get("campaign", {})
        
        self.time_window_sec = time_window_sec if time_window_sec is not None else campaign_cfg.get("time_window_sec", 600)
        self.max_events = max_events if max_events is not None else campaign_cfg.get("max_events", 2000)
        self.sessions: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.sessions: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    def track(self, session_id: str, workflow_id: str, endpoints: List[Dict[str, Any]], risk_score: float) -> Dict[str, Any]:
        now = time.time()
        self._cleanup(session_id, now)

        # Extract features
        categories = []
        targets = []
        for ep in endpoints:
            method = ep.get("method", "").upper()
            path = ep.get("endpoint", "")
            categories.append(method)
            
            # Simple heuristic for target extraction
            parts = [p for p in path.split("/") if p]
            if len(parts) >= 2:
                targets.append(parts[-1]) # often ID

        event = {
            "timestamp": now,
            "workflow_id": workflow_id,
            "categories": categories,
            "targets": targets,
            "risk_score": risk_score,
            "signature": hash("".join(sorted(categories)))
        }
        self.sessions[session_id].append(event)
        
        return self._evaluate(session_id)

    def _cleanup(self, session_id: str, now: float) -> None:
        valid = [e for e in self.sessions[session_id] if now - e["timestamp"] <= self.time_window_sec]
        if len(valid) > self.max_events:
            valid = valid[-self.max_events:]
        self.sessions[session_id] = valid

    def _evaluate(self, session_id: str) -> Dict[str, Any]:
        events = self.sessions[session_id]
        if len(events) < 2:
            return {"campaign_risk": 0.0, "is_campaign": False}

        cumulative_risk = sum(e["risk_score"] for e in events)
        
        # Calculate destructive action density
        destructive_count = sum(1 for e in events for c in e["categories"] if c in {"DELETE", "PATCH", "POST", "PUT"})
        total_actions = sum(len(e["categories"]) for e in events)
        density = (destructive_count / total_actions) if total_actions > 0 else 0

        # Target concentration
        all_targets = [t for e in events for t in e["targets"]]
        unique_targets = len(set(all_targets))
        # if targets are mostly unique, it's a bulk operation on fleet
        # if targets are exactly the same, it's hammer attack on one target
        # Both are signs of campaign if density/velocity is high
        
        # Similarity (same signatures repeatedly)
        signatures = [e["signature"] for e in events]
        similarity = 1.0 - (len(set(signatures)) / len(signatures))

        # Velocity
        duration = events[-1]["timestamp"] - events[0]["timestamp"]
        velocity = len(events) / max(1.0, duration)

        campaign_cfg = self.gov_config.get("campaign", {})
        c_risk_coeff = campaign_cfg.get("cumulative_risk_coefficient", 0.3)
        density_coeff = campaign_cfg.get("density_coefficient", 30.0)
        sim_coeff = campaign_cfg.get("similarity_coefficient", 20.0)
        vel_coeff = campaign_cfg.get("velocity_coefficient", 2.0)
        
        # Synthesize campaign risk using relative metrics rather than hardcoded sizes
        campaign_risk = (cumulative_risk * c_risk_coeff) + (density * density_coeff) + (similarity * sim_coeff) + (velocity * vel_coeff)
        
        normalized = min(1.0, campaign_risk / 100.0)

        is_campaign = normalized >= campaign_cfg.get("threshold", 0.65)

        if is_campaign:
            logger.warning(f"Campaign detected in session {session_id}! Score: {normalized:.2f}")

        return {
            "campaign_risk": normalized,
            "is_campaign": is_campaign,
            "cumulative_risk": cumulative_risk,
            "density": density,
            "velocity": velocity
        }
