import subprocess
import shlex
import sys
import typer
from enum import Enum
from typing import List, Dict, Optional

from ternexar.version_check import get_version_check_data, CheckStatus
from ternexar.installer_profiles import profile_registry, ProfileStatus, InstallerProfile, PlatformProfile
from ternexar.install_preflight import handle_install_preflight, PreflightVerdict
from ternexar.gate import gate_engine, GateStatus
from ternexar.risk import RiskLevel
from ternexar.audit import audit_manager
from ternexar.ui import ui

class InstallStatus(Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUSED = "REFUSED"
    ALREADY_INSTALLED = "ALREADY_INSTALLED"

class InstallerExecutor:
    def __init__(self):
        self.sudo_safety_note = "Your system may ask for a password. TERNEXAR does not read or store it."

    def execute_install(self, tool_name: str):
        """Orchestrates the confirmed installer execution flow."""
        # 1. Normalize and Audit Request
        profile = profile_registry.get_profile(tool_name)
        normalized_name = profile.name if profile else tool_name
        
        audit_manager.log_event(
            command=f"install {tool_name}",
            risk_level="HIGH",
            gate_decision="HOLD",
            policy="REQUIRE_STRONG_CONFIRMATION",
            confirmation_mode="STRONG_CONFIRMATION",
            action_type="INSTALL_REQUESTED",
            result="PENDING",
            notes=f"Requested: {tool_name} | Normalized: {normalized_name}"
        )

        # 2. Version Check
        version_data = get_version_check_data(tool_name)
        if version_data["status"] == CheckStatus.INSTALLED:
            ui.info(f"Tool '{normalized_name}' is already installed ({version_data['version_output']}).")
            audit_manager.log_event(
                command=f"install {tool_name}",
                risk_level="LOW",
                gate_decision="PASS",
                policy="N/A",
                confirmation_mode="N/A",
                action_type="INSTALL_SKIPPED_ALREADY_INSTALLED",
                result="ALREADY_INSTALLED",
                notes=f"Version: {version_data['version_output']}"
            )
            return

        # 3. Preflight Readiness
        # We re-run the preflight logic internally to get the verdict data
        preflight_data = self._get_preflight_data(tool_name, version_data, profile)
        
        audit_manager.log_event(
            command=f"install {tool_name}",
            risk_level="LOW",
            gate_decision="PASS",
            policy="N/A",
            confirmation_mode="N/A",
            action_type="INSTALL_PREFLIGHT_RESULT",
            result=preflight_data["verdict"].value
        )

        if preflight_data["verdict"] != PreflightVerdict.READY_FOR_FUTURE_CONFIRMED_EXECUTION:
            ui.render_install_preflight_report(preflight_data)
            ui.error(f"Installation refused: {preflight_data['verdict'].value}")
            if preflight_data["notes"]:
                ui.info(f"Reason: {preflight_data['notes']}")
            
            audit_manager.log_event(
                command=f"install {tool_name}",
                risk_level="N/A",
                gate_decision="BLOCK",
                policy="DENY",
                confirmation_mode="N/A",
                action_type="INSTALL_REFUSED",
                result="REFUSED",
                notes=preflight_data["notes"]
            )
            return

        if profile is None:
            ui.error("Installation refused: verified installer profile is unavailable.")
            audit_manager.log_event(
                command=f"install {tool_name}",
                risk_level="N/A",
                gate_decision="BLOCK",
                policy="DENY",
                confirmation_mode="N/A",
                action_type="INSTALL_REFUSED",
                result="REFUSED",
                notes="Verified installer profile was unavailable before execution."
            )
            return

        # 4. Mandatory Review UI
        ui.render_install_execution_header(normalized_name)
        ui.render_install_preflight_report(preflight_data)
        
        os_key = profile_registry.detect_os_key()
        platform_profile = profile.platforms[os_key]
        commands = platform_profile.commands

        # 5. Two-Step Confirmation
        ui.info(f"\n[bold yellow]SAFETY NOTE:[/] {self.sudo_safety_note}")
        
        # Step 1: Standard Choice
        if not typer.confirm("\nProceed with verified installer profile?", default=False):
            self._handle_cancel(tool_name, normalized_name)
            return

        # Step 2: Strong String Confirmation
        expected_str = f"INSTALL {profile.id.upper()}"
        ui.warning(f"\nSTRONG CONFIRMATION REQUIRED")
        confirm_str = typer.prompt(f"Type {expected_str} to continue")

        if confirm_str != expected_str:
            ui.error("Confirmation string mismatch.")
            self._handle_cancel(tool_name, normalized_name)
            return

        # 6. Execution Phase
        audit_manager.log_event(
            command=f"install {tool_name}",
            risk_level="HIGH",
            gate_decision="PASS",
            policy="N/A",
            confirmation_mode="STRONG_CONFIRMATION",
            action_type="INSTALL_CONFIRMED",
            result="CONFIRMED"
        )

        success = True
        for i, cmd_str in enumerate(commands):
            ui.render_install_step(i + 1, len(commands), cmd_str)
            
            # Strict Validation before execution
            if not self._is_command_safe(cmd_str):
                ui.error(f"Safety violation detected in profile command: {cmd_str}")
                success = False
                break

            audit_manager.log_event(
                command=cmd_str,
                risk_level="HIGH",
                gate_decision="PASS",
                policy="N/A",
                confirmation_mode="N/A",
                action_type="INSTALL_COMMAND_START",
                result="STARTING"
            )

            try:
                # Use shlex.split for safe list args
                args = shlex.split(cmd_str)
                
                # Execute with terminal inheritance to allow sudo prompts
                # shell=False is implied by list args with subprocess.run
                result = subprocess.run(
                    args,
                    shell=False,
                    check=False, # We handle errors manually
                    timeout=600  # 10 minute timeout per command
                )
                
                if result.returncode != 0:
                    ui.error(f"Command failed with exit code {result.returncode}")
                    ui.hint(f"Safe recovery may be available. Try: [bold white]tx recover \"<error summary>\"[/]")
                    audit_manager.log_event(
                        command=cmd_str,
                        risk_level="HIGH",
                        gate_decision="N/A",
                        policy="N/A",
                        confirmation_mode="N/A",
                        action_type="INSTALL_COMMAND_FAILED",
                        result="FAILED",
                        notes=f"Exit code: {result.returncode}"
                    )
                    success = False
                    break
                else:
                    audit_manager.log_event(
                        command=cmd_str,
                        risk_level="HIGH",
                        gate_decision="N/A",
                        policy="N/A",
                        confirmation_mode="N/A",
                        action_type="INSTALL_COMMAND_SUCCESS",
                        result="SUCCESS"
                    )

            except Exception as e:
                ui.error(f"Execution error: {str(e)}")
                audit_manager.log_event(
                    command=cmd_str,
                    risk_level="HIGH",
                    gate_decision="N/A",
                    policy="N/A",
                    confirmation_mode="N/A",
                    action_type="INSTALL_COMMAND_FAILED",
                    result="ERROR",
                    notes=str(e)
                )
                success = False
                break

        # 7. Post-Install Verification
        if success:
            ui.info("\n[bold green]Execution complete. Verifying installation...[/]")
            audit_manager.log_event(
                command=f"verify {tool_name}",
                risk_level="LOW",
                gate_decision="PASS",
                policy="N/A",
                confirmation_mode="N/A",
                action_type="INSTALL_VERIFY_START",
                result="STARTING"
            )
            
            # Wait a moment for PATH to potentially update if needed (unlikely to help in same process but good for audit)
            version_data_after = get_version_check_data(tool_name)
            
            if version_data_after["status"] == CheckStatus.INSTALLED:
                ui.render_install_result(InstallStatus.SUCCESS, normalized_name, version_data_after["version_output"])
                audit_manager.log_event(
                    command=f"install {tool_name}",
                    risk_level="N/A",
                    gate_decision="N/A",
                    policy="N/A",
                    confirmation_mode="N/A",
                    action_type="INSTALL_SUCCESS",
                    result="SUCCESS",
                    notes=f"Verified: {version_data_after['version_output']}"
                )
            else:
                ui.render_install_result(InstallStatus.FAILED, normalized_name, "Verification failed after install steps.")
                audit_manager.log_event(
                    command=f"install {tool_name}",
                    risk_level="N/A",
                    gate_decision="N/A",
                    policy="N/A",
                    confirmation_mode="N/A",
                    action_type="INSTALL_VERIFY_FAILED",
                    result="FAILED",
                    notes="Command sequence finished but tool not found in PATH."
                )
        else:
            ui.render_install_result(InstallStatus.FAILED, normalized_name, "One or more commands failed.")
            audit_manager.log_event(
                command=f"install {tool_name}",
                risk_level="N/A",
                gate_decision="N/A",
                policy="N/A",
                confirmation_mode="N/A",
                action_type="INSTALL_FAILED",
                result="FAILED"
            )

    def _get_preflight_data(self, tool: str, version_data: Dict, profile: Optional[InstallerProfile]) -> Dict:
        """Internal helper to get preflight data without rendering."""
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
            platform_profile = profile.platforms.get(os_key)
            if not platform_profile:
                data["verdict"] = PreflightVerdict.NOT_READY_UNSUPPORTED_OS
            else:
                any_blocked = False
                for cmd in platform_profile.commands:
                    gate_result = gate_engine.evaluate(cmd)
                    step_data = {
                        "command": cmd,
                        "risk_level": gate_result.risk_level,
                        "gate_decision": gate_result.gate_decision,
                        "confirmation_mode": "STRONG_CONFIRMATION" if gate_result.risk_level == RiskLevel.HIGH else "STANDARD_CONFIRMATION"
                    }
                    data["steps"].append(step_data)
                    if gate_result.gate_decision == GateStatus.BLOCK:
                        any_blocked = True
                
                if any_blocked:
                    data["verdict"] = PreflightVerdict.REFUSED
                    data["notes"] = "One or more installer commands are BLOCKED by safety policy."
                else:
                    data["verdict"] = PreflightVerdict.READY_FOR_FUTURE_CONFIRMED_EXECUTION
        
        return data

    def _is_command_safe(self, cmd: str) -> bool:
        """Strict validation for installer commands."""
        # Reject shell metacharacters
        unsafe = [";", "&&", "||", "|", ">", "<", "$(", "`"]
        if any(char in cmd for char in unsafe):
            return False
            
        # Reject specific dangerous patterns
        dangerous = ["rm ", "chmod 777", "curl ", "wget ", "reboot", "shutdown", "ufw ", "iptables", ".env"]
        if any(pattern in cmd.lower() for pattern in dangerous):
            return False
            
        return True

    def _handle_cancel(self, tool: str, normalized: str):
        ui.info("\n[dim]Installation cancelled by user.[/]")
        audit_manager.log_event(
            command=f"install {tool}",
            risk_level="N/A",
            gate_decision="N/A",
            policy="N/A",
            confirmation_mode="N/A",
            action_type="INSTALL_CANCELLED",
            result="CANCELLED",
            notes=f"Tool: {normalized}"
        )

installer_executor = InstallerExecutor()
