"""
Policy Engine for threat tier assignment and action recommendation.
"""
from typing import Tuple


class PolicyEngine:
    """
    Maps risk scores to threat tiers and enforcement actions.
    Implements defense policy with escalation override logic.
    """
    
    # Tier thresholds
    SAFE_THRESHOLD = 0.30
    SUSPICIOUS_THRESHOLD = 0.60
    HIGH_THRESHOLD = 0.80
    
    # Tier names
    TIER_SAFE = "SAFE"
    TIER_SUSPICIOUS = "SUSPICIOUS"
    TIER_HIGH = "HIGH"
    TIER_CRITICAL = "CRITICAL"
    
    # Action mapping
    ACTION_ALLOW = "ALLOW"
    ACTION_MONITOR = "MONITOR"
    ACTION_RATE_LIMIT = "RATE_LIMIT"
    ACTION_BLOCK = "BLOCK"
    
    def __init__(self):
        """Initialize policy engine with default mappings."""
        self._policy_map = {
            self.TIER_SAFE: self.ACTION_ALLOW,
            self.TIER_SUSPICIOUS: self.ACTION_MONITOR,
            self.TIER_HIGH: self.ACTION_RATE_LIMIT,
            self.TIER_CRITICAL: self.ACTION_BLOCK
        }
    
    def assign_tier(self, rolling_score: float) -> str:
        """
        Assign threat tier based on rolling risk score.
        
        Tier Boundaries:
        - score < 0.30 → SAFE
        - 0.30 ≤ score < 0.60 → SUSPICIOUS
        - 0.60 ≤ score < 0.80 → HIGH
        - score ≥ 0.80 → CRITICAL
        
        Args:
            rolling_score: Exponentially smoothed risk score (0-1)
            
        Returns:
            Tier classification string
        """
        if rolling_score < self.SAFE_THRESHOLD:
            return self.TIER_SAFE
        elif rolling_score < self.SUSPICIOUS_THRESHOLD:
            return self.TIER_SUSPICIOUS
        elif rolling_score < self.HIGH_THRESHOLD:
            return self.TIER_HIGH
        else:
            return self.TIER_CRITICAL
    
    def apply_escalation_override(self, base_tier: str, escalation_detected: bool) -> str:
        """
        Upgrade tier to CRITICAL if escalation detected.
        
        Args:
            base_tier: Tier from score-based assignment
            escalation_detected: Whether escalation pattern detected
            
        Returns:
            Final tier (upgraded if escalation)
        """
        if escalation_detected:
            return self.TIER_CRITICAL
        return base_tier
    
    def get_recommended_action(self, tier: str) -> str:
        """
        Map threat tier to enforcement action.
        
        Args:
            tier: Threat tier classification
            
        Returns:
            Recommended security action
        """
        return self._policy_map.get(tier, self.ACTION_BLOCK)
    
    def evaluate_policy(self, rolling_score: float, escalation_detected: bool) -> Tuple[str, str]:
        """
        Complete policy evaluation pipeline.
        
        Args:
            rolling_score: Smoothed risk score
            escalation_detected: Escalation flag
            
        Returns:
            Tuple of (tier, recommended_action)
        """
        base_tier = self.assign_tier(rolling_score)
        final_tier = self.apply_escalation_override(base_tier, escalation_detected)
        action = self.get_recommended_action(final_tier)
        
        return final_tier, action
    
    def set_custom_policy(self, tier: str, action: str) -> None:
        """
        Override default policy mapping.
        
        Args:
            tier: Threat tier
            action: Custom action to apply
        """
        if tier in [self.TIER_SAFE, self.TIER_SUSPICIOUS, self.TIER_HIGH, self.TIER_CRITICAL]:
            self._policy_map[tier] = action
        else:
            raise ValueError(f"Invalid tier: {tier}")
    
    def get_policy_map(self) -> dict:
        """Return current policy mappings."""
        return self._policy_map.copy()
