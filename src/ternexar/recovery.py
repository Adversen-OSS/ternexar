import os
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Tuple

from ternexar.recovery_profiles import RecoveryProfile, RecoveryDomain, classify_error
from ternexar.audit import audit_manager
from ternexar.ui import ui

@dataclass
class RecoveryReport:
    error_text: str
    profile: RecoveryProfile
    source_file: Optional[str] = None
    status: str = "PREVIEW_ONLY"
    safety_decision: str = "SAFE_PREVIEW"

class RecoveryEngine:
    def __init__(self):
        self.max_file_size = 100 * 1024  # 100 KB
        self.blocked_keywords = {"secret", "token", "key", "password", "credential"}
        self.blocked_paths = {
            "/etc", "/usr", "/var", "/proc", "/sys", "/dev", "/bin", "/sbin", "/boot", "/root"
        }

    def recover(self, error_text: str, source_file: Optional[str] = None) -> RecoveryReport:
        """Analyze error text and return a recovery report."""
        
        # 1. Redact potential secrets before processing
        safe_text = self._redact_secrets(error_text)
        
        # 2. Check for destructive requests
        if self._is_destructive(safe_text):
            destructive_profile = RecoveryProfile(
                id="BLOCKED_DESTRUCTIVE_REQUEST",
                domain=RecoveryDomain.DESTRUCTIVE,
                signatures=[],
                explanation="This request contains patterns associated with destructive system actions which are strictly blocked.",
                repair_plan=["None. TERNEXAR refuses to assist with destructive requests."]
            )
            report = RecoveryReport(
                error_text=safe_text,
                profile=destructive_profile,
                source_file=source_file,
                status="BLOCKED",
                safety_decision="REFUSED"
            )
        else:
            # 3. Classify
            profile = classify_error(safe_text)
            report = RecoveryReport(
                error_text=safe_text,
                profile=profile,
                source_file=source_file
            )

        # 4. Audit
        self._audit_recovery(report)
        
        return report

    def recover_file(self, file_path: str) -> RecoveryReport:
        """Read a file and run recovery on its content."""
        path = Path(file_path).resolve()
        
        # Strict security checks
        try:
            # 1. Hidden files/folders
            if path.name.startswith(".") or any(p.startswith(".") for p in path.parts):
                 return self._refused_report(f"Hidden path blocked: {file_path}", "PATH_BLOCKED")

            # 2. Sensitive folders
            sensitive_parts = {".git", ".ssh", ".gnupg", ".aws", ".config"}
            if any(part in path.parts for part in sensitive_parts):
                return self._refused_report(f"Sensitive folder blocked: {file_path}", "PATH_BLOCKED")

            # 3. System paths
            if self._is_blocked_system_path(path):
                return self._refused_report(f"System path blocked in v2.1: {file_path}", "PATH_BLOCKED")

            # 4. Filename checks
            if any(kw in path.name.lower() for kw in self.blocked_keywords):
                return self._refused_report(f"Sensitive filename blocked: {file_path}", "FILENAME_BLOCKED")

            # 5. File type check (text only)
            # We'll try to read it as utf-8. If it fails or contains null bytes, it's likely binary.
            if not path.exists():
                return self._refused_report(f"File not found: {file_path}", "NOT_FOUND")

            if path.stat().st_size > self.max_file_size:
                return self._refused_report(f"File too large: {file_path} (Max 100KB)", "SIZE_BLOCKED")

            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                if "\0" in content:
                    return self._refused_report(f"Binary file blocked: {file_path}", "TYPE_BLOCKED")
                
                return self.recover(content, source_file=str(path))

        except UnicodeDecodeError:
            return self._refused_report(f"Non-text file blocked: {file_path}", "TYPE_BLOCKED")
        except Exception as e:
            return self._refused_report(f"Error reading file: {str(e)}", "READ_ERROR")

    def _is_blocked_system_path(self, path: Path) -> bool:
        """Return whether a resolved path is a blocked root or its descendant."""
        return any(
            path == blocked_root or blocked_root in path.parents
            for blocked_root in (Path(blocked_path) for blocked_path in self.blocked_paths)
        )

    def _is_destructive(self, text: str) -> bool:
        """Detect destructive patterns."""
        lower_text = text.lower()
        destructive_patterns = [
            r"rm\s+-rf",
            r"delete\s+/home",
            r"wipe\s+disk",
            r"format\s+disk",
            r"remove\s+all\s+apt\s+sources",
            r"chmod\s+777",
            r"chown\s+-R\s+/",
            r"cat\s+\.env",
            r"curl\s+.*\s+\|\s*sh",
            r"wget\s+.*\s+\|\s*sh"
        ]
        return any(re.search(p, lower_text) for p in destructive_patterns)

    def _redact_secrets(self, text: str) -> str:
        """Simple redaction for potential tokens/keys."""
        # Redact things that look like keys/tokens (hex or base64-like strings > 20 chars)
        # This is a heuristic, not a guarantee.
        redacted = re.sub(r"[a-zA-Z0-9+/]{32,}", "[REDACTED_SENSITIVE_DATA]", text)
        return redacted

    def _refused_report(self, message: str, reason: str) -> RecoveryReport:
        refused_profile = RecoveryProfile(
            id="RECOVERY_REFUSED",
            domain=RecoveryDomain.UNKNOWN,
            signatures=[],
            explanation=message,
            repair_plan=["Review safety policy constraints."]
        )
        report = RecoveryReport(
            error_text=message,
            profile=refused_profile,
            status="REFUSED",
            safety_decision=reason
        )
        self._audit_recovery(report)
        return report

    def _audit_recovery(self, report: RecoveryReport):
        """Log recovery events to audit."""
        audit_manager.log_event(
            command=f"recover {report.source_file or 'text'}",
            risk_level="LOW",
            gate_decision="PASS",
            policy="RECOVERY",
            confirmation_mode="N/A",
            action_type="RECOVERY_REPORT_GENERATED",
            result=report.status,
            notes=f"Domain: {report.profile.domain.value} | Profile: {report.profile.id} | Decision: {report.safety_decision}"
        )

recovery_engine = RecoveryEngine()

def handle_recover(text: str):
    """CLI handler for tx recover."""
    ui.info(f"Diagnosing error text...")
    report = recovery_engine.recover(text)
    ui.render_recovery_report(report)

def handle_recover_file(path: str):
    """CLI handler for tx recover-file."""
    ui.info(f"Reading and diagnosing file: [bold white]{path}[/]")
    report = recovery_engine.recover_file(path)
    ui.render_recovery_report(report)
