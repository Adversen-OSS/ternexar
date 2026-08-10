import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from ternexar.audit import audit_manager
from ternexar.ollama_client import ollama_client
from ternexar.patcher import patcher
from ternexar.ui import ui

@dataclass
class AnalysisResult:
    task: str
    detected_issue: Optional[str] = None
    explanation: Optional[str] = None
    proposed_file: Optional[Path] = None
    proposed_content: Optional[str] = None
    diff: Optional[str] = None
    safety_verdict: str = "PENDING"
    reason: Optional[str] = None

class Analyzer:
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()

    def analyze(self, task: str) -> AnalysisResult:
        """Analyze a task or error message and propose a fix."""
        result = AnalysisResult(task=task)

        # 1. Deterministic Detection: ModuleNotFoundError / ImportError
        missing_module = self._detect_missing_module(task)
        
        if missing_module:
            result.detected_issue = f"Missing Python module: [bold cyan]{missing_module}[/]"
            result.proposed_file = self.project_root / "requirements.txt"
            
            # Suggest adding to requirements.txt
            new_content = self._generate_requirements_patch(missing_module)
            result.proposed_content = new_content
            
            # Generate Diff
            result.diff = patcher.generate_diff(result.proposed_file, new_content)
            result.safety_verdict = "SAFE"
        else:
            # Check for blocked actions in the prompt
            blocked_reason = self._check_blocked_actions(task)
            if blocked_reason:
                result.detected_issue = "Blocked action detected."
                result.safety_verdict = "BLOCKED"
                result.reason = blocked_reason
                return result
            
            result.detected_issue = "No deterministic fix found for this issue."
            result.safety_verdict = "REFUSED"
            result.reason = "Currently, TERNEXAR v1.2 only supports simple Python dependency fixes."

        # 2. Optional static explanation
        if missing_module:
            result.explanation = f"The application is trying to import '{missing_module}', but it's not installed in the current environment or listed in requirements.txt."

        return result

    def _detect_missing_module(self, text: str) -> Optional[str]:
        """Detect missing module from error strings."""
        patterns = [
            # Handles ModuleNotFoundError: No module named 'requests' or No module named requests
            r"ModuleNotFoundError:\s*No\s*module\s*named\s*['\"]?([^'\"\s\n]+)['\"]?",
            # Handles ImportError: No module named 'requests' or No module named requests
            r"ImportError:\s*No\s*module\s*named\s*['\"]?([^'\"\s\n]+)['\"]?",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Group 1 captures the module name without quotes due to [^'\"\s\n]+
                return match.group(1).strip()
        
        return None

    def _generate_requirements_patch(self, module_name: str) -> str:
        """Generate new content for requirements.txt including the new module."""
        req_file = self.project_root / "requirements.txt"
        current_content = ""
        if req_file.exists():
            with open(req_file, "r", encoding="utf-8") as f:
                current_content = f.read()

        lines = current_content.splitlines()
        # Clean up lines and check if already exists
        if any(line.strip().split('==')[0].lower() == module_name.lower() for line in lines if line.strip()):
            return current_content

        if current_content and not current_content.endswith("\n"):
            current_content += "\n"
        
        return current_content + f"{module_name}\n"

    def _check_blocked_actions(self, task: str) -> Optional[str]:
        """Check for destructive or out-of-scope actions in the task description."""
        blocked_keywords = {
            "delete": "File deletion is strictly prohibited.",
            "remove": "File removal is strictly prohibited.",
            "rm ": "Shell commands like 'rm' are blocked.",
            "rename": "Renaming files is not supported in v1.2.",
            "move": "Moving files is not supported in v1.2.",
            "chmod": "Permission changes are blocked.",
            "chown": "Ownership changes are blocked.",
            "sudo": "Administrative actions are blocked.",
            "pip install": "Automatic package installation is blocked. TERNEXAR only suggests requirements.txt patches.",
            ".env": "Accessing or modifying .env files is strictly blocked.",
        }
        
        task_lower = task.lower()
        for kw, reason in blocked_keywords.items():
            if kw in task_lower:
                return reason
        
        return None


def handle_analyze(task: str):
    """Orchestrate the analysis and patching workflow."""
    ui.info(f"Analyzing: [bold white]{task}[/]")
    
    # 1. Start Audit
    audit_manager.log_event(
        command=f"tx analyze \"{task}\"",
        risk_level="LOW",
        gate_decision="PASS",
        policy="ANALYZE",
        confirmation_mode="STANDARD_CONFIRMATION",
        action_type="ANALYZE_START",
        result="STARTED",
        notes=f"Task: {task}"
    )

    with ui.status("Scanning project and detecting issues..."):
        result = analyzer.analyze(task)

    ui.render_analysis_result(result)

    if result.safety_verdict == "SAFE" and result.proposed_file and result.proposed_content:
        # Ask for confirmation
        import typer
        if typer.confirm("\nApply fix?", default=False):
            with ui.status("Applying safe patch..."):
                patch_result = patcher.apply_patch(result.proposed_file, result.proposed_content)
            
            if patch_result.success:
                ui.render_patch_applied(patch_result)
                # A committed patch whose post-commit cleanup or durability sync
                # failed must never be audited as an ordinary clean success.
                if patch_result.warning:
                    patch_action = "PATCH_APPLIED_WITH_WARNING"
                    patch_outcome = "SUCCESS_WITH_WARNING"
                    patch_notes = (
                        f"Modified {result.proposed_file}; "
                        f"post-commit warning: {patch_result.warning}"
                    )
                else:
                    patch_action = "PATCH_APPLIED"
                    patch_outcome = "SUCCESS"
                    patch_notes = f"Modified {result.proposed_file}"
                audit_manager.log_event(
                    command=f"tx analyze \"{task}\"",
                    risk_level="LOW",
                    gate_decision="PASS",
                    policy="ANALYZE",
                    confirmation_mode="STANDARD_CONFIRMATION",
                    action_type=patch_action,
                    result=patch_outcome,
                    notes=patch_notes
                )
            else:
                ui.render_patch_failed(patch_result.error or "Unknown error")
                audit_manager.log_event(
                    command=f"tx analyze \"{task}\"",
                    risk_level="LOW",
                    gate_decision="PASS",
                    policy="ANALYZE",
                    confirmation_mode="STANDARD_CONFIRMATION",
                    action_type="PATCH_FAILED",
                    result="FAILED",
                    notes=patch_result.error
                )
        else:
            ui.render_patch_cancelled()
            audit_manager.log_event(
                command=f"tx analyze \"{task}\"",
                risk_level="LOW",
                gate_decision="PASS",
                policy="ANALYZE",
                confirmation_mode="STANDARD_CONFIRMATION",
                action_type="PATCH_CANCELLED",
                result="CANCELLED"
            )
    elif result.safety_verdict == "BLOCKED":
        audit_manager.log_event(
            command=f"tx analyze \"{task}\"",
            risk_level="BLOCKED",
            gate_decision="BLOCK",
            policy="ANALYZE",
            confirmation_mode="REFUSED",
            action_type="PATCH_BLOCKED",
            result="BLOCKED",
            notes=result.reason
        )
    else:
        # Just log completion if no patch was proposed or it was refused
        audit_manager.log_event(
            command=f"tx analyze \"{task}\"",
            risk_level="LOW",
            gate_decision="PASS",
            policy="ANALYZE",
            confirmation_mode="MINIMAL_CONFIRMATION",
            action_type="ANALYZE_END",
            result="COMPLETED",
            notes=result.reason or "No patch proposed."
        )

analyzer = Analyzer()
