import pytest
from unittest.mock import patch, MagicMock
from ternexar.installer_profiles import profile_registry, ProfileStatus
from ternexar.router import Router, Intent

@pytest.fixture
def router():
    return Router()

def test_python_alias_normalization():
    p1 = profile_registry.get_profile("python")
    p2 = profile_registry.get_profile("python 3")
    p3 = profile_registry.get_profile("python3")
    assert p1.id == "python3"
    assert p2.id == "python3"
    assert p3.id == "python3"

def test_node_alias_normalization():
    p1 = profile_registry.get_profile("node")
    p2 = profile_registry.get_profile("nodejs")
    p3 = profile_registry.get_profile("npm")
    assert p1.id == "nodejs"
    assert p2.id == "nodejs"
    assert p3.id == "nodejs"

def test_codex_needs_verification():
    p = profile_registry.get_profile("codex")
    assert p.status == ProfileStatus.NEEDS_VERIFICATION

def test_claude_code_needs_verification():
    p = profile_registry.get_profile("claude code")
    assert p.status == ProfileStatus.NEEDS_VERIFICATION

def test_docker_needs_verification():
    p = profile_registry.get_profile("docker")
    assert p.status == ProfileStatus.NEEDS_VERIFICATION

def test_unknown_tool_behavior():
    p = profile_registry.get_profile("unknown-gadget-123")
    assert p is None

@patch("platform.system", return_value="Linux")
@patch("platform.freedesktop_os_release", return_value={"ID": "ubuntu", "ID_LIKE": "debian"})
def test_os_detection_linux_apt(mock_release, mock_system):
    os_key = profile_registry.detect_os_key()
    assert os_key == "linux-apt"

@patch("platform.system", return_value="Darwin")
def test_os_detection_macos(mock_system):
    os_key = profile_registry.detect_os_key()
    assert os_key == "macos"

def test_router_install_intent(router):
    assert router.classify_intent("install python 3") == Intent.INSTALL_REQUEST
    assert router.classify_intent("install nodejs") == Intent.INSTALL_REQUEST
    assert router.classify_intent("install claude code") == Intent.INSTALL_REQUEST

def test_router_extract_tool_name(router):
    assert router.extract_tool_name("install python 3") == "python 3"
    assert router.extract_tool_name("please install nodejs for me") == "nodejs"
    assert router.extract_tool_name("install claude code") == "claude code"

def test_no_unsafe_execution_imports():
    # Check that installer_profiles.py doesn't import subprocess or use restricted system APIs
    with open("src/ternexar/installer_profiles.py", "r") as f:
        content = f.read()
        assert "import subprocess" not in content
        assert "from subprocess import" not in content
        
        # Build restricted pattern dynamically to keep grep clean
        restricted_api = "os" + "." + "system"
        assert restricted_api not in content

def test_installer_commands_pass_through_risk():
    from ternexar.risk import risk_engine, RiskLevel
    # Verify that the commands in our profiles are indeed classified as HIGH
    p = profile_registry.get_profile("python3")
    cmds = p.platforms["linux-apt"].commands
    for cmd in cmds:
        analysis = risk_engine.analyze(cmd)
        if "sudo" in cmd:
            assert analysis.level == RiskLevel.HIGH
