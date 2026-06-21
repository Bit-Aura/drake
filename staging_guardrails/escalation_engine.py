"""
Escalation Engine for detecting rapid threat velocity increases.
"""
from typing import Tuple


class EscalationEngine:
    """
    Detects threat escalation patterns by monitoring velocity changes.
    Tracks consecutive increases to identify attack progression.
    """
    
    def __init__(self, velocity_threshold: float = 0.15, escalation_limit: int = 3):
        """
        Initialize escalation engine.
        
        Args:
            velocity_threshold: Minimum velocity to count as escalation
            escalation_limit: Consecutive escalations to trigger alert
        """
        self.velocity_threshold = velocity_threshold
        self.escalation_limit = escalation_limit
    
    def compute_velocity(self, current_score: float, last_score: float) -> float:
        """
        Calculate rate of score change.
        
        Args:
            current_score: Current fusion score
            last_score: Previous fusion score
            
        Returns:
            Velocity (delta between scores)
        """
        return current_score - last_score
    
    def detect_escalation(self, current_score: float, last_score: float, 
                          current_escalation_count: int) -> Tuple[bool, float, int]:
        """
        Analyze velocity and update escalation tracking.
        
        Rules:
        - If velocity > threshold: increment escalation count
        - If velocity <= threshold: reset escalation count to 0
        - If escalation_count >= limit: escalation detected
        
        Args:
            current_score: Current fusion score
            last_score: Previous fusion score
            current_escalation_count: Current escalation counter
            
        Returns:
            Tuple of (escalation_detected, velocity, updated_escalation_count)
        """
        velocity = self.compute_velocity(current_score, last_score)
        
        if velocity > self.velocity_threshold:
            # Escalation detected, increment counter
            updated_count = current_escalation_count + 1
        else:
            # No escalation, reset counter
            updated_count = 0
        
        # Check if threshold reached
        escalation_detected = updated_count >= self.escalation_limit
        
        return escalation_detected, velocity, updated_count
    
    def is_rapid_escalation(self, velocity: float) -> bool:
        """
        Check if velocity indicates rapid escalation.
        
        Args:
            velocity: Computed velocity
            
        Returns:
            True if velocity exceeds threshold
        """
        return velocity > self.velocity_threshold
    
    def get_escalation_severity(self, escalation_count: int) -> str:
        """
        Classify escalation severity.
        
        Args:
            escalation_count: Current escalation counter
            
        Returns:
            Severity level string
        """
        if escalation_count == 0:
            return "NONE"
        elif escalation_count < self.escalation_limit:
            return "MODERATE"
        else:
            return "SEVERE"
