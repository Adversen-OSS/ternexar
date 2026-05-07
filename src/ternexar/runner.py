from enum import Enum
from dataclasses import dataclass
from ternexar.gate import gate_engine, GateStatus
from ternexar.confirm import confirm_engine, ConfirmationMode
from ternexar.risk import RiskLevel
from ternexar.audit import audit_manager

class RunnerVerdict(Enum):
    DRY_ELIGIBLE = "DRY_ELIGIBLE"
    HELD = "HELD"
    DENIED = "DENIED"

@dataclass
class RunnerCheckResult:
    command: str
    risk_level: RiskLevel
    gate_decision: GateStatus
    confirmation_mode: str
    verdict: RunnerVerdict
    reason: str

class RunnerSkeleton:
    def evaluate(self, command: str) -> RunnerCheckResult:
        """Evaluate a command through the full safety pipeline without execution."""
        gate_result = gate_engine.evaluate(command)
        confirm_result = confirm_engine.evaluate(command)
        
        # Mapping logic as per v0.8 requirements
        if (gate_result.risk_level == RiskLevel.LOW and 
            gate_result.gate_decision == GateStatus.PASS and 
            confirm_result.mode == ConfirmationMode.MINIMAL_CONFIRMATION.value):
            verdict = RunnerVerdict.DRY_ELIGIBLE
        elif gate_result.gate_decision == GateStatus.BLOCK or confirm_result.mode == ConfirmationMode.REFUSED.value:
            verdict = RunnerVerdict.DENIED
        else:
            verdict = RunnerVerdict.HELD

        result = RunnerCheckResult(
            command=command,
            risk_level=gate_result.risk_level,
            gate_decision=gate_result.gate_decision,
            confirmation_mode=confirm_result.mode,
            verdict=verdict,
            reason=gate_result.reason
        )

        # Log to audit
        audit_manager.log_event(
            command=command,
            risk_level=gate_result.risk_level.value,
            gate_decision=gate_result.gate_decision.value,
            policy=gate_result.policy.value,
            confirmation_mode=confirm_result.mode,
            action_type="RUNNER_DRY_CHECK",
            result=verdict.value,
            notes=gate_result.reason
        )

        return result

runner_skeleton = RunnerSkeleton()
