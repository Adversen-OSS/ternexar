import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict

class AuditManager:
    def __init__(self):
        self.base_dir = Path.home() / ".local" / "share" / "ternexar"
        self.log_file = self.base_dir / "audit.jsonl"
        self._ensure_dir()

    def _ensure_dir(self):
        """Ensure the audit directory exists with safe permissions."""
        if not self.base_dir.exists():
            self.base_dir.mkdir(parents=True, exist_ok=True)
            # Set directory permissions to 700 (rwx for owner only)
            os.chmod(self.base_dir, 0o700)

    def log_event(
        self,
        command: str,
        risk_level: str,
        gate_decision: str,
        policy: str,
        confirmation_mode: str,
        action_type: str,
        result: str,
        notes: Optional[str] = None
    ):
        """Log a safety event to the audit file."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "command": command,
            "risk_level": risk_level,
            "gate_decision": gate_decision,
            "policy": policy,
            "confirmation_mode": confirmation_mode,
            "action_type": action_type,
            "result": result,
            "notes": notes or ""
        }
        
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            return

    def get_records(self, limit: int = 10) -> List[Dict]:
        """Retrieve the last N records from the audit log."""
        if not self.log_file.exists():
            return []
            
        records = []
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        records.append(json.loads(line))
        except Exception:
            return []
            
        return records[-limit:]

    def clear_logs(self):
        """Securely clear the audit log file."""
        if self.log_file.exists():
            try:
                # Open with 'w' to truncate the file
                with open(self.log_file, "w") as f:
                    f.truncate(0)
            except Exception as e:
                raise RuntimeError(f"Failed to clear audit log: {e}")

audit_manager = AuditManager()
