import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


REDACTED_VALUE = "[REDACTED_SENSITIVE_DATA]"
SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(token|secret|api[_-]?key|password|credential)\b\s*([:=])\s*([^\s,;]+)"
)
BEARER_TOKEN = re.compile(r"(?i)(authorization\s*:\s*bearer\s+)([^\s,;]+)")

class AuditManager:
    def __init__(self):
        self.base_dir = Path.home() / ".local" / "share" / "ternexar"
        self.log_file = self.base_dir / "audit.jsonl"
        self._write_lock = threading.RLock()
        self._ensure_dir()

    def _ensure_dir(self):
        """Ensure the audit directory exists with safe permissions."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.base_dir, 0o700)

    def _redact_secrets(self, value: str) -> str:
        """Redact common secret-bearing values before they reach the audit log."""
        value = SECRET_ASSIGNMENT.sub(
            lambda match: f"{match.group(1)}{match.group(2)}{REDACTED_VALUE}", value
        )
        return BEARER_TOKEN.sub(lambda match: f"{match.group(1)}{REDACTED_VALUE}", value)

    def _write_record(self, record: Dict) -> None:
        """Append one JSONL record while enforcing owner-only file permissions."""
        self._ensure_dir()
        with open(self.log_file, "a", encoding="utf-8") as log_handle:
            log_handle.write(json.dumps(record) + "\n")
        os.chmod(self.log_file, 0o600)

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
    ) -> bool:
        """Log a safety event to the audit file."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "command": self._redact_secrets(command),
            "risk_level": risk_level,
            "gate_decision": gate_decision,
            "policy": policy,
            "confirmation_mode": confirmation_mode,
            "action_type": action_type,
            "result": result,
            "notes": self._redact_secrets(notes or "")
        }

        try:
            with self._write_lock:
                self._write_record(record)
            return True
        except Exception:
            return False

    def get_records(self, limit: int = 10) -> List[Dict]:
        """Retrieve the last N records from the audit log."""
        if not self.log_file.exists():
            return []
            
        records: List[Dict] = []
        try:
            with self._write_lock:
                with open(self.log_file, "r", encoding="utf-8") as log_handle:
                    for line in log_handle:
                        if not line.strip():
                            continue
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(record, dict):
                            records.append(record)
        except Exception:
            return []
            
        return records[-limit:]

    def clear_logs(self):
        """Securely clear the audit log file."""
        clear_record = {
            "timestamp": datetime.now().isoformat(),
            "command": "audit clear",
            "risk_level": "LOW",
            "gate_decision": "PASS",
            "policy": "AUDIT",
            "confirmation_mode": "CONFIRMED",
            "action_type": "AUDIT_LOG_CLEARED",
            "result": "CLEARED",
            "notes": "Previous audit log cleared.",
        }
        try:
            with self._write_lock:
                self._ensure_dir()
                with open(self.log_file, "w", encoding="utf-8") as log_handle:
                    log_handle.truncate(0)
                os.chmod(self.log_file, 0o600)
                self._write_record(clear_record)
        except Exception as error:
            raise RuntimeError(f"Failed to clear audit log: {error}")

audit_manager = AuditManager()
