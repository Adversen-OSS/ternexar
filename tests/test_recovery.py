import pytest
from pathlib import Path
from ternexar.recovery_profiles import RecoveryDomain, classify_error
from ternexar.recovery import recovery_engine, RecoveryReport

def test_operator_routing_recovery(mocker):
    from ternexar.router import router, Intent
    intent = router.classify_intent("recover this error")
    assert intent == Intent.RECOVER

def test_classification_apt_signed_by():
    error = "E: Conflicting values set for option Signed-By regarding source https://repo.protonvpn.com/debian stable"
    profile = classify_error(error)
    assert profile.id == "APT_SIGNED_BY_CONFLICT"
    assert profile.domain == RecoveryDomain.APT

def test_classification_apt_malformed():
    error = "Malformed line 1 in source list /etc/apt/sources.list.d/test.list (type)"
    profile = classify_error(error)
    assert profile.id == "APT_MALFORMED_ENTRY"

def test_classification_python_missing_module():
    error = "ModuleNotFoundError: No module named 'requests'"
    profile = classify_error(error)
    assert profile.id == "PYTHON_MODULE_NOT_FOUND"

def test_classification_npm_missing_package_json():
    error = "npm ERR! enoent Could not read package.json"
    profile = classify_error(error)
    assert profile.id == "NPM_MISSING_PACKAGE_JSON"

def test_classification_npm_dependency_conflict():
    error = "npm ERR! ERESOLVE could not resolve dependency"
    profile = classify_error(error)
    assert profile.id == "NPM_DEPENDENCY_CONFLICT"

def test_classification_git_not_repo():
    error = "fatal: not a git repository (or any of the parent directories): .git"
    profile = classify_error(error)
    assert profile.id == "GIT_NOT_REPOSITORY"

def test_classification_git_merge_conflict():
    error = "CONFLICT (content): Merge conflict in file.txt"
    profile = classify_error(error)
    assert profile.id == "GIT_MERGE_CONFLICT"

def test_classification_permission_denied():
    error = "Permission denied: '/root/secret.txt'"
    profile = classify_error(error)
    assert profile.id == "PERMISSION_DENIED"

def test_classification_port_in_use():
    error = "Error: listen EADDRINUSE: address already in use :::8080"
    profile = classify_error(error)
    assert profile.id == "PORT_IN_USE"

def test_classification_file_not_found():
    error = "FileNotFoundError: [Errno 2] No such file or directory: 'missing.txt'"
    profile = classify_error(error)
    assert profile.id == "FILE_NOT_FOUND"

def test_classification_unknown():
    error = "Some random weird error that doesn't match anything"
    profile = classify_error(error)
    assert profile.id == "UNKNOWN_FAILURE"

def test_destructive_request_blocked():
    error = "rm -rf /"
    report = recovery_engine.recover(error)
    assert report.profile.id == "BLOCKED_DESTRUCTIVE_REQUEST"
    assert report.status == "BLOCKED"

def test_recover_file_blocks_env(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SECRET=123")
    report = recovery_engine.recover_file(str(env_file))
    assert report.status == "REFUSED"
    assert "Hidden path blocked" in report.profile.explanation

def test_recover_file_blocks_secret_name(tmp_path):
    secret_file = tmp_path / "my_password.txt"
    secret_file.write_text("123456")
    report = recovery_engine.recover_file(str(secret_file))
    assert report.status == "REFUSED"
    assert "Sensitive filename blocked" in report.profile.explanation

def test_recover_file_blocks_binary(tmp_path):
    bin_file = tmp_path / "test.bin"
    with open(bin_file, "wb") as f:
        f.write(b"\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00")
    report = recovery_engine.recover_file(str(bin_file))
    assert report.status == "REFUSED"
    # Null byte detection
    assert "Binary file blocked" in report.profile.explanation

def test_recover_file_blocks_large_file(tmp_path):
    large_file = tmp_path / "large.txt"
    with open(large_file, "w") as f:
        f.write("A" * (100 * 1024 + 1))
    report = recovery_engine.recover_file(str(large_file))
    assert report.status == "REFUSED"
    assert "File too large" in report.profile.explanation

def test_recover_file_blocks_system_path():
    report = recovery_engine.recover_file("/etc/apt/sources.list")
    assert report.status == "REFUSED"
    assert "System path blocked" in report.profile.explanation

def test_redaction():
    error = "Error with token abcdef1234567890abcdef1234567890abcdef1234567890"
    report = recovery_engine.recover(error)
    assert "[REDACTED_SENSITIVE_DATA]" in report.error_text
    assert "abcdef1234567890" not in report.error_text

def test_composer_routes_to_handle_recover(mocker):
    """Verify operator routes recovery intent to handle_recover correctly."""
    mock_handle = mocker.patch("ternexar.composer.handle_recover")
    mocker.patch("ternexar.ui.ui.render_operator_routing_feedback")
    from ternexar.composer import route_operator_input
    route_operator_input("recover this error")
    mock_handle.assert_called_once_with("recover this error")
