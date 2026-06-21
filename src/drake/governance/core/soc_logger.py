"""
SOC Logger for security event persistence and audit trails.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


class SOCLogger:
    """
    Structured logging system for security operations center.
    Writes events in JSON Lines format for analysis and compliance.
    """
    
    def __init__(self, log_file: str = "data/security_events.jsonl"):
        """
        Initialize SOC logger.
        
        Args:
            log_file: Path to JSONL log file (relative or absolute)
        """
        self.log_file = Path(log_file)
        self._ensure_log_directory()
    
    def _ensure_log_directory(self) -> None:
        """Create log directory if it doesn't exist."""
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def log_event(self, session_id: str, fusion_score: float, rolling_score: float,
                  velocity: float, tier: str, action: str, 
                  escalation_detected: bool = False,
                  additional_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Log security event to persistent storage.
        
        Args:
            session_id: Session identifier
            fusion_score: Raw model output score
            rolling_score: Exponentially smoothed score
            velocity: Score change rate
            tier: Assigned threat tier
            action: Recommended action
            escalation_detected: Whether escalation was detected
            additional_data: Optional metadata to include
        """
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session_id": session_id,
            "fusion_score": round(fusion_score, 4),
            "rolling_score": round(rolling_score, 4),
            "velocity": round(velocity, 4),
            "tier": tier,
            "action": action,
            "escalation_detected": escalation_detected
        }
        
        if additional_data:
            event.update(additional_data)
        
        self._write_event(event)
    
    def _write_event(self, event: Dict[str, Any]) -> None:
        """
        Append event to log file.
        
        Args:
            event: Event dictionary to write
        """
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event) + '\n')
        except Exception as e:
            # Fallback: print to stderr if file write fails
            print(f"[SOC_LOGGER_ERROR] Failed to write event: {e}", flush=True)
    
    def read_events(self, limit: Optional[int] = None) -> list:
        """
        Read events from log file.
        
        Args:
            limit: Maximum number of events to return (most recent first)
            
        Returns:
            List of event dictionaries
        """
        if not self.log_file.exists():
            return []
        
        events = []
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
        except Exception as e:
            print(f"[SOC_LOGGER_ERROR] Failed to read events: {e}", flush=True)
            return []
        
        if limit:
            return events[-limit:]
        return events
    
    def get_session_history(self, session_id: str) -> list:
        """
        Retrieve all events for specific session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of events for session
        """
        all_events = self.read_events()
        return [e for e in all_events if e.get("session_id") == session_id]
    
    def get_critical_events(self, tier: str = "CRITICAL") -> list:
        """
        Filter events by threat tier.
        
        Args:
            tier: Tier to filter by
            
        Returns:
            List of matching events
        """
        all_events = self.read_events()
        return [e for e in all_events if e.get("tier") == tier]
    
    def clear_logs(self) -> bool:
        """
        Delete log file (use with caution).
        
        Returns:
            True if file was deleted, False otherwise
        """
        try:
            if self.log_file.exists():
                os.remove(self.log_file)
                return True
        except Exception as e:
            print(f"[SOC_LOGGER_ERROR] Failed to clear logs: {e}", flush=True)
        return False
    
    def get_log_size(self) -> int:
        """
        Get log file size in bytes.
        
        Returns:
            File size or 0 if file doesn't exist
        """
        if self.log_file.exists():
            return self.log_file.stat().st_size
        return 0
