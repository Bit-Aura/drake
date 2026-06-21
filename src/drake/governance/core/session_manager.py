"""
Session Manager for tracking user sessions and their security metrics.
"""
from datetime import datetime
from typing import Dict, Any


class SessionData:
    """Container for session-level security metrics."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.message_count = 0
        self.rolling_mean = 0.0
        self.last_score = 0.0
        self.velocity = 0.0
        self.escalation_count = 0
        self.tier = "SAFE"
        self.first_seen = datetime.utcnow()
        self.last_seen = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session data to dictionary format."""
        return {
            "session_id": self.session_id,
            "message_count": self.message_count,
            "rolling_mean": self.rolling_mean,
            "last_score": self.last_score,
            "velocity": self.velocity,
            "escalation_count": self.escalation_count,
            "tier": self.tier,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat()
        }


class SessionManager:
    """
    In-memory session storage and management.
    Tracks security metrics per session without external dependencies.
    """
    
    def __init__(self):
        self._sessions: Dict[str, SessionData] = {}
    
    def get_or_create(self, session_id: str) -> SessionData:
        """
        Retrieve existing session or create new one.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            SessionData instance
        """
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionData(session_id)
        else:
            self._sessions[session_id].last_seen = datetime.utcnow()
        
        return self._sessions[session_id]
    
    def update_session(self, session_id: str, **kwargs) -> None:
        """
        Update session attributes.
        
        Args:
            session_id: Session identifier
            **kwargs: Attributes to update
        """
        session = self.get_or_create(session_id)
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)
        session.last_seen = datetime.utcnow()
    
    def get_session(self, session_id: str) -> SessionData:
        """
        Retrieve session without creating.
        
        Args:
            session_id: Session identifier
            
        Returns:
            SessionData or None if not exists
        """
        return self._sessions.get(session_id)
    
    def clear_session(self, session_id: str) -> bool:
        """
        Remove session from storage.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was removed, False if not found
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False
    
    def get_all_sessions(self) -> Dict[str, SessionData]:
        """Return all active sessions."""
        return self._sessions.copy()
    
    def session_count(self) -> int:
        """Return total number of active sessions."""
        return len(self._sessions)
