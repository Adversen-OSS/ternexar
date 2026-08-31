import shlex
import subprocess
from ternexar.risk import RiskLevel, risk_engine
from ternexar.gate import gate_engine, GateStatus
from ternexar.confirm import (
    ConfirmationMode,
    confirm_engine,
    is_interactive_terminal,
    prompt_medium_confirmation,
)
from ternexar.audit import audit_manager
from ternexar.ui import ui

STRICT_ALLOWLIST = [
    "ls",
    "pwd",
    "git status",
    "python --version",
    "python3 --version",
    "whoami",
    "date"
]

FORBIDDEN_CHARS = [";", "&&", "||", "|", ">", ">>", "<", "`", "$("]

def is_in_allowlist(command: str) -> bool:
    """Check if the command starts with an allowlisted base command."""
    # Special handling for multi-word allowlist items like 'git status'
    for allowed in STRICT_ALLOWLIST:
        if command == allowed or command.startswith(f"{allowed} "):
            return True
    return False

def contains_forbidden_elements(command: str) -> bool:
    """Check for shell metacharacters or forbidden chaining."""
    for char in FORBIDDEN_CHARS:
        if char in command:
            return True
    return False


def is_medium_execution_eligible(command: str) -> bool:
    """Determine whether a MEDIUM-risk command belongs to an authorized execution family.

    Risk classification ("What damage class might this command represent?") and execution
    eligibility ("Is this exact command family implemented and authorized for execution?")
    are strictly separated.

    In v1.1, the supported MEDIUM execution family is package manager installation:
      - pip install ... / pip3 install ...
      - npm install ... / npm i ...
      - yarn install ... / yarn add ...
      - cargo install ...

    Generic keyword matches (e.g. 'delete'), recursive deletions ('rm -rf'), git cleanup
    ('git clean -fd'), and nested interpreter invocations ('python -c', 'sh -c', 'bash -c')
    are classification-only and remain non-executable (refused).
    """
    try:
        args = shlex.split(command)
    except Exception:
        return False

    if not args:
        return False

    binary = args[0].lower()

    # Explicitly refuse nested interpreters
    nested_interpreters = {
        "python",
        "python3",
        "sh",
        "bash",
        "zsh",
        "dash",
        "ksh",
        "csh",
        "tcsh",
        "perl",
        "ruby",
        "node",
    }
    if binary in nested_interpreters:
        return False

    # Check authorized package installation command family
    if binary in {"pip", "pip3"}:
        return len(args) >= 2 and args[1].lower() == "install"
    elif binary == "npm":
        return len(args) >= 2 and args[1].lower() in {"install", "i"}
    elif binary == "yarn":
        return len(args) >= 2 and args[1].lower() in {"install", "add"}
    elif binary == "cargo":
        return len(args) >= 2 and args[1].lower() == "install"

    return False


def log_refusal(command: str, reason: str, gate_result=None, confirm_result=None):
    """Log a refused execution attempt to the audit log."""
    audit_manager.log_event(
        command=command,
        risk_level=gate_result.risk_level.value if gate_result else "UNKNOWN",
        gate_decision=gate_result.gate_decision.value if gate_result else "BLOCK",
        policy=gate_result.policy.value if gate_result else "DENY",
        confirmation_mode=confirm_result.mode if confirm_result else "REFUSED",
        action_type="EXECUTION_REFUSED",
        result="REFUSED",
        notes=reason,
    )
    ui.render_refusal(command, reason)


