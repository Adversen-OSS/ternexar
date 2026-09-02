import subprocess
from unittest.mock import MagicMock, patch
import pytest
from ternexar.do import (
    LOW_EXECUTION_TIMEOUT_SECONDS,
    MEDIUM_INSTALL_TIMEOUT_SECONDS,
    STRICT_ALLOWLIST,
    handle_do,
    is_medium_execution_eligible,
)
from ternexar.risk import RiskLevel, risk_engine


@pytest.fixture
def mock_ui():
    with patch("ternexar.do.ui") as mock:
        yield mock


@pytest.fixture
def mock_audit():
    with patch("ternexar.do.audit_manager") as mock:
        yield mock


@pytest.fixture
def mock_run():
    with patch("subprocess.run") as mock:
        mock.return_value = MagicMock(returncode=0, stdout="Success", stderr="")
        yield mock


def test_do_allowlisted(mock_run, mock_ui, mock_audit):
    # Test a clearly allowlisted command
    handle_do("ls -la")

    # Verify subprocess.run was called with shell=False and timeout=10
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0] == ["ls", "-la"]
    assert kwargs["shell"] is False
    assert kwargs["timeout"] == LOW_EXECUTION_TIMEOUT_SECONDS

    # Verify UI render
    mock_ui.render_execution_result.assert_called_once()


def test_do_not_allowlisted(mock_run, mock_ui, mock_audit):
    # Test a command NOT in allowlist
    handle_do("touch newfile")

    # Verify subprocess.run was NOT called
    mock_run.assert_not_called()

    # Verify refusal UI
    mock_ui.render_refusal.assert_called_once()
    args = mock_ui.render_refusal.call_args[0]
    assert "not in the strict v1.0 allowlist" in args[1]


def test_do_dangerous_risk(mock_run, mock_ui, mock_audit):
    # Test a MEDIUM risk command in non-interactive mode
    handle_do("pip install rich")

    mock_run.assert_not_called()
    mock_ui.render_refusal.assert_called_once()
    args = mock_ui.render_refusal.call_args[0]
    assert "Risk detected: MEDIUM" in args[1]


def test_do_medium_interactive_confirmed(mock_run, mock_ui, mock_audit, monkeypatch):
    monkeypatch.setattr("ternexar.do.is_interactive_terminal", lambda: True)
    monkeypatch.setattr("ternexar.do.prompt_medium_confirmation", lambda cmd, reason: True)

    handle_do("pip install rich")

    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0] == ["pip", "install", "rich"]
    assert kwargs["shell"] is False
    assert kwargs["timeout"] == MEDIUM_INSTALL_TIMEOUT_SECONDS

    # Check audit calls: MEDIUM_CONFIRMED, EXECUTION_START, EXECUTION_END
    actions = [call.kwargs.get("action_type") for call in mock_audit.log_event.call_args_list]
    assert "MEDIUM_CONFIRMED" in actions
    assert "EXECUTION_START" in actions
    assert "EXECUTION_END" in actions
    mock_ui.render_execution_result.assert_called_once()


def test_do_medium_interactive_declined(mock_run, mock_ui, mock_audit, monkeypatch):
    monkeypatch.setattr("ternexar.do.is_interactive_terminal", lambda: True)
    monkeypatch.setattr("ternexar.do.prompt_medium_confirmation", lambda cmd, reason: False)

    handle_do("pip install rich")

    mock_run.assert_not_called()
    actions = [call.kwargs.get("action_type") for call in mock_audit.log_event.call_args_list]
    assert "MEDIUM_DECLINED" in actions
    assert "EXECUTION_START" not in actions
    mock_ui.render_execution_declined.assert_called_once()


def test_do_medium_shell_injection_blocked_before_prompt(mock_run, mock_ui, mock_audit, monkeypatch):
    prompt_mock = MagicMock()
    monkeypatch.setattr("ternexar.do.is_interactive_terminal", lambda: True)
    monkeypatch.setattr("ternexar.do.prompt_medium_confirmation", prompt_mock)

    handle_do("pip install rich; rm -rf /")

    prompt_mock.assert_not_called()
    mock_run.assert_not_called()
    mock_ui.render_refusal.assert_called_once()
    args = mock_ui.render_refusal.call_args[0]
    assert "forbidden shell characters" in args[1]


