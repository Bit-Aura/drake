"""
Risk Engine for computing rolling risk scores using exponential smoothing.
"""


class RiskEngine:
    """
    Computes temporal risk aggregation using exponential smoothing.
    Balances historical behavior with current threat indicators.
    """
    
    def __init__(self, alpha: float = 0.3):
        """
        Initialize risk engine.
        
        Args:
            alpha: Smoothing factor for current score (0-1).
                   Higher alpha = more weight on current score.
                   Default 0.3 means 70% historical, 30% current.
        """
        if not 0 <= alpha <= 1:
            raise ValueError("Alpha must be between 0 and 1")
        self.alpha = alpha
        self.beta = 1.0 - alpha
    
    def update_rolling_score(self, previous_mean: float, current_score: float) -> float:
        """
        Compute exponentially weighted moving average.
        
        Formula: rolling_mean = beta * previous_mean + alpha * current_score
        Where beta = 0.7, alpha = 0.3 (default)
        
        Args:
            previous_mean: Previous rolling average score
            current_score: Current fusion score from model
            
        Returns:
            Updated rolling mean score (0-1)
        """
        if not 0 <= current_score <= 1:
            raise ValueError("Current score must be between 0 and 1")
        if not 0 <= previous_mean <= 1:
            raise ValueError("Previous mean must be between 0 and 1")
        
        rolling_mean = self.beta * previous_mean + self.alpha * current_score
        
        # Ensure bounds due to floating point arithmetic
        return max(0.0, min(1.0, rolling_mean))
    
    def compute_risk_change(self, previous_mean: float, current_mean: float) -> float:
        """
        Calculate change in risk level.
        
        Args:
            previous_mean: Previous rolling score
            current_mean: Current rolling score
            
        Returns:
            Delta between current and previous (can be negative)
        """
        return current_mean - previous_mean
    
    def is_risk_increasing(self, previous_mean: float, current_mean: float, 
                          threshold: float = 0.0) -> bool:
        """
        Determine if risk is trending upward.
        
        Args:
            previous_mean: Previous rolling score
            current_mean: Current rolling score
            threshold: Minimum delta to consider as increase
            
        Returns:
            True if risk is increasing beyond threshold
        """
        delta = self.compute_risk_change(previous_mean, current_mean)
        return delta > threshold
