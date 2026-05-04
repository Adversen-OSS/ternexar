from enum import Enum
from dataclasses import dataclass
from typing import List, Optional
from ternexar.risk import risk_engine, RiskLevel, RiskAnalysis
from ternexar.ui import ui

class PolicyDecision(Enum):
    ALLOW_PREVIEW = "ALLOW_PREVIEW"
    REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"
    REQUIRE_STRONG_CONFIRMATION = "REQUIRE_STRONG_CONFIRMATION"
    DENY = "DENY"

class GateStatus(Enum):
    PASS = "PASS"
    HOLD = "HOLD"
    BLOCK = "BLOCK"

@dataclass
class GateResult:
    command: str
    risk_level: RiskLevel
    matched_patterns: List[str]
    policy: PolicyDecision
    gate_decision: GateStatus
    reason: str
    future_instruction: str

class GateEngine:
    def map_risk_to_policy(self, risk_level: RiskLevel) -> PolicyDecision:
        return {
            RiskLevel.LOW: PolicyDecision.ALLOW_PREVIEW,
            RiskLevel.MEDIUM: PolicyDecision.REQUIRE_CONFIRMATION,
            RiskLevel.HIGH: PolicyDecision.REQUIRE_STRONG_CONFIRMATION,
            RiskLevel.BLOCKED: PolicyDecision.DENY,
        }[risk_level]

    def map_policy_to_gate(self, policy: PolicyDecision) -> GateStatus:
        return {
            PolicyDecision.ALLOW_PREVIEW: GateStatus.PASS,
            PolicyDecision.REQUIRE_CONFIRMATION: GateStatus.HOLD,
            PolicyDecision.REQUIRE_STRONG_CONFIRMATION: GateStatus.HOLD,
            PolicyDecision.DENY: GateStatus.BLOCK,
        }[policy]

    def get_future_instruction(self, policy: PolicyDecision) -> str:
        return {
            PolicyDecision.ALLOW_PREVIEW: "Eligible for future execution with minimal confirmation.",
            PolicyDecision.REQUIRE_CONFIRMATION: "Future 'tx do' will require standard [y/N] confirmation.",
            PolicyDecision.REQUIRE_STRONG_CONFIRMATION: "Future 'tx do' will require typing 'confirm' to proceed.",
            PolicyDecision.DENY: "Future 'tx do' will refuse to execute this command.",
        }[policy]

    def evaluate(self, command: str) -> GateResult:
        analysis = risk_engine.analyze(command)
        policy = self.map_risk_to_policy(analysis.level)
        gate_decision = self.map_policy_to_gate(policy)
        future_instruction = self.get_future_instruction(policy)
        
        matched_patterns = [m.label for m in analysis.matches]
        if not matched_patterns:
            matched_patterns = ["No specific risky patterns"]

        # Reason logic: Use the highest-risk match or a default
        if analysis.matches:
            # Sort matches by risk level to get the highest one for the reason
            # (RiskLevel enum order is LOW, MEDIUM, HIGH, BLOCKED)
            sorted_matches = sorted(
                analysis.matches, 
                key=lambda m: list(RiskLevel).index(m.level), 
                reverse=True
            )
            reason = sorted_matches[0].reason
        else:
            reason = "Command follows standard safe patterns."

        return GateResult(
            command=command,
            risk_level=analysis.level,
            matched_patterns=matched_patterns,
            policy=policy,
            gate_decision=gate_decision,
            reason=reason,
            future_instruction=future_instruction
        )

gate_engine = GateEngine()

def handle_gate(command: str):
    result = gate_engine.evaluate(command)
    ui.render_gate_report(result)
