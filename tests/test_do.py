import pytest
from unittest.mock import patch, MagicMock
from ternexar.do import handle_do, STRICT_ALLOWLIST

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
    
    # Verify subprocess.run was called with shell=False
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0] == ["ls", "-la"]
    assert kwargs["shell"] is False
    
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


def test_do_timeout(mock_run, mock_ui, mock_audit):
    import subprocess
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="ls", timeout=10)

    handle_do("ls")

    mock_ui.render_execution_result.assert_called_once()
    args = mock_ui.render_execution_result.call_args[0]
    assert "timed out" in args[2]  # stderr
    assert mock_run.call_args.kwargs["timeout"] == 10


def test_original_security_bypass_prevented(mock_run, mock_ui, mock_audit, monkeypatch):
    from ternexar.risk import risk_engine, RiskLevel

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


def test_literal_rich_markup_command_rendering(mock_run, monkeypatch):
    from ternexar.ui import ui

    monkeypatch.setattr("ternexar.do.is_interactive_terminal", lambda: True)
    monkeypatch.setattr("ternexar.do.prompt_medium_confirmation", lambda cmd, reason: True)

    # Command containing Rich markup syntax e.g. brackets
    cmd = 'pip install "requests[security]" "[bold red]test[/]"'
    handle_do(cmd)

    mock_run.assert_called_once()
    args, _ = mock_run.call_args
    assert args[0] == ["pip", "install", "requests[security]", "[bold red]test[/]"]

    # Verify ui methods render literal text without throwing markup exception
    ui.render_medium_confirmation_header(cmd, "Package Installation")
    ui.render_execution_declined(cmd, "User declined")
    ui.render_minimal_confirmation("ls [test]")