def test_do_medium_command_identity_preserved(mock_run, mock_ui, mock_audit, monkeypatch):
    monkeypatch.setattr("ternexar.do.is_interactive_terminal", lambda: True)
    prompt_calls = []

    def tracking_prompt(cmd, reason):
        prompt_calls.append(cmd)
        return True

    monkeypatch.setattr("ternexar.do.prompt_medium_confirmation", tracking_prompt)

    cmd = "pip install --no-deps requests"
    handle_do(cmd)

    assert prompt_calls == [cmd]
    args, kwargs = mock_run.call_args
    assert args[0] == ["pip", "install", "--no-deps", "requests"]
    assert kwargs["timeout"] == MEDIUM_INSTALL_TIMEOUT_SECONDS


def test_do_blocked_risk(mock_run, mock_ui, mock_audit):
    # Test a BLOCKED command
    handle_do("rm -rf /")

    mock_run.assert_not_called()
    mock_ui.render_refusal.assert_called_once()
    args = mock_ui.render_refusal.call_args[0]
    assert "Risk detected: BLOCKED" in args[1]


def test_do_shell_injection(mock_run, mock_ui, mock_audit):
    # Test shell chaining
    handle_do("ls; rm -rf /")

    mock_run.assert_not_called()
    mock_ui.render_refusal.assert_called_once()
    args = mock_ui.render_refusal.call_args[0]
    assert "forbidden shell characters" in args[1]


def test_do_timeout_low(mock_run, mock_ui, mock_audit):
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="ls", timeout=LOW_EXECUTION_TIMEOUT_SECONDS)

    handle_do("ls")

    mock_ui.render_execution_result.assert_called_once()
    args = mock_ui.render_execution_result.call_args[0]
    assert "timed out after 10 seconds" in args[2]  # stderr
    assert mock_run.call_args.kwargs["timeout"] == 10

    # Verify audit event recorded as TIMEOUT
    end_event = [call.kwargs for call in mock_audit.log_event.call_args_list if call.kwargs.get("action_type") == "EXECUTION_END"][0]
    assert end_event["result"] == "TIMEOUT"


def test_do_timeout_medium(mock_run, mock_ui, mock_audit, monkeypatch):
    monkeypatch.setattr("ternexar.do.is_interactive_terminal", lambda: True)
    monkeypatch.setattr("ternexar.do.prompt_medium_confirmation", lambda cmd, reason: True)
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="pip install rich", timeout=MEDIUM_INSTALL_TIMEOUT_SECONDS)

    handle_do("pip install rich")

    mock_ui.render_execution_result.assert_called_once()
    args = mock_ui.render_execution_result.call_args[0]
    assert "timed out after 600 seconds" in args[2]  # stderr
    assert mock_run.call_args.kwargs["timeout"] == 600

    # Verify audit event recorded as TIMEOUT
    end_event = [call.kwargs for call in mock_audit.log_event.call_args_list if call.kwargs.get("action_type") == "EXECUTION_END"][0]
    assert end_event["result"] == "TIMEOUT"


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
def test_medium_parity_matrix(cmd):
    """Test that all advertised MEDIUM commands classify MEDIUM and are execution-eligible."""
    assert risk_engine.analyze(cmd).level == RiskLevel.MEDIUM
    assert is_medium_execution_eligible(cmd) is True


@pytest.mark.parametrize(
    "cmd,expected_args",
    [
        ("pip3 install rich", ["pip3", "install", "rich"]),
        ("npm i lodash", ["npm", "i", "lodash"]),
        ("npm install lodash", ["npm", "install", "lodash"]),
        ("yarn install", ["yarn", "install"]),
        ("yarn add lodash", ["yarn", "add", "lodash"]),
        ("cargo install ripgrep", ["cargo", "install", "ripgrep"]),
    ],
)
def test_medium_aliases_interactive_execution(mock_run, mock_ui, mock_audit, monkeypatch, cmd, expected_args):
    """Test that representative aliases execute once when confirmed, and zero times when declined."""
    monkeypatch.setattr("ternexar.do.is_interactive_terminal", lambda: True)

    # 1. Confirmed -> executes once
    monkeypatch.setattr("ternexar.do.prompt_medium_confirmation", lambda c, r: True)
    handle_do(cmd)
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0] == expected_args
    assert kwargs["shell"] is False
    assert kwargs["timeout"] == 600

    mock_run.reset_mock()
    mock_audit.reset_mock()
    mock_ui.reset_mock()

    # 2. Declined -> executes zero times
    monkeypatch.setattr("ternexar.do.prompt_medium_confirmation", lambda c, r: False)
    handle_do(cmd)
    mock_run.assert_not_called()
    actions = [call.kwargs.get("action_type") for call in mock_audit.log_event.call_args_list]
    assert "MEDIUM_DECLINED" in actions
    assert "EXECUTION_START" not in actions


