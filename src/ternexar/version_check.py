import shutil
import subprocess
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Dict

from ternexar.risk import RiskLevel
from ternexar.gate import gate_engine, GateStatus
from ternexar.confirm import confirm_engine, ConfirmationMode
from ternexar.audit import audit_manager
from ternexar.ui import ui

class CheckStatus(Enum):
    INSTALLED = "INSTALLED"
    NOT_INSTALLED = "NOT_INSTALLED"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"
    UNKNOWN_TOOL = "UNKNOWN_TOOL"
    CHECK_FAILED = "CHECK_FAILED"
    REFUSED = "REFUSED"

@dataclass
class VersionCheckProfile:
    id: str
    name: str
    aliases: List[str]
    executable: str
    version_command: List[str]
    status: CheckStatus = CheckStatus.INSTALLED

class VersionCheckRegistry:
    def __init__(self):
        self.profiles: List[VersionCheckProfile] = [
            VersionCheckProfile(
                id="python3",
                name="Python 3",
                aliases=["python", "python 3", "python3"],
                executable="python3",
                version_command=["python3", "--version"]
            ),
            VersionCheckProfile(
                id="nodejs",
                name="Node.js",
                aliases=["node", "nodejs"],
                executable="node",
                version_command=["node", "--version"]
            ),
            VersionCheckProfile(
                id="npm",
                name="npm",
                aliases=["npm"],
                executable="npm",
                version_command=["npm", "--version"]
            ),
            VersionCheckProfile(
                id="codex",
                name="OpenAI Codex",
                aliases=["codex", "openai codex"],
                executable="codex",
                version_command=[],
                status=CheckStatus.NEEDS_VERIFICATION
            ),
            VersionCheckProfile(
                id="claude-code",
                name="Claude Code",
                aliases=["claude", "claude code", "anthropic claude code"],
                executable="claude",
                version_command=[],
                status=CheckStatus.NEEDS_VERIFICATION
            )
        ]

    def get_profile(self, tool_name: str) -> Optional[VersionCheckProfile]:
        query = tool_name.strip().lower()
        for profile in self.profiles:
            if query == profile.id or query in profile.aliases:
                return profile
        return None

version_check_registry = VersionCheckRegistry()

def get_version_check_data(tool_name: str) -> Dict:
    """Safely get version check data for a supported tool without rendering UI."""
    profile = version_check_registry.get_profile(tool_name)
    
    data = {
        "requested_tool": tool_name,
        "normalized_tool": profile.name if profile else "Unknown",
        "status": CheckStatus.UNKNOWN_TOOL,
        "executable": None,
        "command": None,
        "version_output": None,
        "risk_level": None,
        "gate_decision": None,
        "confirmation_mode": None,
        "exit_code": None,
        "notes": None
    }

    if not profile:
        return data

    data["normalized_tool"] = profile.name
    data["executable"] = profile.executable

    if profile.status == CheckStatus.NEEDS_VERIFICATION:
        data["status"] = CheckStatus.NEEDS_VERIFICATION
        data["notes"] = "Trusted version-check profile not yet verified for this tool."
        return data

    # 1. Existence Check
    exec_path = shutil.which(profile.executable)
    if not exec_path:
        data["status"] = CheckStatus.NOT_INSTALLED
        data["notes"] = f"Executable '{profile.executable}' not found in PATH."
        _log_audit(data)
        return data

    # 2. Safety Check
    cmd_str = " ".join(profile.version_command)
    gate_result = gate_engine.evaluate(cmd_str)
    confirm_result = confirm_engine.evaluate(cmd_str)

    data["command"] = cmd_str
    data["risk_level"] = gate_result.risk_level
    data["gate_decision"] = gate_result.gate_decision
    data["confirmation_mode"] = confirm_result.mode

    # Must be LOW + PASS + MINIMAL_CONFIRMATION
    if (gate_result.risk_level != RiskLevel.LOW or 
        gate_result.gate_decision != GateStatus.PASS or 
        confirm_result.mode != ConfirmationMode.MINIMAL_CONFIRMATION.value):
        data["status"] = CheckStatus.REFUSED
        data["notes"] = f"Safety policy refused execution: {gate_result.risk_level.value}/{gate_result.gate_decision.value}"
        _log_audit(data)
        return data

    # 3. Execution
    try:
        result = subprocess.run(
            profile.version_command,
            shell=False,
            capture_output=True,
            text=True,
            timeout=5
        )
        data["exit_code"] = result.returncode
        
        if result.returncode == 0:
            data["status"] = CheckStatus.INSTALLED
            # Clean output: first line only, max 100 chars
            output = result.stdout.strip() or result.stderr.strip()
            data["version_output"] = output.split('\n')[0][:100]
        else:
            data["status"] = CheckStatus.CHECK_FAILED
            data["version_output"] = (result.stderr.strip() or result.stdout.strip())[:100]
            data["notes"] = f"Command failed with exit code {result.returncode}"
            
    except subprocess.TimeoutExpired:
        data["status"] = CheckStatus.CHECK_FAILED
        data["notes"] = "Version check timed out after 5 seconds."
    except Exception as e:
        data["status"] = CheckStatus.CHECK_FAILED
        data["notes"] = f"Unexpected error during execution: {str(e)}"

    _log_audit(data)
    return data

def handle_version_check(tool_name: str):
    """Safely check the version of a supported tool and render UI."""
    data = get_version_check_data(tool_name)
    ui.render_version_check_result(data)

def _log_audit(data: Dict):
    """Internal helper to log version check to audit."""
    audit_manager.log_event(
        command=data["command"] or "N/A",
        risk_level=data["risk_level"].value if data["risk_level"] else "N/A",
        gate_decision=data["gate_decision"].value if data["gate_decision"] else "N/A",
        policy="N/A",
        confirmation_mode=data["confirmation_mode"] or "N/A",
        action_type=f"VERSION_CHECK_{data['status'].value}",
        result=data["status"].value,
        notes=f"Tool: {data['requested_tool']} | Output: {data['version_output']}"
    )
