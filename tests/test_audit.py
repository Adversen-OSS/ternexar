import json
import os
from concurrent.futures import ThreadPoolExecutor
import pytest
import ternexar.audit as audit_module
from ternexar.audit import AuditManager


def make_manager(tmp_path):
    manager = AuditManager()
    manager.base_dir = tmp_path / "audit"
    manager.log_file = manager.base_dir / "audit.jsonl"
    manager._ensure_dir()
    return manager

def test_audit_logging(tmp_path):
    # Setup AuditManager with a temp path
    manager = make_manager(tmp_path)

    # Log an event
    manager.log_event(
        command="ls",
        risk_level="LOW",
        gate_decision="PASS",
        policy="ALLOW_PREVIEW",
        confirmation_mode="MINIMAL",
        action_type="EXECUTION_START",
        result="STARTED",
        notes="Test note"
    )

    # Verify record
    records = manager.get_records()
    assert len(records) == 1
    assert records[0]["command"] == "ls"
    assert records[0]["notes"] == "Test note"

def test_audit_clear(tmp_path):
    manager = make_manager(tmp_path)

    manager.log_event("ls", "LOW", "PASS", "ALLOW", "MIN", "START", "OK")
    assert len(manager.get_records()) == 1

    manager.clear_logs()
    records = manager.get_records()
    assert len(records) == 1
    assert records[0]["action_type"] == "AUDIT_LOG_CLEARED"


def test_audit_redacts_secrets_from_command_and_notes(tmp_path):
    manager = make_manager(tmp_path)
    secrets = [
        ("deploy --password secret-value", "secret-value"),
        ("deploy --token secret-value", "secret-value"),
        ("deploy --api-key secret-value", "secret-value"),
        ("Authorization: Bearer secret-value", "secret-value"),
        ("key=secret-value", "secret-value"),
        ("key:secret-value", "secret-value"),
        ("use ghp_abcdefghijklmnopqrstuvwxyz1234567890", "ghp_abcdefghijklmnopqrstuvwxyz1234567890"),
        ("use sk-abcdefghijklmnopqrstuvwxyz1234567890", "sk-abcdefghijklmnopqrstuvwxyz1234567890"),
        ("use AKIAABCDEFGHIJKLMNOP", "AKIAABCDEFGHIJKLMNOP"),
    ]

    for command, secret in secrets:
        manager.log_event(
            command=command,
            risk_level="HIGH",
            gate_decision="HOLD",
            policy="REQUIRE_CONFIRMATION",
            confirmation_mode="STANDARD",
            action_type="EXECUTION_START",
            result="PENDING",
            notes=f"password={secret}",
        )

    for record, (_, secret) in zip(manager.get_records(limit=len(secrets)), secrets):
        assert secret not in record["command"]
        assert secret not in record["notes"]
        assert "[REDACTED]" in record["command"]
        assert "[REDACTED]" in record["notes"]


def test_audit_enforces_directory_and_file_permissions(tmp_path):
    manager = AuditManager()
    manager.base_dir = tmp_path / "audit"
    manager.log_file = manager.base_dir / "audit.jsonl"
    manager.base_dir.mkdir()
    os.chmod(manager.base_dir, 0o755)
    manager.log_file.write_text("")
    os.chmod(manager.log_file, 0o644)

    manager._ensure_dir()
    manager.log_event("ls", "LOW", "PASS", "ALLOW", "MIN", "START", "OK")

    assert os.stat(manager.base_dir).st_mode & 0o777 == 0o700
    assert os.stat(manager.log_file).st_mode & 0o777 == 0o600


def test_audit_creates_new_files_with_owner_only_permissions(tmp_path):
    manager = make_manager(tmp_path)

    manager.log_event("ls", "LOW", "PASS", "ALLOW", "MIN", "START", "OK")

    assert os.stat(manager.log_file).st_mode & 0o777 == 0o600


def test_audit_corrects_existing_file_permissions_before_writing(tmp_path, monkeypatch):
    manager = make_manager(tmp_path)
    manager.log_file.write_text("")
    os.chmod(manager.log_file, 0o644)
    observed_modes = []
    original_fdopen = os.fdopen

    def inspect_fdopen(fd, *args, **kwargs):
        observed_modes.append(os.stat(manager.log_file).st_mode & 0o777)
        return original_fdopen(fd, *args, **kwargs)

    monkeypatch.setattr(audit_module.os, "fdopen", inspect_fdopen)

    manager.log_event("ls", "LOW", "PASS", "ALLOW", "MIN", "START", "OK")

    assert observed_modes == [0o600]


