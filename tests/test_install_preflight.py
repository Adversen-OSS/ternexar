import pytest
from unittest.mock import MagicMock, patch
from ternexar.install_preflight import handle_install_preflight, PreflightVerdict
from ternexar.version_check import CheckStatus
from ternexar.installer_profiles import ProfileStatus

@patch("ternexar.install_preflight.get_version_check_data")
@patch("ternexar.install_preflight.profile_registry")
@patch("ternexar.install_preflight.ui")
@patch("ternexar.install_preflight.audit_manager")
def test_preflight_already_installed(mock_audit, mock_ui, mock_registry, mock_version):
    # Setup: Tool is already installed
    mock_version.return_value = {
        "status": CheckStatus.INSTALLED,
        "normalized_tool": "Python 3",
        "version_output": "Python 3.10.12",
        "notes": None
    }
    mock_registry.get_profile.return_value = MagicMock(status=ProfileStatus.AVAILABLE)
    mock_registry.detect_os_key.return_value = "linux-apt"
    
    handle_install_preflight("python3")
    
    # Verify verdict
    args, _ = mock_ui.render_install_preflight_report.call_args
    assert args[0]["verdict"] == PreflightVerdict.ALREADY_INSTALLED
    assert args[0]["version_status"] == CheckStatus.INSTALLED

@patch("ternexar.install_preflight.get_version_check_data")
@patch("ternexar.install_preflight.profile_registry")
@patch("ternexar.install_preflight.ui")
def test_preflight_ready_for_execution(mock_ui, mock_registry, mock_version):
    # Setup: Tool not installed, profile available
    mock_version.return_value = {
        "status": CheckStatus.NOT_INSTALLED,
        "normalized_tool": "Python 3",
        "version_output": None,
        "notes": "Not found"
    }
    
    mock_profile = MagicMock()
    mock_profile.status = ProfileStatus.AVAILABLE
    mock_platform = MagicMock()
    mock_platform.commands = ["sudo apt update", "sudo apt install python3"]
    mock_profile.platforms = {"linux-apt": mock_platform}
    
    mock_registry.get_profile.return_value = mock_profile
    mock_registry.detect_os_key.return_value = "linux-apt"
    
    handle_install_preflight("python3")
    
    # Verify verdict
    args, _ = mock_ui.render_install_preflight_report.call_args
    assert args[0]["verdict"] == PreflightVerdict.READY_FOR_FUTURE_CONFIRMED_EXECUTION

@patch("ternexar.install_preflight.get_version_check_data")
@patch("ternexar.install_preflight.profile_registry")
@patch("ternexar.install_preflight.ui")
def test_preflight_needs_verification(mock_ui, mock_registry, mock_version):
    # Setup: Profile needs verification
    mock_version.return_value = {
        "status": CheckStatus.NOT_INSTALLED,
        "normalized_tool": "OpenAI Codex",
        "version_output": None,
        "notes": None
    }
    mock_registry.get_profile.return_value = MagicMock(status=ProfileStatus.NEEDS_VERIFICATION)
    
    handle_install_preflight("codex")
    
    # Verify verdict
    args, _ = mock_ui.render_install_preflight_report.call_args
    assert args[0]["verdict"] == PreflightVerdict.NOT_READY_NEEDS_VERIFICATION

@patch("ternexar.install_preflight.get_version_check_data")
@patch("ternexar.install_preflight.profile_registry")
@patch("ternexar.install_preflight.ui")
def test_preflight_unknown_tool(mock_ui, mock_registry, mock_version):
    # Setup: Unknown tool
    mock_version.return_value = {
        "status": CheckStatus.UNKNOWN_TOOL,
        "normalized_tool": "Unknown",
        "version_output": None,
        "notes": None
    }
    mock_registry.get_profile.return_value = None
    
    handle_install_preflight("mystery-tool")
    
    # Verify verdict
    args, _ = mock_ui.render_install_preflight_report.call_args
    assert args[0]["verdict"] == PreflightVerdict.NOT_READY_UNKNOWN_TOOL

@patch("ternexar.install_preflight.get_version_check_data")
@patch("ternexar.install_preflight.profile_registry")
@patch("ternexar.install_preflight.gate_engine")
@patch("ternexar.install_preflight.ui")
def test_preflight_refused_blocked_command(mock_ui, mock_gate, mock_registry, mock_version):
    # Setup: One command is BLOCKED
    mock_version.return_value = {
        "status": CheckStatus.NOT_INSTALLED,
        "normalized_tool": "Python 3",
        "version_output": None,
        "notes": None
    }
    
    mock_profile = MagicMock()
    mock_profile.status = ProfileStatus.AVAILABLE
    mock_platform = MagicMock()
    mock_platform.commands = ["sudo apt update", "rm -rf /"] # BLOCKED
    mock_profile.platforms = {"linux-apt": mock_platform}
    
    mock_registry.get_profile.return_value = mock_profile
    mock_registry.detect_os_key.return_value = "linux-apt"
    
    # Mock gate to block the second command
    from ternexar.gate import GateResult, GateStatus
    from ternexar.risk import RiskLevel
    from ternexar.gate import PolicyDecision
    
    def mock_evaluate(cmd):
        if "rm -rf /" in cmd:
            return GateResult(cmd, RiskLevel.BLOCKED, [], PolicyDecision.DENY, GateStatus.BLOCK, "Blocked", "")
        return GateResult(cmd, RiskLevel.LOW, [], PolicyDecision.ALLOW_PREVIEW, GateStatus.PASS, "Pass", "")
    
    mock_gate.evaluate.side_effect = mock_evaluate
    
    handle_install_preflight("python3")
    
    # Verify verdict
    args, _ = mock_ui.render_install_preflight_report.call_args
    assert args[0]["verdict"] == PreflightVerdict.REFUSED
    assert "BLOCKED" in args[0]["notes"]