@pytest.mark.parametrize(
    "cmd,expected_args",
    [
        ("PIP install rich", ["PIP", "install", "rich"]),
        ("Pip install rich", ["Pip", "install", "rich"]),
        ("NPM i lodash", ["NPM", "i", "lodash"]),
        ("YARN add lodash", ["YARN", "add", "lodash"]),
        ("pip INSTALL rich", ["pip", "INSTALL", "rich"]),
        ("Yarn Install", ["Yarn", "Install"]),
        ("CARGO install ripgrep", ["CARGO", "install", "ripgrep"]),
    ],
)
def test_cased_commands_exact_argv_execution(mock_run, mock_ui, mock_audit, monkeypatch, cmd, expected_args):
    """Test that cased package manager and subcommand tokens preserve exact argv casing upon execution."""
    assert risk_engine.analyze(cmd).level == RiskLevel.MEDIUM
    assert is_medium_execution_eligible(cmd) is True

    monkeypatch.setattr("ternexar.do.is_interactive_terminal", lambda: True)
    monkeypatch.setattr("ternexar.do.prompt_medium_confirmation", lambda c, r: True)

    handle_do(cmd)
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0] == expected_args
    assert kwargs["shell"] is False
    assert kwargs["timeout"] == MEDIUM_INSTALL_TIMEOUT_SECONDS


def test_cross_consumer_consistency_shell_chained_install(mock_run, mock_ui, mock_audit, monkeypatch):
    """Verify internal coherence across risk_engine, gate_engine, confirm_engine, runner_skeleton, and handle_do."""
    from ternexar.gate import gate_engine, GateStatus, PolicyDecision
    from ternexar.confirm import confirm_engine, ConfirmationMode
    from ternexar.runner import runner_skeleton, RunnerVerdict

    cmd = "pip install rich; echo ok"

    # 1. Risk Engine: identifies install intent -> MEDIUM
    analysis = risk_engine.analyze(cmd)
    assert analysis.level == RiskLevel.MEDIUM
    assert any(m.label == "Package Installation" for m in analysis.matches)

    # 2. Gate Engine: HOLD / REQUIRE_CONFIRMATION (NOT LOW / PASS)
    gate_result = gate_engine.evaluate(cmd)
    assert gate_result.risk_level == RiskLevel.MEDIUM
    assert gate_result.gate_decision == GateStatus.HOLD
    assert gate_result.policy == PolicyDecision.REQUIRE_CONFIRMATION

    # 3. Confirm Engine: STANDARD_CONFIRMATION (NOT MINIMAL_CONFIRMATION)
    confirm_result = confirm_engine.evaluate(cmd)
    assert confirm_result.mode == ConfirmationMode.STANDARD_CONFIRMATION.value

    # 4. Runner Skeleton: HELD (NOT DRY_ELIGIBLE)
    runner_result = runner_skeleton.evaluate(cmd)
    assert runner_result.verdict == RunnerVerdict.HELD
    assert runner_result.risk_level == RiskLevel.MEDIUM

    # 5. Execution Eligibility: False
    assert is_medium_execution_eligible(cmd) is False

    # 6. handle_do: Refused without prompting or subprocess execution
    prompt_mock = MagicMock()
    monkeypatch.setattr("ternexar.do.is_interactive_terminal", lambda: True)
    monkeypatch.setattr("ternexar.do.prompt_medium_confirmation", prompt_mock)

    handle_do(cmd)
    prompt_mock.assert_not_called()
    mock_run.assert_not_called()
    mock_ui.render_refusal.assert_called_once()
    actions = [call.kwargs.get("action_type") for call in mock_audit.log_event.call_args_list]
    assert "EXECUTION_REFUSED" in actions


