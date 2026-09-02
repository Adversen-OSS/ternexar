import pytest
from ternexar.risk import (
    RiskLevel,
    SupportedMediumInstall,
    contains_forbidden_elements,
    parse_supported_medium_install,
    recognize_medium_install_intent,
    risk_engine,
)


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
    assert recognize_medium_install_intent(cmd) is True
    assert parse_supported_medium_install(cmd) is not None


@pytest.mark.parametrize(
    "cmd,expected_binary,expected_subcmd,expected_argv",
    [
        ("PIP install rich", "PIP", "install", ["PIP", "install", "rich"]),
        ("Pip install rich", "Pip", "install", ["Pip", "install", "rich"]),
        ("pip INSTALL rich", "pip", "INSTALL", ["pip", "INSTALL", "rich"]),
        ("NPM i lodash", "NPM", "i", ["NPM", "i", "lodash"]),
        ("npm INSTALL lodash", "npm", "INSTALL", ["npm", "INSTALL", "lodash"]),
        ("YARN add lodash", "YARN", "add", ["YARN", "add", "lodash"]),
        ("Yarn Install", "Yarn", "Install", ["Yarn", "Install"]),
        ("CARGO install ripgrep", "CARGO", "install", ["CARGO", "install", "ripgrep"]),
    ],
)
def test_risk_medium_cased_package_installs(cmd, expected_binary, expected_subcmd, expected_argv):
    analysis = risk_engine.analyze(cmd)
    assert analysis.level == RiskLevel.MEDIUM
    assert any(m.label == "Package Installation" for m in analysis.matches)
    assert recognize_medium_install_intent(cmd) is True

    parsed = parse_supported_medium_install(cmd)
    assert parsed is not None
    assert parsed.binary == expected_binary
    assert parsed.subcommand == expected_subcmd
    assert parsed.argv == expected_argv


@pytest.mark.parametrize(
    "cmd",
    [
        'pip install "Django<5"',
        'pip install "Django<=5"',
        'pip install "Django>4"',
        'pip install "Django>=4"',
        'pip install "Django==5.0"',
        'pip install "Django!=4.2"',
        'pip install "requests>=2,<3"',
        'pip install "pkg>=1"',
        'pip3 install "urllib3<3"',
        'npm install "example@>=1"',
        'npm i "example@<2"',
        'yarn add "example@>=1"',
        'yarn add "example@<2"',
        'pip install "requests[security]"',
        'pip install "importlib-metadata; python_version < \'3.8\'"',
    ],
)
def test_risk_medium_version_constrained_package_installs(cmd):
    analysis = risk_engine.analyze(cmd)
    assert analysis.level == RiskLevel.MEDIUM
    assert any(m.label == "Package Installation" for m in analysis.matches)
    assert recognize_medium_install_intent(cmd) is True
    assert parse_supported_medium_install(cmd) is not None


@pytest.mark.parametrize(
    "cmd",
    [
        "pip install rich ; whoami",
        "pip install rich;whoami",
        "pip install rich && whoami",
        "pip install rich&&whoami",
        "pip install rich || whoami",
        "pip install rich||whoami",
        "pip install rich | cat",
        "pip install rich|cat",
        "pip install rich > output.txt",
        "pip install rich>output.txt",
        "pip install rich >> output.txt",
        "pip install rich>>output.txt",
        "pip install rich < requirements.txt",
        "pip install rich<requirements.txt",
        "pip install rich `whoami`",
        "pip install rich $(whoami)",
        'pip install "$(whoami)"',
        'pip install "`whoami`"',
        "pip install rich &",
        "(pip install rich)",
        "pip install Django<5",
        "pip install Django>4",
        "pip install requests>=2,<3",
        'pip install "unterminated',
    ],
)
def test_risk_medium_package_installs_with_shell_control_classified_medium(cmd):
    """Commands expressing package-install intent must classify as MEDIUM risk even if shell control is present."""
    analysis = risk_engine.analyze(cmd)
    assert analysis.level == RiskLevel.MEDIUM
    assert any(m.label == "Package Installation" for m in analysis.matches)
    assert recognize_medium_install_intent(cmd) is True
    # But strict execution grammar must refuse execution eligibility
    assert parse_supported_medium_install(cmd) is None


@pytest.mark.parametrize(
    "cmd",
    [
        "pip add rich",
        "pip i rich",
        "npm add lodash",
        "yarn i lodash",
        "cargo add ripgrep",
        "cargo i ripgrep",
        "pip list",
        "pip show rich",
        "pip uninstall rich",
        "npm list",
        "npm remove lodash",
        "yarn remove lodash",
        "cargo uninstall ripgrep",
    ],
)
def test_risk_unsupported_package_manager_shapes(cmd):
    analysis = risk_engine.analyze(cmd)
    assert not any(m.label == "Package Installation" for m in analysis.matches)
    assert analysis.level == RiskLevel.LOW
    assert recognize_medium_install_intent(cmd) is False
    assert parse_supported_medium_install(cmd) is None


