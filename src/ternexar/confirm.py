from enum import Enum
from dataclasses import dataclass
from ternexar.gate import gate_engine, PolicyDecision
from ternexar.risk import RiskLevel
from ternexar.ui import ui

class ConfirmationMode(Enum):
    MINIMAL_CONFIRMATION = "MINIMAL_CONFIRMATION"
    STANDARD_CONFIRMATION = "STANDARD_CONFIRMATION"
    STRONG_CONFIRMATION = "STRONG_CONFIRMATION"
    REFUSED = "REFUSED"

@dataclass
class ConfirmationResult:
    command: str
    risk_level: RiskLevel
    gate_decision: str
    policy: PolicyDecision
    mode: str
    future_behavior: str
    reason: str
    recommendation: str

class ConfirmationEngine:
    def map_policy_to_mode(self, policy: PolicyDecision) -> ConfirmationMode:
        return {
            PolicyDecision.ALLOW_PREVIEW: ConfirmationMode.MINIMAL_CONFIRMATION,
            PolicyDecision.REQUIRE_CONFIRMATION: ConfirmationMode.STANDARD_CONFIRMATION,
            PolicyDecision.REQUIRE_STRONG_CONFIRMATION: ConfirmationMode.STRONG_CONFIRMATION,
            PolicyDecision.DENY: ConfirmationMode.REFUSED,
        }[policy]

    def get_future_behavior(self, mode: ConfirmationMode) -> str:
        return {
            ConfirmationMode.MINIMAL_CONFIRMATION: "Eligible for future execution with visible/auditable minimal confirmation.",
            ConfirmationMode.STANDARD_CONFIRMATION: "Future 'tx do' must ask [y/N].",
            ConfirmationMode.STRONG_CONFIRMATION: "Future 'tx do' must require typing 'CONFIRM'.",
            ConfirmationMode.REFUSED: "Confirmation unavailable; command denied.",
        }[mode]

    def evaluate(self, command: str) -> ConfirmationResult:
        gate_result = gate_engine.evaluate(command)
        mode = self.map_policy_to_mode(gate_result.policy)
        future_behavior = self.get_future_behavior(mode)
        
        # Get recommendation from risk engine matches if available
        # We need to re-analyze or just use gate_result if it had more info.
        # gate_result has reason.
        
        # For recommendation, we can look at risk engine matches
        from ternexar.risk import risk_engine
        analysis = risk_engine.analyze(command)
        recommendation = "Follow standard safe practices."
        if analysis.matches:
            # Get the highest risk match's alternative
            sorted_matches = sorted(
                analysis.matches, 
                key=lambda m: list(RiskLevel).index(m.level), 
                reverse=True
            )
            recommendation = sorted_matches[0].alternative or recommendation

        return ConfirmationResult(
            command=command,
            risk_level=gate_result.risk_level,
            gate_decision=gate_result.gate_decision,
            policy=gate_result.policy,
            mode=mode.value,
            future_behavior=future_behavior,
            reason=gate_result.reason,
            recommendation=recommendation
        )

confirm_engine = ConfirmationEngine()

def handle_confirm(command: str):
    result = confirm_engine.evaluate(command)
    ui.render_confirmation_report(result)
