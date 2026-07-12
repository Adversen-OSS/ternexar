import pytest
from pathlib import Path
from ternexar.patcher import Patcher

def test_patcher_validate_file_safe(tmp_path):
    patcher = Patcher(project_root=tmp_path)
    safe_file = tmp_path / "app.py"
    safe_file.write_text("print('hello')")
    
    valid, error = patcher.validate_file(safe_file)
    assert valid is True
    assert error is None

def test_patcher_validate_file_outside_root(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    patcher = Patcher(project_root=root)
    
    outside_file = tmp_path / "outside.py"
    outside_file.write_text("print('outside')")
    
    valid, error = patcher.validate_file(outside_file)
    assert valid is False
    assert "outside the project root" in error

def test_patcher_validate_file_blocked_extension(tmp_path):
    patcher = Patcher(project_root=tmp_path)
    blocked_file = tmp_path / "image.png"
    blocked_file.write_bytes(b"\x89PNG\r\n\x1a\n")
    
    valid, error = patcher.validate_file(blocked_file)
    assert valid is False
    assert "Unsupported file extension" in error

def test_patcher_validate_file_hidden(tmp_path):
    patcher = Patcher(project_root=tmp_path)
    hidden_file = tmp_path / ".secret"
    hidden_file.write_text("secret")
    
    valid, error = patcher.validate_file(hidden_file)
    assert valid is False
    assert "hidden path" in error

def test_patcher_generate_diff(tmp_path):
    patcher = Patcher(project_root=tmp_path)
    file = tmp_path / "req.txt"
    file.write_text("flask\n")
    
    diff = patcher.generate_diff(file, "flask\nrequests\n")
    assert "+requests" in diff
    assert "-flask" not in diff

def test_patcher_apply_patch_with_backup(tmp_path):
    patcher = Patcher(project_root=tmp_path)
    file = tmp_path / "app.py"
    file.write_text("old content")
    
    result = patcher.apply_patch(file, "new content")
    
    assert result.success is True
    assert file.read_text() == "new content"
    assert result.backup_path.exists()
    assert result.backup_path.read_text() == "old content"
    assert ".ternexar/backups" in str(result.backup_path)

def test_patcher_apply_patch_no_change_creates_no_backup(tmp_path):
    patcher = Patcher(project_root=tmp_path)
    file = tmp_path / "app.py"
    original_content = "same content"
    file.write_text(original_content)

    result = patcher.apply_patch(file, original_content)

    assert result.success is True
    assert result.diff is None
    assert result.backup_path is None
    assert result.error is None
    assert file.read_text() == original_content
    assert not patcher.backup_dir.exists()