@pytest.mark.parametrize(
    "cmd",
    [
        "pip install foo && sudo whoami",
        "sudo pip install rich",
        "rm -rf / ; pip install rich",
    ],
)
def test_higher_risk_install_commands_refused(mock_run, mock_ui, mock_audit, monkeypatch, cmd):
    """Commands combining install intent with HIGH/BLOCKED triggers must be refused execution."""
    prompt_mock = MagicMock()
    monkeypatch.setattr("ternexar.do.is_interactive_terminal", lambda: True)
    monkeypatch.setattr("ternexar.do.prompt_medium_confirmation", prompt_mock)

    handle_do(cmd)
    prompt_mock.assert_not_called()
    mock_run.assert_not_called()
    mock_ui.render_refusal.assert_called_once()


@pytest.mark.parametrize(
    "cmd,expected_args",
    [
        ('pip install "Django<5"', ["pip", "install", "Django<5"]),
        ('pip install "Django<=5"', ["pip", "install", "Django<=5"]),
        ('pip install "Django>4"', ["pip", "install", "Django>4"]),
        ('pip install "Django>=4"', ["pip", "install", "Django>=4"]),
        ('pip install "Django==5.0"', ["pip", "install", "Django==5.0"]),
        ('pip install "Django!=4.2"', ["pip", "install", "Django!=4.2"]),
        ('pip install "requests>=2,<3"', ["pip", "install", "requests>=2,<3"]),
        ('pip install "pkg>=1"', ["pip", "install", "pkg>=1"]),
        ('pip3 install "urllib3<3"', ["pip3", "install", "urllib3<3"]),
        ('npm install "example@>=1"', ["npm", "install", "example@>=1"]),
        ('npm i "example@<2"', ["npm", "i", "example@<2"]),
        ('yarn add "example@>=1"', ["yarn", "add", "example@>=1"]),
        ('yarn add "example@<2"', ["yarn", "add", "example@<2"]),
    ],
)
def test_version_constraints_medium_execution(mock_run, mock_ui, mock_audit, monkeypatch, cmd, expected_args):
    """Test that legitimate version constraints in MEDIUM package installs are authorized and executed."""
    assert risk_engine.analyze(cmd).level == RiskLevel.MEDIUM
    assert is_medium_execution_eligible(cmd) is True

    monkeypatch.setattr("ternexar.do.is_interactive_terminal", lambda: True)

    # 1. Confirmed -> executes once with exact argv, shell=False, timeout=600
    monkeypatch.setattr("ternexar.do.prompt_medium_confirmation", lambda c, r: True)
    handle_do(cmd)
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0] == expected_args
    assert kwargs["shell"] is False
    assert kwargs["timeout"] == 600

    mock_run.reset_mock()
    mock_audit.reset_mock()
    mock_ui.reset_mock()

    # 2. Declined -> executes zero times
    monkeypatch.setattr("ternexar.do.prompt_medium_confirmation", lambda c, r: False)
    handle_do(cmd)
    mock_run.assert_not_called()
    actions = [call.kwargs.get("action_type") for call in mock_audit.log_event.call_args_list]
    assert "MEDIUM_DECLINED" in actions
    assert "EXECUTION_START" not in actions



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
def test_unsupported_package_manager_shapes_refused(mock_run, mock_ui, mock_audit, monkeypatch, cmd):
    """Unsupported package manager shapes must not obtain MEDIUM execution eligibility."""
    assert is_medium_execution_eligible(cmd) is False

    prompt_mock = MagicMock()
    monkeypatch.setattr("ternexar.do.is_interactive_terminal", lambda: True)
    monkeypatch.setattr("ternexar.do.prompt_medium_confirmation", prompt_mock)

    handle_do(cmd)

    prompt_mock.assert_not_called()
    mock_run.assert_not_called()
    mock_ui.render_refusal.assert_called_once()
    actions = [call.kwargs.get("action_type") for call in mock_audit.log_event.call_args_list]
    assert "EXECUTION_REFUSED" in actions


def test_original_security_bypass_prevented(mock_run, mock_ui, mock_audit, monkeypatch):
    prompt_mock = MagicMock()
    monkeypatch.setattr("ternexar.do.is_interactive_terminal", lambda: True)
    monkeypatch.setattr("ternexar.do.prompt_medium_confirmation", prompt_mock)

    command = 'python -c "print(\'delete\')"'
    assert risk_engine.analyze(command).level == RiskLevel.MEDIUM

    handle_do(command)

    prompt_mock.assert_not_called()
    mock_run.assert_not_called()
    mock_ui.render_refusal.assert_called_once()
    args = mock_ui.render_refusal.call_args[0]
    assert "not execution-eligible" in args[1]