def handle_do(command: str):
    """Safely execute a LOW or MEDIUM-risk command after safety validation and confirmation."""
    # 1. Structural checks
    if contains_forbidden_elements(command):
        log_refusal(command, "Command contains forbidden shell characters or chaining (e.g., |, &&, ;, >).")
        return

    # 2. Pipeline checks
    gate_result = gate_engine.evaluate(command)
    confirm_result = confirm_engine.evaluate(command)

    if gate_result.risk_level in (RiskLevel.HIGH, RiskLevel.BLOCKED):
        log_refusal(
            command,
            f"Execution refused for {gate_result.risk_level.value} risk level. Risk detected: {gate_result.risk_level.value}",
            gate_result,
            confirm_result,
        )
        return

    if gate_result.gate_decision == GateStatus.BLOCK or confirm_result.mode == ConfirmationMode.REFUSED.value:
        log_refusal(
            command,
            f"Command failed the execution gate. Status: {gate_result.gate_decision.value}",
            gate_result,
            confirm_result,
        )
        return

    # 3. Risk-based Execution Boundary
    if gate_result.risk_level == RiskLevel.LOW:
        if not is_in_allowlist(command):
            log_refusal(
                command,
                "Command is not in the strict v1.0 allowlist.",
                gate_result,
                confirm_result,
            )
            return
        ui.render_minimal_confirmation(command)

    elif gate_result.risk_level == RiskLevel.MEDIUM:
        if not is_medium_execution_eligible(command):
            log_refusal(
                command,
                "Command is classified as MEDIUM risk, but this command pattern is not execution-eligible in v1.1. Risk detected: MEDIUM",
                gate_result,
                confirm_result,
            )
            return

        if not is_interactive_terminal():
            log_refusal(
                command,
                "Interactive confirmation required for MEDIUM risk command, but stdin is not interactive (non-TTY). Risk detected: MEDIUM",
                gate_result,
                confirm_result,
            )
            return

        confirmed = prompt_medium_confirmation(command, gate_result.reason)
        if not confirmed:
            audit_manager.log_event(
                command=command,
                risk_level=gate_result.risk_level.value,
                gate_decision=gate_result.gate_decision.value,
                policy=gate_result.policy.value,
                confirmation_mode=confirm_result.mode,
                action_type="MEDIUM_DECLINED",
                result="DECLINED",
                notes="User declined interactive confirmation.",
            )
            ui.render_execution_declined(command, "User declined interactive confirmation.")
            return

        audit_manager.log_event(
            command=command,
            risk_level=gate_result.risk_level.value,
            gate_decision=gate_result.gate_decision.value,
            policy=gate_result.policy.value,
            confirmation_mode=confirm_result.mode,
            action_type="MEDIUM_CONFIRMED",
            result="CONFIRMED",
            notes="User granted explicit interactive confirmation.",
        )

    else:
        log_refusal(
            command,
            f"Unsupported risk level for execution: {gate_result.risk_level.value}",
            gate_result,
            confirm_result,
        )
        return

    # 4. Pre-execution Audit
    audit_manager.log_event(
        command=command,
        risk_level=gate_result.risk_level.value,
        gate_decision=gate_result.gate_decision.value,
        policy=gate_result.policy.value,
        confirmation_mode=confirm_result.mode,
        action_type="EXECUTION_START",
        result="STARTED",
        notes="Passing through safety pipeline.",
    )

    # 5. Execution
    try:
        args = shlex.split(command)
        result = subprocess.run(
            args,
            shell=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        exit_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr
        execution_status = "SUCCESS" if exit_code == 0 else "FAILED"

    except subprocess.TimeoutExpired:
        exit_code = -1
        stdout = ""
        stderr = "Error: Command timed out after 10 seconds."
        execution_status = "TIMEOUT"
    except Exception as e:
        exit_code = -1
        stdout = ""
        stderr = f"Error: {str(e)}"
        execution_status = "ERROR"

    # 6. Post-execution Audit
    audit_manager.log_event(
        command=command,
        risk_level=gate_result.risk_level.value,
        gate_decision=gate_result.gate_decision.value,
        policy=gate_result.policy.value,
        confirmation_mode=confirm_result.mode,
        action_type="EXECUTION_END",
        result="SUCCESS" if exit_code == 0 else execution_status,
        notes=f"Exit code: {exit_code}",
    )

    # 7. UI Result
    ui.render_execution_result(command, stdout, stderr, exit_code)
