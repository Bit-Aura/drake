"""
SOC Logger for security event persistence and audit trails.
"""
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import logging
from logging.handlers import RotatingFileHandler


def _reverse_readline(filename: Path, buf_size: int = 8192):
    """A generator that returns the lines of a file in reverse order."""
    if not filename.exists():
        return
    with open(filename, 'rb') as f:
        f.seek(0, 2)
        p = f.tell()
        remainder = b''
        while p > 0:
            read_size = min(buf_size, p)
            p -= read_size
            f.seek(p)
            buffer = f.read(read_size) + remainder
            lines = buffer.split(b'\n')
            remainder = lines[0]
            for line in reversed(lines[1:]):
                if line.strip():
                    yield line.decode('utf-8').strip()
        if remainder.strip():
            yield remainder.decode('utf-8').strip()


class SOCLogger:
    """
    Structured logging system for security operations center.
    Writes events in JSON Lines format for analysis and compliance.
    """
    
    def __init__(self, log_file: str = "data/security_events.jsonl", 
                 max_bytes: int = 10 * 1024 * 1024, backup_count: int = 5):
        """
        Initialize SOC logger.
        
        Args:
            log_file: Path to JSONL log file (relative or absolute)
            max_bytes: Maximum size of a single log file (default 10MB)
            backup_count: Number of backup log files to retain (default 5)
        """
        self.log_file = Path(log_file)
        self._ensure_log_directory()
        
        self._lock = threading.Lock()
        
        # Setup rotating file handler
        self.logger = logging.getLogger("SOCLogger_" + str(self.log_file))
        self.logger.setLevel(logging.INFO)
        
        # Remove existing handlers to avoid duplicates if instantiated multiple times
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
            
        handler = RotatingFileHandler(
            self.log_file, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8'
        )
        handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(handler)
        self.logger.propagate = False
    
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
            with self._lock:
                self.logger.info(json.dumps(event))
        except Exception as e:
            # Fallback: print to stderr if file write fails
            print(f"[SOC_LOGGER_ERROR] Failed to write event: {e}", flush=True)
    
    def _get_all_log_files(self) -> list:
        """Returns the main log file and all rotated backup files in order (newest to oldest)."""
        files = [self.log_file]
        for i in range(1, self.logger.handlers[0].backupCount + 1):
            backup = Path(f"{self.log_file}.{i}")
            if backup.exists():
                files.append(backup)
            else:
                break
        return files

    def read_events(self, limit: Optional[int] = None) -> list:
        """
        Read events from log file.
        
        Args:
            limit: Maximum number of events to return (most recent first in timeline, 
                   so the result is oldest to newest among the limited subset)
            
        Returns:
            List of event dictionaries in chronological order
        """
        events = []
        try:
            for log_path in self._get_all_log_files():
                for line in _reverse_readline(log_path):
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                        
                    if limit and len(events) >= limit:
                        events.reverse()
                        return events
        except Exception as e:
            print(f"[SOC_LOGGER_ERROR] Failed to read events: {e}", flush=True)
            
        events.reverse()
        return events
    
    def get_session_history(self, session_id: str) -> list:
        """
        Retrieve all events for specific session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of events for session in chronological order
        """
        events = []
        try:
            for log_path in self._get_all_log_files():
                for line in _reverse_readline(log_path):
                    try:
                        event = json.loads(line)
                        if event.get("session_id") == session_id:
                            events.append(event)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"[SOC_LOGGER_ERROR] Failed to read events: {e}", flush=True)
            
        events.reverse()
        return events
    
    def get_critical_events(self, tier: str = "CRITICAL") -> list:
        """
        Filter events by threat tier.
        
        Args:
            tier: Tier to filter by
            
        Returns:
            List of matching events in chronological order
        """
        events = []
        try:
            for log_path in self._get_all_log_files():
                for line in _reverse_readline(log_path):
                    try:
                        event = json.loads(line)
                        if event.get("tier") == tier:
                            events.append(event)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"[SOC_LOGGER_ERROR] Failed to read events: {e}", flush=True)
            
        events.reverse()
        return events
    
    def clear_logs(self) -> bool:
        """
        Delete log file (use with caution).
        
        Returns:
            True if file was deleted, False otherwise
        """
        success = False
        with self._lock:
            try:
                for log_path in self._get_all_log_files():
                    if log_path.exists():
                        os.remove(log_path)
                        success = True
            except Exception as e:
                print(f"[SOC_LOGGER_ERROR] Failed to clear logs: {e}", flush=True)
        return success
    
    def get_log_size(self) -> int:
        """
        Get log file size in bytes (including rotated backup files).
        
        Returns:
            Total file size or 0 if no files exist
        """
        total_size = 0
        try:
            for log_path in self._get_all_log_files():
                if log_path.exists():
                    total_size += log_path.stat().st_size
        except Exception:
            pass
        return total_size