def test_audit_skips_malformed_jsonl_and_preserves_valid_records(tmp_path):
    manager = make_manager(tmp_path)
    valid_first = {"command": "first"}
    valid_last = {"command": "last"}
    manager.log_file.write_text(
        f"{json.dumps(valid_first)}\nnot-json\n{json.dumps(valid_last)}\n"
    )

    assert manager.get_records() == [valid_first, valid_last]


def test_audit_skips_blank_jsonl_lines_between_valid_records(tmp_path):
    manager = make_manager(tmp_path)
    valid_first = {"command": "first"}
    valid_last = {"command": "last"}
    manager.log_file.write_text(f"{json.dumps(valid_first)}\n\n   \n{json.dumps(valid_last)}\n")

    assert manager.get_records() == [valid_first, valid_last]


def test_audit_limits_apply_only_to_valid_dictionary_records(tmp_path):
    manager = make_manager(tmp_path)
    valid_first = {"command": "first"}
    valid_last = {"command": "last"}
    manager.log_file.write_text(
        f"{json.dumps(valid_first)}\n[\"not a record\"]\nnot-json\n{json.dumps(valid_last)}\n"
    )

    assert manager.get_records(limit=1) == [valid_last]
    assert manager.get_records(limit=0) == []
    with pytest.raises(ValueError):
        manager.get_records(limit=-1)


def test_audit_returns_empty_for_missing_or_unreadable_logs(tmp_path, monkeypatch):
    manager = make_manager(tmp_path)
    assert manager.get_records() == []

    manager.log_file.write_text("\n")

    def fail_open(*args, **kwargs):
        raise OSError("read unavailable")

    monkeypatch.setattr("builtins.open", fail_open)
    assert manager.get_records() == []


def test_audit_jsonl_serialization_prevents_newline_injection(tmp_path):
    manager = make_manager(tmp_path)
    injected_command = 'safe\n{"action_type":"FORGED"}'

    manager.log_event(
        injected_command, "LOW", "PASS", "ALLOW", "MIN", "START", "OK", "note\nforged"
    )

    raw_lines = manager.log_file.read_text().splitlines()
    assert len(raw_lines) == 1
    assert manager.get_records()[0]["command"] == injected_command


def test_audit_does_not_redact_benign_similar_text(tmp_path):
    manager = make_manager(tmp_path)
    command = "monkey=value"

    manager.log_event(command, "LOW", "PASS", "ALLOW", "MIN", "START", "OK")

    assert manager.get_records()[0]["command"] == command


def test_audit_write_failures_remain_non_fatal_and_preserve_public_api(tmp_path, monkeypatch):
    manager = make_manager(tmp_path)
    called = []

    def fail_fdopen(*args, **kwargs):
        called.append(True)
        raise OSError("disk unavailable")

    monkeypatch.setattr(audit_module.os, "fdopen", fail_fdopen)

    assert manager.log_event("ls", "LOW", "PASS", "ALLOW", "MIN", "START", "OK") is None
    assert called == [True]


def test_audit_clear_failure_preserves_existing_history(tmp_path, monkeypatch):
    manager = make_manager(tmp_path)
    manager.log_event("ls", "LOW", "PASS", "ALLOW", "MIN", "START", "OK")
    original_log = manager.log_file.read_text()

    def fail_replace(*args, **kwargs):
        raise OSError("replace unavailable")

    monkeypatch.setattr(audit_module.os, "replace", fail_replace)

    with pytest.raises(RuntimeError):
        manager.clear_logs()

    assert manager.log_file.read_text() == original_log


def test_audit_preserves_repeated_and_concurrent_appends(tmp_path):
    manager = make_manager(tmp_path)

    def append(index):
        return manager.log_event(
            f"command-{index}", "LOW", "PASS", "ALLOW", "MIN", "START", "OK"
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(append, range(40)))

    assert all(result is None for result in results)
    records = manager.get_records(limit=40)
    assert len(records) == 40
    assert {record["command"] for record in records} == {f"command-{index}" for index in range(40)}
