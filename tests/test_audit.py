import json
import os
from concurrent.futures import ThreadPoolExecutor
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
    command_secret = "super-secret-token"
    notes_secret = "correct-horse-battery-staple"

    manager.log_event(
        command=f"deploy --token={command_secret}",
        risk_level="HIGH",
        gate_decision="HOLD",
        policy="REQUIRE_CONFIRMATION",
        confirmation_mode="STANDARD",
        action_type="EXECUTION_START",
        result="PENDING",
        notes=f"password={notes_secret}",
    )

    record = manager.get_records()[0]
    assert command_secret not in record["command"]
    assert notes_secret not in record["notes"]
    assert "[REDACTED_SENSITIVE_DATA]" in record["command"]
    assert "[REDACTED_SENSITIVE_DATA]" in record["notes"]


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


def test_audit_skips_malformed_jsonl_and_preserves_valid_records(tmp_path):
    manager = make_manager(tmp_path)
    valid_first = {"command": "first"}
    valid_last = {"command": "last"}
    manager.log_file.write_text(
        f"{json.dumps(valid_first)}\nnot-json\n{json.dumps(valid_last)}\n"
    )

    assert manager.get_records() == [valid_first, valid_last]


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


def test_audit_returns_false_on_controlled_write_failure(tmp_path, monkeypatch):
    manager = make_manager(tmp_path)

    def fail_open(*args, **kwargs):
        raise OSError("disk unavailable")

    monkeypatch.setattr("builtins.open", fail_open)

    assert manager.log_event("ls", "LOW", "PASS", "ALLOW", "MIN", "START", "OK") is False


def test_audit_clear_raises_when_its_audit_record_cannot_be_written(tmp_path, monkeypatch):
    manager = make_manager(tmp_path)

    def fail_open(*args, **kwargs):
        raise OSError("write unavailable")

    monkeypatch.setattr("builtins.open", fail_open)

    try:
        manager.clear_logs()
    except RuntimeError as error:
        assert "Failed to clear audit log" in str(error)
    else:
        raise AssertionError("Expected clear_logs to fail when audit logging fails")


def test_audit_preserves_repeated_and_concurrent_appends(tmp_path):
    manager = make_manager(tmp_path)

    def append(index):
        return manager.log_event(
            f"command-{index}", "LOW", "PASS", "ALLOW", "MIN", "START", "OK"
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(append, range(40)))

    assert all(results)
    records = manager.get_records(limit=40)
    assert len(records) == 40
    assert {record["command"] for record in records} == {f"command-{index}" for index in range(40)}
