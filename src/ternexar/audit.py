import json
import os
import re
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


REDACTED_VALUE = "[REDACTED]"
SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(token|secret|api[_-]?key|password|credential|key)\b\s*([:=])\s*([^\s,;]+)"
)
SECRET_FLAG = re.compile(r"(?i)(--(?:password|token|api-key)\s+)([^\s,;]+)")
BEARER_TOKEN = re.compile(r"(?i)(authorization\s*:\s*bearer\s+)([^\s,;]+)")
GITHUB_TOKEN = re.compile(r"\bghp_[A-Za-z0-9]+\b")
OPENAI_TOKEN = re.compile(r"\bsk-[A-Za-z0-9_-]+\b")
AWS_ACCESS_KEY = re.compile(r"\bAKIA[0-9A-Z]{16}\b")

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
        value = SECRET_FLAG.sub(lambda match: f"{match.group(1)}{REDACTED_VALUE}", value)
        value = SECRET_ASSIGNMENT.sub(
            lambda match: f"{match.group(1)}{match.group(2)}{REDACTED_VALUE}", value
        )
        value = BEARER_TOKEN.sub(lambda match: f"{match.group(1)}{REDACTED_VALUE}", value)
        value = GITHUB_TOKEN.sub(REDACTED_VALUE, value)
        value = OPENAI_TOKEN.sub(REDACTED_VALUE, value)
        return AWS_ACCESS_KEY.sub(REDACTED_VALUE, value)

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
    ) -> None:
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
        except Exception:
            return

    def get_records(self, limit: int = 10) -> List[Dict]:
        """Retrieve the last N records from the audit log."""
        if limit < 0:
            raise ValueError("limit must be non-negative")
        if limit == 0:
            return []
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
        replacement_path: Optional[Path] = None
        try:
            with self._write_lock:
                self._ensure_dir()
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=self.base_dir,
                    prefix=".audit-",
                    suffix=".jsonl",
                    delete=False,
                ) as replacement_handle:
                    replacement_path = Path(replacement_handle.name)
                    replacement_handle.write(json.dumps(clear_record) + "\n")
                    replacement_handle.flush()
                    os.fsync(replacement_handle.fileno())
                os.chmod(replacement_path, 0o600)
                os.replace(replacement_path, self.log_file)
                replacement_path = None
        except Exception as error:
            if replacement_path is not None:
                try:
                    replacement_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise RuntimeError(f"Failed to clear audit log: {error}")

audit_manager = AuditManager()
