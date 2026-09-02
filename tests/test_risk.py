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
    ],
)
def test_risk_medium_shell_control_rejected_from_package_installs(cmd):
    analysis = risk_engine.analyze(cmd)
    assert not any(m.label == "Package Installation" for m in analysis.matches)


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


def test_supported_medium_install_argv_property():
    from ternexar.risk import SupportedMediumInstall
    install = SupportedMediumInstall(
        binary="pip",
        subcommand="install",
        args=["requests>=2,<3", "--no-deps"],
    )
    assert install.argv == ["pip", "install", "requests>=2,<3", "--no-deps"]


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
    from ternexar.risk import contains_forbidden_elements
    assert contains_forbidden_elements(cmd) is expected_forbidden
