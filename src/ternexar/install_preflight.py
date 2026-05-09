from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Dict

from ternexar.version_check import get_version_check_data, CheckStatus
from ternexar.installer_profiles import profile_registry, ProfileStatus
from ternexar.gate import gate_engine, GateStatus
from ternexar.confirm import confirm_engine
from ternexar.risk import RiskLevel
from ternexar.audit import audit_manager
from ternexar.ui import ui

class PreflightVerdict(Enum):
    ALREADY_INSTALLED = "ALREADY_INSTALLED"
    READY_FOR_FUTURE_CONFIRMED_EXECUTION = "READY_FOR_FUTURE_CONFIRMED_EXECUTION"
    NOT_READY_NEEDS_VERIFICATION = "NOT_READY_NEEDS_VERIFICATION"
    NOT_READY_UNKNOWN_TOOL = "NOT_READY_UNKNOWN_TOOL"
    NOT_READY_UNSUPPORTED_OS = "NOT_READY_UNSUPPORTED_OS"
    REFUSED = "REFUSED"
    CHECK_FAILED = "CHECK_FAILED"

def handle_install_preflight(tool: str):
    """Orchestrate the installer preflight readiness check."""
    # 1. Version Check
    version_data = get_version_check_data(tool)
    
    # 2. Profile Lookup
    profile = profile_registry.get_profile(tool)
    os_key = profile_registry.detect_os_key()
    
    data = {
        "requested_tool": tool,
        "normalized_tool": version_data["normalized_tool"],
        "version_status": version_data["status"],
        "version_output": version_data["version_output"],
        "profile_status": profile.status if profile else ProfileStatus.UNKNOWN_TOOL,
        "os_key": os_key,
        "steps": [],
        "verdict": PreflightVerdict.NOT_READY_UNKNOWN_TOOL,
        "notes": None
    }

    # 3. Determine Verdict
    if version_data["status"] == CheckStatus.INSTALLED:
        data["verdict"] = PreflightVerdict.ALREADY_INSTALLED
    
    elif version_data["status"] == CheckStatus.CHECK_FAILED:
        data["verdict"] = PreflightVerdict.CHECK_FAILED
        data["notes"] = version_data["notes"]
    
    elif version_data["status"] == CheckStatus.REFUSED:
        data["verdict"] = PreflightVerdict.REFUSED
        data["notes"] = "Version check was refused by safety policy."

    elif not profile:
        data["verdict"] = PreflightVerdict.NOT_READY_UNKNOWN_TOOL
    
    elif profile.status == ProfileStatus.NEEDS_VERIFICATION:
        data["verdict"] = PreflightVerdict.NOT_READY_NEEDS_VERIFICATION
    
    else:
        # Evaluate profile steps
        platform_profile = profile.platforms.get(os_key)
        if not platform_profile:
            data["verdict"] = PreflightVerdict.NOT_READY_UNSUPPORTED_OS
        else:
            any_blocked = False
            for cmd in platform_profile.commands:
                gate_result = gate_engine.evaluate(cmd)
                confirm_result = confirm_engine.evaluate(cmd)
                
                step_data = {
                    "command": cmd,
                    "risk_level": gate_result.risk_level,
                    "gate_decision": gate_result.gate_decision,
                    "confirmation_mode": confirm_result.mode
                }
                data["steps"].append(step_data)
                
                if gate_result.gate_decision == GateStatus.BLOCK:
                    any_blocked = True
            
            if any_blocked:
                data["verdict"] = PreflightVerdict.REFUSED
                data["notes"] = "One or more installer commands are BLOCKED by safety policy."
            else:
                data["verdict"] = PreflightVerdict.READY_FOR_FUTURE_CONFIRMED_EXECUTION

    # 4. Audit Logging
    _log_preflight_audit(data)

    # 5. UI Rendering
    ui.render_install_preflight_report(data)

def _log_preflight_audit(data: Dict):
    """Log preflight event to audit manager."""
    audit_manager.log_event(
        command=f"install-preflight {data['requested_tool']}",
        risk_level="LOW",  # The preflight itself is LOW risk
        gate_decision="PASS",
        policy="N/A",
        confirmation_mode="N/A",
        action_type=f"INSTALL_PREFLIGHT_{data['verdict'].value}",
        result=data["verdict"].value,
        notes=(
            f"Tool: {data['normalized_tool']} | "
            f"Version: {data['version_status'].value} | "
            f"Profile: {data['profile_status'].value} | "
            f"OS: {data['os_key']}"
        )
    )
