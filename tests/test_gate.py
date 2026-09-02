import pytest
from ternexar.gate import gate_engine, GateStatus, PolicyDecision
from ternexar.risk import RiskLevel

def test_gate_low():
    result = gate_engine.evaluate("ls")
    assert result.risk_level == RiskLevel.LOW
    assert result.gate_decision == GateStatus.PASS
    assert result.policy == PolicyDecision.ALLOW_PREVIEW

def test_gate_medium():
    result = gate_engine.evaluate("pip install rich")
    assert result.risk_level == RiskLevel.MEDIUM
    assert result.gate_decision == GateStatus.HOLD
    assert result.policy == PolicyDecision.REQUIRE_CONFIRMATION

def test_gate_high():
    result = gate_engine.evaluate("sudo rm test")
    assert result.risk_level == RiskLevel.HIGH
    assert result.gate_decision == GateStatus.HOLD
    assert result.policy == PolicyDecision.REQUIRE_STRONG_CONFIRMATION

def test_gate_blocked():
    result = gate_engine.evaluate("rm -rf /")
    assert result.risk_level == RiskLevel.BLOCKED
    assert result.gate_decision == GateStatus.BLOCK
    assert result.policy == PolicyDecision.DENY


def test_gate_medium_with_shell_control():
    result = gate_engine.evaluate("pip install rich; echo ok")
    assert result.risk_level == RiskLevel.MEDIUM
    assert result.gate_decision == GateStatus.HOLD
    assert result.policy == PolicyDecision.REQUIRE_CONFIRMATION