@pytest.mark.parametrize(
    "cmd",
    [
        "",
        "   ",
    ],
)
def test_risk_empty_inputs(cmd):
    analysis = risk_engine.analyze(cmd)
    assert not any(m.label == "Package Installation" for m in analysis.matches)
    assert analysis.level == RiskLevel.LOW
    assert recognize_medium_install_intent(cmd) is False
    assert parse_supported_medium_install(cmd) is None


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


def test_higher_risk_precedence():
    """Higher risk rules (HIGH, BLOCKED) must take precedence over MEDIUM package install intent."""
    # sudo + pip install -> HIGH
    analysis_sudo = risk_engine.analyze("pip install foo && sudo whoami")
    assert analysis_sudo.level == RiskLevel.HIGH
    labels_sudo = {m.label for m in analysis_sudo.matches}
    assert "Package Installation" in labels_sudo
    assert "Superuser Access" in labels_sudo

    # sudo pip install -> HIGH
    analysis_sudo_pip = risk_engine.analyze("sudo pip install rich")
    assert analysis_sudo_pip.level == RiskLevel.HIGH

    # rm -rf / + pip install -> BLOCKED
    analysis_blocked = risk_engine.analyze("rm -rf / ; pip install rich")
    assert analysis_blocked.level == RiskLevel.BLOCKED
    labels_blocked = {m.label for m in analysis_blocked.matches}
    assert "Package Installation" in labels_blocked
    assert "Root Deletion" in labels_blocked


def test_supported_medium_install_argv_property():
    install = SupportedMediumInstall(
        binary="pip",
        subcommand="install",
        args=["requests>=2,<3", "--no-deps"],
    )
    assert install.argv == ["pip", "install", "requests>=2,<3", "--no-deps"]


@pytest.mark.parametrize(
    "cmd,expected_risk,expected_eligible",
    [
        ("pip install rich", RiskLevel.MEDIUM, True),
        ("pip install rich; echo ok", RiskLevel.MEDIUM, False),
        ("pip install rich > out", RiskLevel.MEDIUM, False),
        ('pip install "$(whoami)"', RiskLevel.MEDIUM, False),
        ("npm i lodash", RiskLevel.MEDIUM, True),
        ("npm i lodash && whoami", RiskLevel.MEDIUM, False),
        ("yarn add lodash", RiskLevel.MEDIUM, True),
        ("cargo install ripgrep", RiskLevel.MEDIUM, True),
        ("pip list", RiskLevel.LOW, False),
        ("my_tool delete", RiskLevel.MEDIUM, False),
    ],
)
def test_risk_vs_eligibility_matrix(cmd, expected_risk, expected_eligible):
    """Verify the decoupling of risk recognition from execution eligibility."""
    analysis = risk_engine.analyze(cmd)
    assert analysis.level == expected_risk
    parsed = parse_supported_medium_install(cmd)
    assert (parsed is not None) is expected_eligible


@pytest.mark.parametrize(
    "cmd,expected_forbidden",
    [
        ('pip install "Django<5"', False),
        ('pip install "requests>=2,<3"', False),
        ('pip install "pkg>=1"', False),
        ('npm install "example@>=1"', False),
        ('yarn add "example@<2"', False),
        ("ls -la", False),
        ("git status", False),
        ("pip install rich ; whoami", True),
        ("pip install rich;whoami", True),
        ("pip install rich && whoami", True),
        ("pip install rich&&whoami", True),
        ("pip install rich || whoami", True),
        ("pip install rich||whoami", True),
        ("pip install rich | cat", True),
        ("pip install rich|cat", True),
        ("pip install rich > output.txt", True),
        ("pip install rich>output.txt", True),
        ("pip install rich >> output.txt", True),
        ("pip install rich>>output.txt", True),
        ("pip install rich < requirements.txt", True),
        ("pip install rich<requirements.txt", True),
        ("pip install rich `whoami`", True),
        ("pip install rich $(whoami)", True),
        ('pip install "$(whoami)"', True),
        ('pip install "`whoami`"', True),
        ("pip install rich &", True),
        ("(pip install rich)", True),
        ("pip install Django<5", True),
        ("pip install Django>4", True),
        ("pip install requests>=2,<3", True),
        ("", True),
        ("   ", True),
        ('pip install "unterminated', True),
    ],
)
def test_contains_forbidden_elements_matrix(cmd, expected_forbidden):
    assert contains_forbidden_elements(cmd) is expected_forbidden


def test_unexpected_parser_exceptions_not_swallowed(monkeypatch):
    """Unexpected exceptions during parsing must propagate and not be silently swallowed."""
    def raise_runtime_error(*args, **kwargs):
        raise RuntimeError("unexpected parser failure")

    monkeypatch.setattr("shlex.split", raise_runtime_error)
    with pytest.raises(RuntimeError, match="unexpected parser failure"):
        parse_supported_medium_install("pip install rich")