@pytest.mark.parametrize(
    "cmd",
    [
        'python -c "print(\'delete\')"',
        'python3 -c "import os; os.system(\'delete\')"',
        'sh -c "echo delete"',
        'bash -c "rm -rf delete"',
        'zsh -c "echo delete"',
        'my_tool delete',
        'rm -rf ./tmp_build',
        'git clean -fd',
    ],
)
def test_non_eligible_medium_commands_refused(mock_run, mock_ui, mock_audit, monkeypatch, cmd):
    prompt_mock = MagicMock()
    monkeypatch.setattr("ternexar.do.is_interactive_terminal", lambda: True)
    monkeypatch.setattr("ternexar.do.prompt_medium_confirmation", prompt_mock)

    handle_do(cmd)

    prompt_mock.assert_not_called()
    mock_run.assert_not_called()
    mock_ui.render_refusal.assert_called_once()
    actions = [call.kwargs.get("action_type") for call in mock_audit.log_event.call_args_list]
    assert "EXECUTION_REFUSED" in actions


@pytest.mark.parametrize(
    "malformed_cmd",
    [
        "",
        "   ",
        'pip install "unterminated',
        'pip3 install "unclosed quote',
        'npm install \'unclosed',
    ],
)
def test_malformed_and_empty_commands_refused(mock_run, mock_ui, mock_audit, monkeypatch, malformed_cmd):
    prompt_mock = MagicMock()
    monkeypatch.setattr("ternexar.do.is_interactive_terminal", lambda: True)
    monkeypatch.setattr("ternexar.do.prompt_medium_confirmation", prompt_mock)

    handle_do(malformed_cmd)

    prompt_mock.assert_not_called()
    mock_run.assert_not_called()
    mock_ui.render_refusal.assert_called_once()
    actions = [call.kwargs.get("action_type") for call in mock_audit.log_event.call_args_list]
    assert "EXECUTION_REFUSED" in actions


@pytest.mark.parametrize(
    "shell_cmd",
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
        "pip install rich & whoami",
        "(pip install rich)",
        "pip install (whoami)",
        "pip install Django<5",
        "pip install Django>4",
        "pip install requests>=2,<3",
    ],
)
def test_shell_control_negative_matrix(mock_run, mock_ui, mock_audit, monkeypatch, shell_cmd):
    """Commands with unquoted shell control, redirections, or substitutions must be refused."""
    prompt_mock = MagicMock()
    monkeypatch.setattr("ternexar.do.is_interactive_terminal", lambda: True)
    monkeypatch.setattr("ternexar.do.prompt_medium_confirmation", prompt_mock)

    handle_do(shell_cmd)

    prompt_mock.assert_not_called()
    mock_run.assert_not_called()
    mock_ui.render_refusal.assert_called_once()
    actions = [call.kwargs.get("action_type") for call in mock_audit.log_event.call_args_list]
    assert "EXECUTION_REFUSED" in actions


def test_literal_rich_markup_command_rendering(mock_run, monkeypatch):
    from ternexar.ui import ui

    monkeypatch.setattr("ternexar.do.is_interactive_terminal", lambda: True)
    monkeypatch.setattr("ternexar.do.prompt_medium_confirmation", lambda cmd, reason: True)

    # Command containing Rich markup syntax e.g. brackets, tags, version bounds
    cmd = 'pip install "requests[security]" "[bold red]test[/]" "[conceal]text[/conceal]" "Django<5" "requests>=2,<3"'
    handle_do(cmd)

    mock_run.assert_called_once()
    args, _ = mock_run.call_args
    assert args[0] == [
        "pip",
        "install",
        "requests[security]",
        "[bold red]test[/]",
        "[conceal]text[/conceal]",
        "Django<5",
        "requests>=2,<3",
    ]

    # Verify ui methods render literal text without throwing markup exception
    ui.render_medium_confirmation_header(cmd, "Package Installation")
    ui.render_execution_declined(cmd, "User declined")
    ui.render_minimal_confirmation("ls [test]")
    ui.render_execution_result(cmd, "output", "", 0)
    ui.render_refusal(cmd, "refused")
