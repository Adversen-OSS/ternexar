import pytest
from pathlib import Path
from ternexar.analyze import Analyzer
from ternexar.patcher import PatchResult

@pytest.mark.parametrize("task,expected_module", [
    ("ModuleNotFoundError: No module named requests", "requests"),
    ("ModuleNotFoundError: No module named 'requests'", "requests"),
    ("ImportError: No module named requests", "requests"),
    ("ImportError: No module named 'requests'", "requests"),
    ("ImportError: No module named \"flask\"", "flask"),
])
def test_analyzer_detect_missing_module_variants(task, expected_module):
    analyzer = Analyzer()
    result = analyzer.analyze(task)
    
    assert result.detected_issue is not None
    assert expected_module in result.detected_issue
    assert result.proposed_file.name == "requirements.txt"
    assert expected_module in result.proposed_content
    assert result.safety_verdict == "SAFE"

def test_analyzer_vague_import_error():
    analyzer = Analyzer()
    task = "fix import error in app.py"
    result = analyzer.analyze(task)
    
    # Should not detect a module and thus not propose a requirements.txt patch
    assert result.detected_issue == "No deterministic fix found for this issue."
    assert result.safety_verdict == "REFUSED"
    assert result.proposed_content is None

def test_analyzer_blocked_action():
    analyzer = Analyzer()
    task = "delete all files in src"
    result = analyzer.analyze(task)
    
    assert result.safety_verdict == "BLOCKED"
    assert "deletion" in result.reason

def test_analyzer_unsupported_fix():
    analyzer = Analyzer()
    task = "Optimize my database queries"
    result = analyzer.analyze(task)
    
    assert result.safety_verdict == "REFUSED"
    assert "only supports simple Python dependency fixes" in result.reason

def test_analyzer_generate_requirements_patch(tmp_path):
    analyzer = Analyzer(project_root=tmp_path)
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("flask==2.0.1\n")
    
    new_content = analyzer._generate_requirements_patch("requests")
    assert "flask==2.0.1" in new_content
    assert "requests" in new_content
    assert new_content.endswith("\n")

def test_analyzer_generate_requirements_patch_new_file(tmp_path):
    analyzer = Analyzer(project_root=tmp_path)
    # requirements.txt does not exist
    
    new_content = analyzer._generate_requirements_patch("requests")
    assert new_content == "requests\n"


class _RecordingAudit:
    def __init__(self):
        self.events = []

    def log_event(self, **kwargs):
        self.events.append(kwargs)


class _StubPatcher:
    def __init__(self, patch_result):
        self.patch_result = patch_result

    def generate_diff(self, file_path, new_content):
        return "--- a/requirements.txt\n+++ b/requirements.txt\n+requests"

    def apply_patch(self, file_path, new_content):
        return self.patch_result


def _run_analyze_with(monkeypatch, patch_result):
    """Drive handle_analyze to the confirmed-patch branch with a stub patcher."""
    import typer

    from ternexar import analyze as analyze_module

    audit = _RecordingAudit()
    monkeypatch.setattr(analyze_module, "audit_manager", audit)
    monkeypatch.setattr(analyze_module, "patcher", _StubPatcher(patch_result))
    monkeypatch.setattr(typer, "confirm", lambda *args, **kwargs: True)

    analyze_module.handle_analyze("ModuleNotFoundError: No module named requests")

    return [
        event
        for event in audit.events
        if str(event.get("action_type", "")).startswith("PATCH_")
    ]


def test_clean_patch_is_audited_as_an_ordinary_success(monkeypatch):
    result = PatchResult(success=True, file_path=Path("requirements.txt"))

    events = _run_analyze_with(monkeypatch, result)

    assert len(events) == 1
    assert events[0]["action_type"] == "PATCH_APPLIED"
    assert events[0]["result"] == "SUCCESS"


def test_committed_patch_with_warning_is_not_audited_as_ordinary_success(monkeypatch):
    """A post-commit warning must be distinguishable in the audit trail."""
    result = PatchResult(
        success=True,
        file_path=Path("requirements.txt"),
        warning="Replacement committed, but post-commit cleanup or durability "
        "sync failed: directory fsync failure",
    )

    events = _run_analyze_with(monkeypatch, result)

    assert len(events) == 1
    assert events[0]["action_type"] != "PATCH_APPLIED"
    assert events[0]["result"] != "SUCCESS"
    assert events[0]["action_type"] == "PATCH_APPLIED_WITH_WARNING"
    assert events[0]["result"] == "SUCCESS_WITH_WARNING"
    assert "durability" in events[0]["notes"]


def test_failed_patch_is_audited_as_failure(monkeypatch):
    result = PatchResult(success=False, error="Target symlink is refused.")

    events = _run_analyze_with(monkeypatch, result)

    assert len(events) == 1
    assert events[0]["action_type"] == "PATCH_FAILED"
    assert events[0]["result"] == "FAILED"
