import os
import shutil
import errno
import importlib
import stat

import pytest
from pathlib import Path
from ternexar.patcher import Patcher


patcher_module = importlib.import_module("ternexar.patcher")


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


def test_patcher_refuses_direct_target_symlink_and_preserves_outside_file(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    outside_file = tmp_path / "outside.py"
    outside_file.write_text("outside content")
    target = project / "app.py"
    target.symlink_to(outside_file)

    result = Patcher(project_root=project).apply_patch(target, "new content")

    assert result.success is False
    assert "symlink" in (result.error or "").lower()
    assert target.is_symlink()
    assert outside_file.read_text() == "outside content"


def test_patcher_refuses_symlinked_parent_directory(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_file = outside_dir / "app.py"
    outside_file.write_text("outside content")
    linked_parent = project / "linked"
    linked_parent.symlink_to(outside_dir, target_is_directory=True)

    result = Patcher(project_root=project).apply_patch(
        linked_parent / "app.py", "new content"
    )

    assert result.success is False
    assert "symlink" in (result.error or "").lower()
    assert outside_file.read_text() == "outside content"


def test_patcher_refuses_target_swapped_to_symlink_before_commit(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    target = project / "app.py"
    target.write_text("original")
    outside_file = tmp_path / "outside.py"
    outside_file.write_text("outside content")
    patcher = Patcher(project_root=project)
    original_verify = patcher._verify_target_unchanged

    def swap_to_symlink(*args, **kwargs):
        target.unlink()
        target.symlink_to(outside_file)
        return original_verify(*args, **kwargs)

    monkeypatch.setattr(patcher, "_verify_target_unchanged", swap_to_symlink)

    result = patcher.apply_patch(target, "new content")

    assert result.success is False
    assert target.is_symlink()
    assert outside_file.read_text() == "outside content"
    assert not list(project.glob(".ternexar-patch-*.tmp"))


def test_patcher_refuses_replaced_target_inode_before_commit(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    target = project / "app.py"
    target.write_text("original")
    replacement = project / "replacement.py"
    replacement.write_text("replacement")
    patcher = Patcher(project_root=project)
    original_verify = patcher._verify_target_unchanged

    def replace_target(*args, **kwargs):
        os.replace(replacement, target)
        return original_verify(*args, **kwargs)

    monkeypatch.setattr(patcher, "_verify_target_unchanged", replace_target)

    result = patcher.apply_patch(target, "new content")

    assert result.success is False
    assert target.read_text() == "replacement"
    assert not list(project.glob(".ternexar-patch-*.tmp"))


def test_patcher_ignores_precreated_predictable_temp_symlink(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    target = project / "app.py"
    target.write_text("original")
    outside_file = tmp_path / "outside.py"
    outside_file.write_text("outside content")
    predictable_temp = target.with_suffix(".py.tmp")
    predictable_temp.symlink_to(outside_file)

    result = Patcher(project_root=project).apply_patch(target, "new content")

    assert result.success is True
    assert target.read_text() == "new content"
    assert predictable_temp.is_symlink()
    assert outside_file.read_text() == "outside content"
    assert not list(project.glob(".ternexar-patch-*.tmp"))


def test_patcher_preserves_existing_target_permissions(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    target = project / "app.py"
    target.write_text("original")
    target.chmod(0o640)

    result = Patcher(project_root=project).apply_patch(target, "new content")

    assert result.success is True
    assert target.stat().st_mode & 0o777 == 0o640


def test_patcher_creates_new_files_with_owner_only_permissions(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    target = project / "requirements.txt"

    result = Patcher(project_root=project).apply_patch(target, "requests\n")

    assert result.success is True
    assert target.read_text() == "requests\n"
    assert target.stat().st_mode & 0o777 == 0o600


def test_patcher_fails_closed_when_secure_primitives_are_unavailable(
    tmp_path, monkeypatch
):
    target = tmp_path / "app.py"
    target.write_text("original")
    patcher = Patcher(project_root=tmp_path)
    monkeypatch.setattr(patcher_module.os, "supports_dir_fd", set())

    valid, error = patcher.validate_file(target)
    result = patcher.apply_patch(target, "new content")

    assert valid is False
    assert "descriptor-relative" in (error or "")
    assert result.success is False
    assert target.read_text() == "original"


def test_patcher_refuses_symlinked_or_non_directory_project_root(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    linked_root = tmp_path / "linked-root"
    linked_root.symlink_to(outside, target_is_directory=True)

    linked_result = Patcher(project_root=linked_root).apply_patch(
        linked_root / "app.py", "new content"
    )
    file_result = Patcher(project_root=tmp_path / "not-a-directory").apply_patch(
        tmp_path / "not-a-directory" / "app.py", "new content"
    )

    assert linked_result.success is False
    assert "root symlink" in (linked_result.error or "").lower()
    assert file_result.success is False
    assert "project root" in (file_result.error or "").lower()


def test_patcher_refuses_invalid_sensitive_and_blocked_targets(tmp_path):
    patcher = Patcher(project_root=tmp_path)
    blocked_dir = tmp_path / "build"
    blocked_dir.mkdir()

    invalid, invalid_error = patcher.validate_file(
        tmp_path / "folder" / ".." / "app.py"
    )
    sensitive, sensitive_error = patcher.validate_file(tmp_path / "api_token.py")
    blocked, blocked_error = patcher.validate_file(blocked_dir / "app.py")

    assert invalid is False
    assert "invalid" in (invalid_error or "").lower()
    assert sensitive is False
    assert "sensitive" in (sensitive_error or "").lower()
    assert blocked is False
    assert "restricted" in (blocked_error or "").lower()


def test_patcher_refuses_non_directory_parent_and_non_regular_target(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "not-a-directory").write_text("x")
    directory_target = project / "directory.py"
    directory_target.mkdir()
    patcher = Patcher(project_root=project)

    parent_result = patcher.apply_patch(project / "not-a-directory" / "app.py", "new")
    target_result = patcher.apply_patch(directory_target, "new")

    assert parent_result.success is False
    assert "parent" in (parent_result.error or "").lower()
    assert target_result.success is False
    assert "regular file" in (target_result.error or "").lower()


def test_patcher_refuses_oversized_and_binary_target_files(tmp_path):
    patcher = Patcher(project_root=tmp_path)
    oversized = tmp_path / "large.py"
    oversized.write_bytes(b"x" * (patcher_module.MAX_FILE_SIZE + 1))
    binary = tmp_path / "binary.py"
    binary.write_bytes(b"\xff\xfe")

    oversized_result = patcher.apply_patch(oversized, "new")
    binary_result = patcher.apply_patch(binary, "new")

    assert oversized_result.success is False
    assert "too large" in (oversized_result.error or "").lower()
    assert binary_result.success is False
    assert "binary" in (binary_result.error or "").lower()


def test_generate_diff_returns_none_for_refused_target(tmp_path):
    target = tmp_path / "linked.py"
    outside = tmp_path / "outside.py"
    outside.write_text("outside")
    target.symlink_to(outside)

    assert Patcher(project_root=tmp_path).generate_diff(target, "new") is None


def test_backup_uses_verified_original_bytes_when_target_is_raced(
    tmp_path, monkeypatch
):
    project = tmp_path / "project"
    project.mkdir()
    target = project / "app.py"
    target.write_text("verified original")
    raced_replacement = project / "replacement.py"
    raced_replacement.write_text("raced replacement")
    patcher = Patcher(project_root=project)
    original_write_temp = patcher._write_temporary_file

    def race_after_backup(*args, **kwargs):
        os.replace(raced_replacement, target)
        return original_write_temp(*args, **kwargs)

    monkeypatch.setattr(patcher, "_write_temporary_file", race_after_backup)

    result = patcher.apply_patch(target, "new content")

    assert result.success is False
    backups = list(patcher.backup_dir.glob("*.tx.bak"))
    assert len(backups) == 1
    assert backups[0].read_text() == "verified original"
    assert target.read_text() == "raced replacement"


def test_existing_target_removal_and_new_target_appearance_fail_closed(
    tmp_path, monkeypatch
):
    project = tmp_path / "project"
    project.mkdir()
    existing = project / "app.py"
    existing.write_text("original")
    new_target = project / "requirements.txt"
    existing_patcher = Patcher(project_root=project)
    new_patcher = Patcher(project_root=project)
    verify_existing = existing_patcher._verify_target_unchanged
    verify_new = new_patcher._verify_target_unchanged

    def remove_existing(*args, **kwargs):
        existing.unlink()
        return verify_existing(*args, **kwargs)

    def create_new_target(*args, **kwargs):
        new_target.write_text("unexpected")
        return verify_new(*args, **kwargs)

    monkeypatch.setattr(existing_patcher, "_verify_target_unchanged", remove_existing)
    monkeypatch.setattr(new_patcher, "_verify_target_unchanged", create_new_target)

    removed_result = existing_patcher.apply_patch(existing, "new")
    appeared_result = new_patcher.apply_patch(new_target, "new")

    assert removed_result.success is False
    assert not existing.exists()
    assert appeared_result.success is False
    assert new_target.read_text() == "unexpected"


def test_temporary_file_failures_clean_up_and_close_descriptors(tmp_path, monkeypatch):
    patcher = Patcher(project_root=tmp_path)
    parent_fd, _ = patcher._open_parent_directory(("app.py",))
    original_fsync = patcher_module.os.fsync
    closed_descriptors = []
    original_close = patcher_module.os.close

    def fail_fsync(descriptor):
        raise OSError("injected fsync failure")

    def record_close(descriptor):
        closed_descriptors.append(descriptor)
        return original_close(descriptor)

    monkeypatch.setattr(patcher_module.os, "fsync", fail_fsync)
    monkeypatch.setattr(patcher_module.os, "close", record_close)
    try:
        with pytest.raises(patcher_module.PatcherSecurityError):
            patcher._write_temporary_file(parent_fd, b"new", 0o600)
    finally:
        original_fsync(parent_fd)
        original_close(parent_fd)

    assert closed_descriptors
    assert not list(tmp_path.glob(".ternexar-patch-*.tmp"))


def test_apply_patch_cleans_temporary_file_when_rename_or_directory_sync_fails(
    tmp_path, monkeypatch
):
    target = tmp_path / "app.py"
    target.write_text("original")
    patcher = Patcher(project_root=tmp_path)
    monkeypatch.setattr(
        patcher,
        "_renameat2",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("rename failure")),
    )

    rename_result = patcher.apply_patch(target, "new")

    assert rename_result.success is False
    assert target.read_text() == "original"
    assert not list(tmp_path.glob(".ternexar-patch-*.tmp"))

    monkeypatch.undo()
    original_fsync = patcher_module.os.fsync
    original_commit = patcher._atomic_commit
    committed = False

    def note_commit(*args, **kwargs):
        nonlocal committed
        commit_result = original_commit(*args, **kwargs)
        committed = True
        return commit_result

    def fail_directory_sync(descriptor):
        if committed:
            raise OSError("directory fsync failure")
        return original_fsync(descriptor)

    monkeypatch.setattr(patcher, "_atomic_commit", note_commit)
    monkeypatch.setattr(patcher_module.os, "fsync", fail_directory_sync)
    sync_result = patcher.apply_patch(target, "newer")

    assert sync_result.success is True
    assert target.read_text() == "newer"
    assert sync_result.error is None
    assert "committed" in (sync_result.warning or "").lower()
    assert not list(tmp_path.glob(".ternexar-patch-*.tmp"))


def test_write_all_rejects_zero_length_write(monkeypatch):
    monkeypatch.setattr(patcher_module.os, "write", lambda *args, **kwargs: 0)

    with pytest.raises(OSError, match="complete"):
        Patcher._write_all(123, b"content")


def test_open_unique_file_retries_collision_with_exclusive_creation(
    tmp_path, monkeypatch
):
    patcher = Patcher(project_root=tmp_path)
    parent_fd, _ = patcher._open_parent_directory(("app.py",))
    tokens = iter(("taken", "fresh"))
    (tmp_path / ".ternexar-patch-taken.tmp").write_text("occupied")
    monkeypatch.setattr(patcher_module.secrets, "token_hex", lambda _: next(tokens))
    descriptor, name = patcher._open_unique_file(
        parent_fd, ".ternexar-patch-", ".tmp", 0o600
    )
    try:
        assert name == ".ternexar-patch-fresh.tmp"
        assert stat.S_IMODE(os.fstat(descriptor).st_mode) == 0o600
    finally:
        os.close(descriptor)
        os.unlink(name, dir_fd=parent_fd)
        os.close(parent_fd)


@pytest.mark.parametrize(
    ("attribute", "expected"),
    [("O_NOFOLLOW", "no-follow"), ("O_DIRECTORY", "no-follow")],
)
def test_platform_constant_capability_absence_fails_closed(
    tmp_path, monkeypatch, attribute, expected
):
    target = tmp_path / "app.py"
    target.write_text("original")
    monkeypatch.delattr(patcher_module.os, attribute)

    result = Patcher(project_root=tmp_path).apply_patch(target, "new")

    assert result.success is False
    assert expected in (result.error or "").lower()


def test_platform_stat_capability_absence_fails_closed(tmp_path, monkeypatch):
    target = tmp_path / "app.py"
    target.write_text("original")
    monkeypatch.setattr(patcher_module.os, "supports_follow_symlinks", set())

    result = Patcher(project_root=tmp_path).apply_patch(target, "new")

    assert result.success is False
    assert "cannot inspect" in (result.error or "").lower()


def test_patcher_refuses_project_root_file_and_allows_nested_regular_file(tmp_path):
    root_file = tmp_path / "root-file"
    root_file.write_text("not a directory")
    root_file_result = Patcher(project_root=root_file).apply_patch(
        root_file / "app.py", "new"
    )

    project = tmp_path / "project"
    nested = project / "nested" / "app.py"
    nested.parent.mkdir(parents=True)
    nested.write_text("old")
    nested_result = Patcher(project_root=project).apply_patch(nested, "new")

    assert root_file_result.success is False
    assert "not a directory" in (root_file_result.error or "").lower()
    assert nested_result.success is True
    assert nested.read_text() == "new"


def test_read_target_rejects_opened_directory_and_growth_after_open(
    tmp_path, monkeypatch
):
    target = tmp_path / "app.py"
    target.write_text("small")
    patcher = Patcher(project_root=tmp_path)
    parent_fd, target_name = patcher._open_parent_directory(("app.py",))
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    original_open = patcher_module.os.open

    def open_directory(name, flags, *args, **kwargs):
        if name == target_name and kwargs.get("dir_fd") == parent_fd:
            return os.dup(directory_fd)
        return original_open(name, flags, *args, **kwargs)

    monkeypatch.setattr(patcher_module.os, "open", open_directory)
    try:
        with pytest.raises(patcher_module.PatcherSecurityError, match="regular file"):
            patcher._read_target(parent_fd, target_name)
    finally:
        monkeypatch.undo()
        os.close(directory_fd)
        os.close(parent_fd)

    parent_fd, target_name = patcher._open_parent_directory(("app.py",))
    monkeypatch.setattr(
        patcher_module.os,
        "read",
        lambda *_: b"x" * (patcher_module.MAX_FILE_SIZE + 1),
    )
    try:
        with pytest.raises(patcher_module.PatcherSecurityError, match="too large"):
            patcher._read_target(parent_fd, target_name)
    finally:
        os.close(parent_fd)


def test_read_target_reports_inspection_and_no_follow_open_failures(
    tmp_path, monkeypatch
):
    target = tmp_path / "app.py"
    target.write_text("original")
    patcher = Patcher(project_root=tmp_path)
    parent_fd, target_name = patcher._open_parent_directory(("app.py",))
    original_stat = patcher_module.os.stat

    def fail_target_stat(name, *args, **kwargs):
        if name == target_name and kwargs.get("dir_fd") == parent_fd:
            raise OSError("inspection failure")
        return original_stat(name, *args, **kwargs)

    monkeypatch.setattr(patcher_module.os, "stat", fail_target_stat)
    try:
        with pytest.raises(patcher_module.PatcherSecurityError, match="inspect"):
            patcher._read_target(parent_fd, target_name)
    finally:
        monkeypatch.undo()
        os.close(parent_fd)

    parent_fd, target_name = patcher._open_parent_directory(("app.py",))
    original_open = patcher_module.os.open

    def fail_target_open(name, flags, *args, **kwargs):
        if name == target_name and kwargs.get("dir_fd") == parent_fd:
            raise OSError(errno.ELOOP, "symlink loop")
        return original_open(name, flags, *args, **kwargs)

    monkeypatch.setattr(patcher_module.os, "open", fail_target_open)
    try:
        with pytest.raises(patcher_module.PatcherSecurityError, match="symlink"):
            patcher._read_target(parent_fd, target_name)
    finally:
        os.close(parent_fd)


def test_backup_directory_and_file_creation_failures_are_controlled(
    tmp_path, monkeypatch
):
    patcher = Patcher(project_root=tmp_path)
    root_fd = patcher._open_project_root()
    monkeypatch.setattr(
        patcher_module.os,
        "mkdir",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("mkdir failure")),
    )
    try:
        with pytest.raises(patcher_module.PatcherSecurityError, match="create backup"):
            patcher._open_or_create_directory(root_fd, "backups")
    finally:
        monkeypatch.undo()
        os.close(root_fd)

    symlink = tmp_path / "linked-backups"
    outside = tmp_path / "outside"
    outside.mkdir()
    symlink.symlink_to(outside, target_is_directory=True)
    root_fd = patcher._open_project_root()
    try:
        with pytest.raises(patcher_module.PatcherSecurityError, match="symlink"):
            patcher._open_or_create_directory(root_fd, "linked-backups")
    finally:
        os.close(root_fd)

    regular = tmp_path / "not-a-directory"
    regular.write_text("x")
    root_fd = patcher._open_project_root()
    try:
        with pytest.raises(
            patcher_module.PatcherSecurityError, match="not a directory"
        ):
            patcher._open_or_create_directory(root_fd, "not-a-directory")
    finally:
        os.close(root_fd)


def test_backup_write_failure_cleans_partial_backup(tmp_path, monkeypatch):
    patcher = Patcher(project_root=tmp_path)
    monkeypatch.setattr(
        patcher,
        "_write_all",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("write failure")),
    )

    root_fd = patcher._open_project_root()
    try:
        with pytest.raises(OSError, match="write failure"):
            patcher._write_backup(root_fd, "app.py", b"original")
    finally:
        os.close(root_fd)

    assert not list(patcher.backup_dir.glob("*.tx.bak"))


def test_unique_file_creation_error_and_verify_failure_paths(tmp_path, monkeypatch):
    patcher = Patcher(project_root=tmp_path)
    parent_fd, _ = patcher._open_parent_directory(("app.py",))
    monkeypatch.setattr(
        patcher_module.os,
        "open",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("open failure")),
    )
    try:
        with pytest.raises(patcher_module.PatcherSecurityError, match="temporary file"):
            patcher._open_unique_file(parent_fd, ".tmp-", ".tmp", 0o600)
    finally:
        monkeypatch.undo()
        os.close(parent_fd)

    target = tmp_path / "app.py"
    target.write_text("original")
    parent_fd, target_name = patcher._open_parent_directory(("app.py",))
    state = patcher._read_target(parent_fd, target_name)
    target.unlink()
    target.mkdir()
    try:
        with pytest.raises(patcher_module.PatcherSecurityError, match="type changed"):
            patcher._verify_target_unchanged(parent_fd, target_name, state)
    finally:
        os.close(parent_fd)


def test_generate_diff_exception_and_oversized_patch_rejection(tmp_path, monkeypatch):
    target = tmp_path / "app.py"
    target.write_text("original")
    patcher = Patcher(project_root=tmp_path)
    monkeypatch.setattr(
        patcher,
        "_target_parts",
        lambda *_: (_ for _ in ()).throw(
            patcher_module.PatcherSecurityError("blocked")
        ),
    )
    assert patcher.generate_diff(target, "new") is None
    monkeypatch.undo()

    oversized_content = "\n".join(f"line-{index}" for index in range(101))
    result = patcher.apply_patch(target, oversized_content)

    assert result.success is False
    assert "too large" in (result.error or "").lower()
    assert target.read_text() == "original"


def test_parent_open_and_target_descriptor_failures_are_controlled(
    tmp_path, monkeypatch
):
    project = tmp_path / "project"
    nested = project / "nested"
    nested.mkdir(parents=True)
    target = nested / "app.py"
    target.write_text("original")
    patcher = Patcher(project_root=project)
    original_open = patcher_module.os.open

    def fail_parent_open(name, flags, *args, **kwargs):
        if name == "nested":
            raise OSError("parent open failure")
        return original_open(name, flags, *args, **kwargs)

    monkeypatch.setattr(patcher_module.os, "open", fail_parent_open)
    with pytest.raises(patcher_module.PatcherSecurityError, match="target parent"):
        patcher._open_parent_directory(("nested", "app.py"))
    monkeypatch.undo()

    parent_fd, target_name = patcher._open_parent_directory(("nested", "app.py"))
    original_fstat = patcher_module.os.fstat

    def oversized_fstat(descriptor):
        values = list(original_fstat(descriptor))
        values[6] = patcher_module.MAX_FILE_SIZE + 1
        return os.stat_result(values)

    monkeypatch.setattr(patcher_module.os, "fstat", oversized_fstat)
    try:
        with pytest.raises(patcher_module.PatcherSecurityError, match="too large"):
            patcher._read_target(parent_fd, target_name)
    finally:
        monkeypatch.undo()
        os.close(parent_fd)

    parent_fd, target_name = patcher._open_parent_directory(("nested", "app.py"))

    def fail_target_open(name, flags, *args, **kwargs):
        if name == target_name and kwargs.get("dir_fd") == parent_fd:
            raise OSError(errno.EACCES, "read denied")
        return original_open(name, flags, *args, **kwargs)

    monkeypatch.setattr(patcher_module.os, "open", fail_target_open)
    try:
        with pytest.raises(patcher_module.PatcherSecurityError, match="read patch"):
            patcher._read_target(parent_fd, target_name)
    finally:
        os.close(parent_fd)


def test_backup_descriptor_and_unique_name_failure_paths_are_controlled(
    tmp_path, monkeypatch
):
    patcher = Patcher(project_root=tmp_path)
    root_fd = patcher._open_project_root()
    original_open = patcher_module.os.open

    def fail_backup_open(name, flags, *args, **kwargs):
        if name == "backups":
            raise OSError("backup open failure")
        return original_open(name, flags, *args, **kwargs)

    monkeypatch.setattr(patcher_module.os, "open", fail_backup_open)
    try:
        with pytest.raises(
            patcher_module.PatcherSecurityError, match="backup directory"
        ):
            patcher._open_or_create_directory(root_fd, "backups")
    finally:
        monkeypatch.undo()
        os.close(root_fd)

    parent_fd, _ = patcher._open_parent_directory(("app.py",))
    (tmp_path / ".occupied.tmp").write_text("occupied")
    monkeypatch.setattr(patcher_module.secrets, "token_hex", lambda _: "occupied")
    try:
        with pytest.raises(patcher_module.PatcherSecurityError, match="unique"):
            patcher._open_unique_file(parent_fd, ".", ".tmp", 0o600)
    finally:
        os.close(parent_fd)


def test_verify_and_generate_diff_operational_errors_are_controlled(
    tmp_path, monkeypatch
):
    target = tmp_path / "app.py"
    target.write_text("original")
    patcher = Patcher(project_root=tmp_path)
    parent_fd, target_name = patcher._open_parent_directory(("app.py",))
    state = patcher._read_target(parent_fd, target_name)
    original_stat = patcher_module.os.stat

    def fail_verify_stat(name, *args, **kwargs):
        if name == target_name and kwargs.get("dir_fd") == parent_fd:
            raise OSError("verification failure")
        return original_stat(name, *args, **kwargs)

    monkeypatch.setattr(patcher_module.os, "stat", fail_verify_stat)
    try:
        with pytest.raises(patcher_module.PatcherSecurityError, match="verify"):
            patcher._verify_target_unchanged(parent_fd, target_name, state)
    finally:
        monkeypatch.undo()
        os.close(parent_fd)

    monkeypatch.setattr(patcher, "validate_file", lambda *_: (True, None))
    monkeypatch.setattr(
        patcher,
        "_read_target",
        lambda *_: (_ for _ in ()).throw(
            patcher_module.PatcherSecurityError("read failure")
        ),
    )
    assert patcher.generate_diff(target, "new") is None


def test_atomic_exchange_rolls_back_when_target_changes_after_verification(
    tmp_path, monkeypatch
):
    target = tmp_path / "app.py"
    target.write_text("verified original")
    raced_target = tmp_path / "raced.py"
    raced_target.write_text("raced replacement")
    patcher = Patcher(project_root=tmp_path)
    original_renameat2 = patcher._renameat2
    swapped = False

    def swap_immediately_before_commit(*args):
        nonlocal swapped
        if args[-1] == patcher_module.RENAME_EXCHANGE and not swapped:
            swapped = True
            os.replace(raced_target, target)
        return original_renameat2(*args)

    monkeypatch.setattr(patcher, "_renameat2", swap_immediately_before_commit)

    result = patcher.apply_patch(target, "new content")

    assert result.success is False
    assert target.read_text() == "raced replacement"
    assert "new content" not in target.read_text()


def test_directory_identity_swap_is_refused_for_root_and_parent(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    replacement_root = tmp_path / "replacement-root"
    replacement_root.mkdir()
    old_root = tmp_path / "old-root"
    patcher = Patcher(project_root=project)
    original_open = patcher_module.os.open

    def swap_root(path, flags, *args, **kwargs):
        if path == project:
            os.rename(project, old_root)
            os.rename(replacement_root, project)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(patcher_module.os, "open", swap_root)
    with pytest.raises(
        patcher_module.PatcherSecurityError, match="changed while opening"
    ):
        patcher._open_project_root()
    monkeypatch.undo()

    nested = project / "nested"
    nested.mkdir()
    replacement_parent = project / "replacement-parent"
    replacement_parent.mkdir()
    old_parent = project / "old-parent"
    original_open = patcher_module.os.open

    def swap_parent(path, flags, *args, **kwargs):
        if path == "nested":
            os.rename(nested, old_parent)
            os.rename(replacement_parent, nested)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(patcher_module.os, "open", swap_parent)
    with pytest.raises(
        patcher_module.PatcherSecurityError, match="changed while opening"
    ):
        patcher._open_parent_directory(("nested", "app.py"))


def test_backup_directory_identity_swap_is_refused(tmp_path, monkeypatch):
    patcher = Patcher(project_root=tmp_path)
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    replacement = tmp_path / "replacement-backups"
    replacement.mkdir()
    old_backup = tmp_path / "old-backups"
    root_fd = patcher._open_project_root()
    original_open = patcher_module.os.open

    def swap_backup(path, flags, *args, **kwargs):
        if path == "backups":
            os.rename(backup_dir, old_backup)
            os.rename(replacement, backup_dir)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(patcher_module.os, "open", swap_backup)
    try:
        with pytest.raises(
            patcher_module.PatcherSecurityError, match="changed while opening"
        ):
            patcher._open_or_create_directory(root_fd, "backups")
    finally:
        os.close(root_fd)


def test_unsupported_atomic_commit_fails_without_mutating_target(tmp_path, monkeypatch):
    target = tmp_path / "app.py"
    target.write_text("original")
    patcher = Patcher(project_root=tmp_path)
    monkeypatch.setattr(
        patcher,
        "_renameat2",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError(errno.ENOSYS, "missing")),
    )

    result = patcher.apply_patch(target, "new")

    assert result.success is False
    assert "unsupported" in (result.error or "").lower()
    assert target.read_text() == "original"


def test_secure_platform_rejects_non_linux_atomic_commit_support(monkeypatch):
    patcher = Patcher(project_root=Path.cwd())
    monkeypatch.setattr(patcher_module.sys, "platform", "darwin")

    assert "atomic conditional rename" in (patcher._secure_platform_error() or "")


def test_project_root_open_os_error_is_reported_as_a_security_failure(
    tmp_path, monkeypatch
):
    patcher = Patcher(project_root=tmp_path)
    monkeypatch.setattr(
        patcher,
        "_open_verified_directory",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("root open failure")),
    )

    with pytest.raises(
        patcher_module.PatcherSecurityError, match="project root safely"
    ):
        patcher._open_project_root()


def test_verified_directory_rejects_type_change_and_fstat_failure(
    tmp_path, monkeypatch
):
    patcher = Patcher(project_root=tmp_path)
    original_fstat = patcher_module.os.fstat
    regular = tmp_path / "regular.py"
    regular.write_text("content")
    regular_stat = os.stat(regular)

    monkeypatch.setattr(patcher_module.os, "fstat", lambda _: regular_stat)
    with pytest.raises(patcher_module.PatcherSecurityError, match="changed type"):
        patcher._open_verified_directory(tmp_path, error_context="Test directory")

    monkeypatch.setattr(
        patcher_module.os,
        "fstat",
        lambda _: (_ for _ in ()).throw(OSError("fstat failure")),
    )
    with pytest.raises(
        patcher_module.PatcherSecurityError, match="verify test directory"
    ):
        patcher._open_verified_directory(tmp_path, error_context="Test directory")
    monkeypatch.setattr(patcher_module.os, "fstat", original_fstat)


def test_backup_directory_fchmod_failure_closes_descriptor(tmp_path, monkeypatch):
    patcher = Patcher(project_root=tmp_path)
    root_fd = patcher._open_project_root()
    closed = []
    original_close = patcher_module.os.close
    monkeypatch.setattr(
        patcher_module.os,
        "fchmod",
        lambda *_: (_ for _ in ()).throw(OSError("chmod failure")),
    )
    monkeypatch.setattr(
        patcher_module.os,
        "close",
        lambda descriptor: (closed.append(descriptor), original_close(descriptor))[1],
    )
    try:
        with pytest.raises(
            patcher_module.PatcherSecurityError, match="backup directory"
        ):
            patcher._open_or_create_directory(root_fd, "backups")
    finally:
        original_close(root_fd)

    assert closed


def test_backup_and_temporary_cleanup_errors_are_suppressed_after_primary_failure(
    tmp_path, monkeypatch
):
    target = tmp_path / "app.py"
    target.write_text("original")
    patcher = Patcher(project_root=tmp_path)
    original_unlink = patcher_module.os.unlink

    monkeypatch.setattr(
        patcher,
        "_write_all",
        lambda *_: (_ for _ in ()).throw(OSError("write failure")),
    )
    monkeypatch.setattr(
        patcher_module.os,
        "unlink",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("cleanup failure")),
    )
    root_fd = patcher._open_project_root()
    try:
        with pytest.raises(OSError, match="write failure"):
            patcher._write_backup(root_fd, "app.py", b"original")
    finally:
        os.close(root_fd)

    parent_fd, _ = patcher._open_parent_directory(("app.py",))
    try:
        with pytest.raises(
            patcher_module.PatcherSecurityError, match="temporary patch"
        ):
            patcher._write_temporary_file(parent_fd, b"new", 0o600)
    finally:
        monkeypatch.setattr(patcher_module.os, "unlink", original_unlink)
        os.close(parent_fd)


def test_renameat2_capability_and_syscall_errors_are_controlled(monkeypatch):
    original_uname = patcher_module.os.uname
    monkeypatch.setattr(
        patcher_module.os,
        "uname",
        lambda: type("Info", (), {"machine": "unknown"})(),
    )
    with pytest.raises(patcher_module.PatcherSecurityError, match="unsupported"):
        Patcher._renameat2(1, "one", 1, "two", patcher_module.RENAME_NOREPLACE)

    class FailingLibc:
        def syscall(self, *args):
            return -1

    monkeypatch.setattr(patcher_module.os, "uname", original_uname)
    monkeypatch.setattr(
        patcher_module.ctypes, "CDLL", lambda *args, **kwargs: FailingLibc()
    )
    monkeypatch.setattr(patcher_module.ctypes, "get_errno", lambda: errno.ENOSYS)
    with pytest.raises(OSError) as error:
        Patcher._renameat2(1, "one", 1, "two", patcher_module.RENAME_NOREPLACE)
    assert error.value.errno == errno.ENOSYS


def test_atomic_new_target_appearance_and_exchanged_read_failure_are_refused(
    tmp_path, monkeypatch
):
    patcher = Patcher(project_root=tmp_path)
    parent_fd, target_name = patcher._open_parent_directory(("app.py",))
    temporary = tmp_path / ".ternexar-patch-test.tmp"
    temporary.write_text("new")
    try:
        new_state = patcher._read_target(parent_fd, target_name)
        monkeypatch.setattr(
            patcher,
            "_renameat2",
            lambda *args: (_ for _ in ()).throw(FileExistsError("appeared")),
        )
        with pytest.raises(patcher_module.PatcherSecurityError, match="appeared"):
            patcher._atomic_commit(parent_fd, temporary.name, target_name, new_state)

        target = tmp_path / "app.py"
        target.write_text("old")
        state = patcher._read_target(parent_fd, target_name)
        monkeypatch.setattr(patcher, "_renameat2", lambda *args: None)
        monkeypatch.setattr(
            patcher,
            "_read_target",
            lambda *args: (_ for _ in ()).throw(
                patcher_module.PatcherSecurityError("exchanged read failure")
            ),
        )
        with pytest.raises(
            patcher_module.PatcherSecurityError, match="could not verify"
        ):
            patcher._atomic_commit(parent_fd, temporary.name, target_name, state)
    finally:
        os.close(parent_fd)


def test_post_commit_old_entry_cleanup_failure_is_a_success_with_warning(
    tmp_path, monkeypatch
):
    target = tmp_path / "app.py"
    target.write_text("old")
    patcher = Patcher(project_root=tmp_path)
    original_unlink = patcher_module.os.unlink
    monkeypatch.setattr(patcher, "_secure_platform_error", lambda: None)

    def fail_only_exchanged_old(name, *args, **kwargs):
        if str(name).startswith(".ternexar-patch-"):
            raise OSError("old entry cleanup failure")
        return original_unlink(name, *args, **kwargs)

    monkeypatch.setattr(patcher_module.os, "unlink", fail_only_exchanged_old)
    result = patcher.apply_patch(target, "new")

    assert result.success is True
    assert target.read_text() == "new"
    assert result.error is None
    assert "committed" in (result.warning or "").lower()


def test_atomic_commit_refuses_in_place_content_change_before_exchange(
    tmp_path, monkeypatch
):
    """An attacker rewriting the target in place must not silently lose bytes."""
    target = tmp_path / "app.py"
    target.write_text("verified original")
    patcher = Patcher(project_root=tmp_path)
    original_renameat2 = patcher._renameat2
    injected = False

    def inject_before_exchange(*args):
        nonlocal injected
        if args[-1] == patcher_module.RENAME_EXCHANGE and not injected:
            injected = True
            with open(target, "w", encoding="utf-8") as handle:
                handle.write("attacker injected")
        return original_renameat2(*args)

    monkeypatch.setattr(patcher, "_renameat2", inject_before_exchange)

    result = patcher.apply_patch(target, "new content")

    assert result.success is False
    assert "changed before commit" in (result.error or "")
    assert target.read_text() == "attacker injected"
    assert not list(tmp_path.glob(".ternexar-patch-*.tmp"))


def test_failed_rollback_preserves_the_surviving_original_entry(tmp_path, monkeypatch):
    """A failed rollback must never delete the only copy of the previous entry."""
    target = tmp_path / "app.py"
    target.write_text("verified original")
    raced = tmp_path / "raced.py"
    raced.write_text("raced replacement")
    patcher = Patcher(project_root=tmp_path)
    original_renameat2 = patcher._renameat2
    exchanges = 0

    def swap_then_fail_rollback(*args):
        nonlocal exchanges
        exchanges += 1
        if exchanges == 1:
            os.replace(raced, target)
            return original_renameat2(*args)
        raise OSError(errno.EBUSY, "rollback failure")

    monkeypatch.setattr(patcher, "_renameat2", swap_then_fail_rollback)

    result = patcher.apply_patch(target, "new content")

    survivors = list(tmp_path.glob(".ternexar-patch-*.tmp"))
    assert result.success is False
    assert "rollback failed" in (result.error or "")
    assert len(survivors) == 1
    assert survivors[0].read_text() == "raced replacement"


def test_target_swapped_to_symlink_before_exchange_is_rolled_back(
    tmp_path, monkeypatch
):
    project = tmp_path / "project"
    project.mkdir()
    target = project / "app.py"
    target.write_text("original")
    outside = tmp_path / "outside.py"
    outside.write_text("outside content")
    patcher = Patcher(project_root=project)
    original_renameat2 = patcher._renameat2
    swapped = False

    def swap_to_symlink(*args):
        nonlocal swapped
        if args[-1] == patcher_module.RENAME_EXCHANGE and not swapped:
            swapped = True
            target.unlink()
            target.symlink_to(outside)
        return original_renameat2(*args)

    monkeypatch.setattr(patcher, "_renameat2", swap_to_symlink)

    result = patcher.apply_patch(target, "new content")

    assert result.success is False
    assert target.is_symlink()
    assert outside.read_text() == "outside content"
    assert not list(project.glob(".ternexar-patch-*.tmp"))


def test_backup_directory_entry_is_synced_before_replacement(tmp_path, monkeypatch):
    target = tmp_path / "app.py"
    target.write_text("original")
    patcher = Patcher(project_root=tmp_path)
    original_fsync = patcher_module.os.fsync
    synced_directories = []

    def record_directory_fsync(descriptor):
        info = os.fstat(descriptor)
        if stat.S_ISDIR(info.st_mode):
            synced_directories.append((info.st_dev, info.st_ino))
        return original_fsync(descriptor)

    monkeypatch.setattr(patcher_module.os, "fsync", record_directory_fsync)

    result = patcher.apply_patch(target, "new content")
    backups = os.stat(patcher.backup_dir)
    root = os.stat(tmp_path)

    assert result.success is True
    assert (backups.st_dev, backups.st_ino) in synced_directories
    assert (root.st_dev, root.st_ino) in synced_directories


def test_backup_stays_in_the_verified_root_when_the_root_path_is_swapped(
    tmp_path, monkeypatch
):
    """Backups must follow the verified root descriptor, not the root pathname."""
    project = tmp_path / "project"
    project.mkdir()
    target = project / "app.py"
    target.write_text("original")
    attacker_root = tmp_path / "attacker-root"
    attacker_root.mkdir()
    displaced = tmp_path / "displaced"
    patcher = Patcher(project_root=project)
    original_write_backup = patcher._write_backup

    def swap_root_then_backup(*args, **kwargs):
        os.rename(project, displaced)
        os.rename(attacker_root, project)
        return original_write_backup(*args, **kwargs)

    monkeypatch.setattr(patcher, "_write_backup", swap_root_then_backup)

    result = patcher.apply_patch(target, "new content")
    backups = list((displaced / ".ternexar" / "backups").glob("*.tx.bak"))

    assert result.success is True
    assert not (project / ".ternexar").exists()
    assert len(backups) == 1
    assert backups[0].read_text() == "original"


def test_unencodable_replacement_content_fails_before_any_mutation(tmp_path):
    target = tmp_path / "app.py"
    target.write_text("original")
    patcher = Patcher(project_root=tmp_path)

    result = patcher.apply_patch(target, "lone surrogate \ud800")

    assert result.success is False
    assert "utf-8" in (result.error or "").lower()
    assert target.read_text() == "original"
    assert not patcher.backup_dir.exists()


def test_temporary_file_close_failure_never_double_closes_or_leaks(
    tmp_path, monkeypatch
):
    patcher = Patcher(project_root=tmp_path)
    parent_fd, _ = patcher._open_parent_directory(("app.py",))
    original_close = patcher_module.os.close
    closes = []

    def failing_close(descriptor):
        closes.append(descriptor)
        original_close(descriptor)
        if descriptor != parent_fd and closes.count(descriptor) == 1:
            raise OSError(errno.EIO, "close failure")

    monkeypatch.setattr(patcher_module.os, "close", failing_close)
    try:
        with pytest.raises(patcher_module.PatcherSecurityError, match="temporary patch"):
            patcher._write_temporary_file(parent_fd, b"new", 0o600)
    finally:
        monkeypatch.undo()
        os.close(parent_fd)

    temporary_closes = [
        descriptor for descriptor in closes if descriptor != parent_fd
    ]
    assert temporary_closes
    assert len(temporary_closes) == len(set(temporary_closes))
    assert not list(tmp_path.glob(".ternexar-patch-*.tmp"))


def test_parent_descent_closes_new_descriptor_when_intermediate_close_fails(
    tmp_path, monkeypatch
):
    """A failing intermediate close must not leak the freshly opened descriptor."""
    project = tmp_path / "project"
    nested = project / "nested"
    nested.mkdir(parents=True)
    (nested / "app.py").write_text("original")
    patcher = Patcher(project_root=project)
    root_fd = patcher._open_project_root()
    original_close = patcher_module.os.close
    closed = []

    def fail_first_intermediate_close(descriptor):
        closed.append(descriptor)
        original_close(descriptor)
        if len(closed) == 1:
            raise OSError(errno.EIO, "close failure")

    monkeypatch.setattr(patcher_module.os, "close", fail_first_intermediate_close)
    try:
        with pytest.raises(patcher_module.PatcherSecurityError, match="target parent"):
            patcher._descend_parent(root_fd, ("nested", "app.py"))
    finally:
        monkeypatch.undo()
        os.close(root_fd)

    assert len(closed) == 2
    assert len(set(closed)) == 2


def test_clean_commit_reports_no_error_and_no_warning(tmp_path):
    """A normal patch stays an unqualified success."""
    target = tmp_path / "app.py"
    target.write_text("original")

    result = Patcher(project_root=tmp_path).apply_patch(target, "new content")

    assert result.success is True
    assert result.error is None
    assert result.warning is None
    assert target.read_text() == "new content"


def test_no_op_patch_reports_no_error_and_no_warning(tmp_path):
    target = tmp_path / "app.py"
    target.write_text("identical")

    result = Patcher(project_root=tmp_path).apply_patch(target, "identical")

    assert result.success is True
    assert result.error is None
    assert result.warning is None
    assert result.diff is None


def test_pre_commit_failure_reports_error_and_no_warning(tmp_path):
    """An uncommitted patch keeps success=False with error, never a warning."""
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("outside content")
    target = project / "app.py"
    target.symlink_to(outside)

    result = Patcher(project_root=project).apply_patch(target, "new content")

    assert result.success is False
    assert result.error is not None
    assert result.warning is None
    assert outside.read_text() == "outside content"


def test_committed_patch_with_unlink_failure_is_a_warning_not_an_error(
    tmp_path, monkeypatch
):
    """Exchanged-old-entry cleanup failure is partial success, not failure."""
    target = tmp_path / "app.py"
    target.write_text("old")
    patcher = Patcher(project_root=tmp_path)
    original_unlink = patcher_module.os.unlink
    # Replacing os.unlink removes it from os.supports_dir_fd, so the real
    # platform guard would otherwise refuse before reaching the commit path.
    monkeypatch.setattr(patcher, "_secure_platform_error", lambda: None)

    def fail_only_exchanged_old(name, *args, **kwargs):
        if str(name).startswith(".ternexar-patch-"):
            raise OSError("old entry cleanup failure")
        return original_unlink(name, *args, **kwargs)

    monkeypatch.setattr(patcher_module.os, "unlink", fail_only_exchanged_old)

    result = patcher.apply_patch(target, "new")

    assert result.success is True
    assert result.error is None
    assert result.warning is not None
    assert "cleanup" in result.warning.lower()
    assert target.read_text() == "new"


def test_committed_patch_with_directory_fsync_failure_is_a_warning(
    tmp_path, monkeypatch
):
    """Durability sync failure after commit is partial success, not failure."""
    target = tmp_path / "app.py"
    target.write_text("old")
    patcher = Patcher(project_root=tmp_path)
    original_fsync = patcher_module.os.fsync
    original_commit = patcher._atomic_commit
    committed = False

    def note_commit(*args, **kwargs):
        nonlocal committed
        commit_result = original_commit(*args, **kwargs)
        committed = True
        return commit_result

    def fail_after_commit(descriptor):
        if committed:
            raise OSError("directory fsync failure")
        return original_fsync(descriptor)

    monkeypatch.setattr(patcher, "_atomic_commit", note_commit)
    monkeypatch.setattr(patcher_module.os, "fsync", fail_after_commit)

    result = patcher.apply_patch(target, "new")

    assert result.success is True
    assert result.error is None
    assert result.warning is not None
    assert "durability" in result.warning.lower()
    assert target.read_text() == "new"


def test_success_never_carries_an_error_across_representative_outcomes(
    tmp_path, monkeypatch
):
    """The contract invariant: success=True implies error is None."""
    clean_target = tmp_path / "clean.py"
    clean_target.write_text("old")
    warned_target = tmp_path / "warned.py"
    warned_target.write_text("old")
    patcher = Patcher(project_root=tmp_path)

    clean = patcher.apply_patch(clean_target, "new")

    original_unlink = patcher_module.os.unlink

    def fail_only_exchanged_old(name, *args, **kwargs):
        if str(name).startswith(".ternexar-patch-"):
            raise OSError("old entry cleanup failure")
        return original_unlink(name, *args, **kwargs)

    monkeypatch.setattr(patcher, "_secure_platform_error", lambda: None)
    monkeypatch.setattr(patcher_module.os, "unlink", fail_only_exchanged_old)
    warned = patcher.apply_patch(warned_target, "new")
    monkeypatch.undo()

    refused = patcher.apply_patch(tmp_path / "image.png", "new")

    for outcome in (clean, warned, refused):
        assert outcome.success is not (outcome.error is not None)
        if outcome.warning is not None:
            assert outcome.success is True
            assert outcome.error is None
