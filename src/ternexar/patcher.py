import ctypes
import difflib
import errno
import os
import secrets
import stat
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from ternexar.ui import ui


SAFE_EXTENSIONS = {".py", ".md", ".toml", ".txt", ".json", ".yaml", ".yml", ""}
SENSITIVE_KEYWORDS = {"secret", "token", "key", "password", "credential"}
MAX_FILE_SIZE = 100 * 1024
MAX_PATCH_LINES = 100
BLOCKED_FOLDERS = {
    ".git",
    ".ssh",
    ".venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
}
NEW_FILE_MODE = 0o600
RENAME_NOREPLACE = 1
RENAME_EXCHANGE = 2
_RENAMEAT2_SYSCALLS = {
    "x86_64": 316,
    "aarch64": 276,
    "armv7l": 382,
    "i386": 353,
    "ppc64": 357,
    "ppc64le": 357,
    "s390x": 347,
    "riscv64": 276,
}


class PatcherSecurityError(RuntimeError):
    """A fail-closed filesystem safety violation."""


class PatcherRollbackError(PatcherSecurityError):
    """An exchange was committed and could not be undone.

    The target holds the replacement and the previous directory entry survives
    under the temporary name, so that entry must never be cleaned up.
    """


@dataclass
class PatchResult:
    """Outcome of a patch attempt.

    Exactly three states are representable:

    * ``success=False`` with ``error`` set: the replacement was **not**
      committed and the target is untouched. Retrying is safe.
    * ``success=True`` with neither ``error`` nor ``warning``: the replacement
      committed cleanly (or the patch was an exact no-op).
    * ``success=True`` with ``warning`` set: the replacement **did** commit, but
      post-commit cleanup or durability degraded. The target holds the new
      content, so callers must not retry; they must surface the warning.

    ``error`` therefore always means "not applied", and ``success`` being true
    implies ``error is None``.
    """

    success: bool
    file_path: Optional[Path] = None
    backup_path: Optional[Path] = None
    error: Optional[str] = None
    diff: Optional[str] = None
    warning: Optional[str] = None


@dataclass
class _TargetState:
    exists: bool
    content: str
    raw_content: bytes
    identity: Optional[Tuple[int, int, int, int, int]] = None
    mode: int = NEW_FILE_MODE


class Patcher:
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = (project_root or Path.cwd()).absolute()
        self.backup_dir = self.project_root / ".ternexar" / "backups"

    def _secure_platform_error(self) -> Optional[str]:
        required_constants = ("O_NOFOLLOW", "O_DIRECTORY")
        if any(not hasattr(os, name) for name in required_constants):
            return "Secure patching is unavailable: this platform lacks no-follow directory support."
        if os.open not in os.supports_dir_fd or os.unlink not in os.supports_dir_fd:
            return "Secure patching is unavailable: this platform lacks descriptor-relative operations."
        if (
            os.stat not in os.supports_dir_fd
            or os.stat not in os.supports_follow_symlinks
        ):
            return "Secure patching is unavailable: this platform cannot inspect targets without following links."
        if sys.platform != "linux" or os.uname().machine not in _RENAMEAT2_SYSCALLS:
            return "Secure patching is unavailable: atomic conditional rename is unsupported on this platform."
        return None

    def _open_flags(self, base_flags: int) -> int:
        flags = base_flags | os.O_NOFOLLOW
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        return flags

    def _target_parts(self, file_path: Path) -> Tuple[str, ...]:
        candidate = file_path.absolute()
        try:
            relative = candidate.relative_to(self.project_root)
        except ValueError as error:
            raise PatcherSecurityError("File is outside the project root.") from error

        if not relative.parts or any(
            part in {"", ".", ".."} for part in relative.parts
        ):
            raise PatcherSecurityError("Invalid file path.")
        if any(part.startswith(".") for part in relative.parts):
            raise PatcherSecurityError("Access denied to hidden path.")
        if any(folder in relative.parts for folder in BLOCKED_FOLDERS):
            raise PatcherSecurityError("Access denied to restricted folder.")

        name = relative.name
        if (
            Path(name).suffix.lower() not in SAFE_EXTENSIONS
            and name != "requirements.txt"
        ):
            raise PatcherSecurityError(
                f"Unsupported file extension: {Path(name).suffix}"
            )
        if any(keyword in name.lower() for keyword in SENSITIVE_KEYWORDS):
            raise PatcherSecurityError("Sensitive file blocked.")
        return relative.parts

    def _open_project_root(self) -> int:
        try:
            return self._open_verified_directory(
                self.project_root,
                error_context="Project root",
            )
        except PatcherSecurityError:
            raise
        except OSError as error:
            raise PatcherSecurityError(
                f"Unable to open project root safely: {error}"
            ) from error

    def _descend_parent(self, root_fd: int, parts: Tuple[str, ...]) -> int:
        """Walk to the target parent using descriptors anchored at ``root_fd``.

        The caller retains ownership of ``root_fd`` so the same verified root
        descriptor can also anchor the backup directory.
        """
        directory_fd = os.dup(root_fd)
        try:
            for part in parts[:-1]:
                previous_fd = directory_fd
                directory_fd = self._open_verified_directory(
                    part,
                    dir_fd=previous_fd,
                    error_context="Target parent directory",
                )
                os.close(previous_fd)
            return directory_fd
        except PatcherSecurityError:
            os.close(directory_fd)
            raise
        except OSError as error:
            os.close(directory_fd)
            raise PatcherSecurityError(
                f"Unable to open target parent safely: {error}"
            ) from error

    def _open_parent_directory(self, parts: Tuple[str, ...]) -> Tuple[int, str]:
        root_fd = self._open_project_root()
        try:
            return self._descend_parent(root_fd, parts), parts[-1]
        finally:
            os.close(root_fd)

    @staticmethod
    def _identity(file_stat: os.stat_result) -> Tuple[int, int, int, int, int]:
        return (
            file_stat.st_dev,
            file_stat.st_ino,
            file_stat.st_size,
            file_stat.st_mtime_ns,
            file_stat.st_ctime_ns,
        )

    @staticmethod
    def _directory_identity(file_stat: os.stat_result) -> Tuple[int, int]:
        return file_stat.st_dev, file_stat.st_ino

    @staticmethod
    def _same_inode(
        first_identity: Optional[Tuple[int, int, int, int, int]],
        second_identity: Optional[Tuple[int, int, int, int, int]],
    ) -> bool:
        return (
            first_identity is not None
            and second_identity is not None
            and first_identity[:2] == second_identity[:2]
        )

    def _open_verified_directory(
        self,
        path: str | Path,
        *,
        dir_fd: Optional[int] = None,
        error_context: str,
    ) -> int:
        try:
            before = os.stat(path, dir_fd=dir_fd, follow_symlinks=False)
            if stat.S_ISLNK(before.st_mode):
                raise PatcherSecurityError(f"{error_context} symlink is refused.")
            if not stat.S_ISDIR(before.st_mode):
                raise PatcherSecurityError(f"{error_context} is not a directory.")
            descriptor = os.open(
                path,
                self._open_flags(os.O_RDONLY | os.O_DIRECTORY),
                dir_fd=dir_fd,
            )
        except PatcherSecurityError:
            raise
        except OSError as error:
            raise PatcherSecurityError(
                f"Unable to open {error_context.lower()} safely: {error}"
            ) from error

        try:
            opened = os.fstat(descriptor)
            if not stat.S_ISDIR(opened.st_mode):
                raise PatcherSecurityError(
                    f"{error_context} changed type while opening."
                )
            if self._directory_identity(opened) != self._directory_identity(before):
                raise PatcherSecurityError(f"{error_context} changed while opening.")
            return descriptor
        except PatcherSecurityError:
            os.close(descriptor)
            raise
        except OSError as error:
            os.close(descriptor)
            raise PatcherSecurityError(
                f"Unable to verify {error_context.lower()} safely: {error}"
            ) from error

    def _read_target(self, parent_fd: int, target_name: str) -> _TargetState:
        try:
            entry_stat = os.stat(target_name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return _TargetState(False, "", b"")
        except OSError as error:
            raise PatcherSecurityError(
                f"Unable to inspect patch target: {error}"
            ) from error

        if stat.S_ISLNK(entry_stat.st_mode):
            raise PatcherSecurityError("Target symlink is refused.")
        if not stat.S_ISREG(entry_stat.st_mode):
            raise PatcherSecurityError("Target is not a regular file.")
        if entry_stat.st_size > MAX_FILE_SIZE:
            raise PatcherSecurityError("File too large (Max 100KB).")

        descriptor: Optional[int] = None
        try:
            descriptor = os.open(
                target_name, self._open_flags(os.O_RDONLY), dir_fd=parent_fd
            )
            opened_stat = os.fstat(descriptor)
            if not stat.S_ISREG(opened_stat.st_mode):
                raise PatcherSecurityError("Target is not a regular file.")
            if opened_stat.st_size > MAX_FILE_SIZE:
                raise PatcherSecurityError("File too large (Max 100KB).")

            chunks = []
            total_size = 0
            while True:
                chunk = os.read(descriptor, 64 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    raise PatcherSecurityError("File too large (Max 100KB).")
            raw_content = b"".join(chunks)
            try:
                content = raw_content.decode("utf-8")
            except UnicodeDecodeError as error:
                raise PatcherSecurityError("Binary files are not supported.") from error
            return _TargetState(
                True,
                content,
                raw_content,
                self._identity(opened_stat),
                stat.S_IMODE(opened_stat.st_mode),
            )
        except PatcherSecurityError:
            raise
        except OSError as error:
            if error.errno == errno.ELOOP:
                raise PatcherSecurityError("Target symlink is refused.") from error
            raise PatcherSecurityError(
                f"Unable to read patch target safely: {error}"
            ) from error
        finally:
            if descriptor is not None:
                os.close(descriptor)

    @staticmethod
    def _make_diff(file_name: str, old_content: str, new_content: str) -> Optional[str]:
        if old_content == new_content:
            return None
        diff = difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{file_name}",
            tofile=f"b/{file_name}",
            lineterm="",
        )
        diff_text = "\n".join(diff)
        return diff_text or None

    @staticmethod
    def _unlink_quietly(directory_fd: int, name: str) -> None:
        """Best-effort cleanup that must not mask the failure being reported."""
        try:
            os.unlink(name, dir_fd=directory_fd)
        except OSError:
            pass

    def _open_or_create_directory(self, parent_fd: int, name: str) -> int:
        created = False
        try:
            os.mkdir(name, 0o700, dir_fd=parent_fd)
            created = True
        except FileExistsError:
            pass
        except OSError as error:
            raise PatcherSecurityError(
                f"Unable to create backup directory safely: {error}"
            ) from error

        descriptor: Optional[int] = None
        try:
            descriptor = self._open_verified_directory(
                name,
                dir_fd=parent_fd,
                error_context="Backup directory",
            )
            os.fchmod(descriptor, 0o700)
            if created:
                os.fsync(parent_fd)
            opened_descriptor = descriptor
            descriptor = None
            return opened_descriptor
        except PatcherSecurityError:
            raise
        except OSError as error:
            raise PatcherSecurityError(
                f"Unable to open backup directory safely: {error}"
            ) from error
        finally:
            if descriptor is not None:
                os.close(descriptor)

    def _open_unique_file(
        self, directory_fd: int, prefix: str, suffix: str, mode: int
    ) -> Tuple[int, str]:
        for _ in range(128):
            name = f"{prefix}{secrets.token_hex(16)}{suffix}"
            try:
                descriptor = os.open(
                    name,
                    self._open_flags(os.O_WRONLY | os.O_CREAT | os.O_EXCL),
                    mode,
                    dir_fd=directory_fd,
                )
                return descriptor, name
            except FileExistsError:
                continue
            except OSError as error:
                raise PatcherSecurityError(
                    f"Unable to create temporary file safely: {error}"
                ) from error
        raise PatcherSecurityError("Unable to allocate a unique temporary file safely.")

    @staticmethod
    def _write_all(descriptor: int, content: bytes) -> None:
        view = memoryview(content)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("Unable to write complete file contents.")
            view = view[written:]

    def _write_backup(self, root_fd: int, target_name: str, content: bytes) -> Path:
        """Persist verified original bytes below the already verified root."""
        ternexar_fd: Optional[int] = None
        backup_fd: Optional[int] = None
        try:
            ternexar_fd = self._open_or_create_directory(root_fd, ".ternexar")
            backup_fd = self._open_or_create_directory(ternexar_fd, "backups")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_fd, backup_name = self._open_unique_file(
                backup_fd,
                f"{target_name}_{timestamp}_",
                ".tx.bak",
                NEW_FILE_MODE,
            )
            try:
                try:
                    self._write_all(file_fd, content)
                    os.fsync(file_fd)
                finally:
                    os.close(file_fd)
                # The backup entry must outlive a crash that keeps the patch.
                os.fsync(backup_fd)
            except OSError:
                self._unlink_quietly(backup_fd, backup_name)
                raise
            return self.backup_dir / backup_name
        finally:
            if backup_fd is not None:
                os.close(backup_fd)
            if ternexar_fd is not None:
                os.close(ternexar_fd)

    def _write_temporary_file(self, parent_fd: int, content: bytes, mode: int) -> str:
        descriptor, temporary_name = self._open_unique_file(
            parent_fd, ".ternexar-patch-", ".tmp", NEW_FILE_MODE
        )
        try:
            try:
                self._write_all(descriptor, content)
                os.fsync(descriptor)
                os.fchmod(descriptor, mode)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except OSError as error:
            self._unlink_quietly(parent_fd, temporary_name)
            raise PatcherSecurityError(
                f"Unable to write temporary patch safely: {error}"
            ) from error
        return temporary_name

    @staticmethod
    def _renameat2(
        source_directory_fd: int,
        source_name: str,
        destination_directory_fd: int,
        destination_name: str,
        flags: int,
    ) -> None:
        """Invoke Linux renameat2 with descriptor-relative names only."""
        try:
            syscall_number = _RENAMEAT2_SYSCALLS[os.uname().machine]
        except (AttributeError, KeyError) as error:
            raise PatcherSecurityError(
                "Atomic conditional rename is unsupported on this platform."
            ) from error

        libc = ctypes.CDLL(None, use_errno=True)
        result = libc.syscall(
            ctypes.c_long(syscall_number),
            ctypes.c_int(source_directory_fd),
            ctypes.c_char_p(source_name.encode("utf-8")),
            ctypes.c_int(destination_directory_fd),
            ctypes.c_char_p(destination_name.encode("utf-8")),
            ctypes.c_uint(flags),
        )
        if result == -1:
            error_number = ctypes.get_errno()
            raise OSError(error_number, os.strerror(error_number))

    def _rollback_exchange(
        self, parent_fd: int, temporary_name: str, target_name: str
    ) -> None:
        try:
            self._renameat2(
                parent_fd,
                temporary_name,
                parent_fd,
                target_name,
                RENAME_EXCHANGE,
            )
        except (OSError, PatcherSecurityError) as error:
            raise PatcherRollbackError(
                "Atomic commit verification failed and rollback failed; the "
                "target contains the replacement and the previous entry "
                f"survives as {temporary_name!r}: {error}"
            ) from error

    def _atomic_commit(
        self,
        parent_fd: int,
        temporary_name: str,
        target_name: str,
        target_state: _TargetState,
    ) -> Optional[str]:
        """Commit with renameat2, returning the exchanged old entry when present."""
        try:
            if not target_state.exists:
                self._renameat2(
                    parent_fd,
                    temporary_name,
                    parent_fd,
                    target_name,
                    RENAME_NOREPLACE,
                )
                return None

            self._renameat2(
                parent_fd,
                temporary_name,
                parent_fd,
                target_name,
                RENAME_EXCHANGE,
            )
        except FileExistsError as error:
            raise PatcherSecurityError(
                "A target appeared before atomic replacement."
            ) from error
        except OSError as error:
            if error.errno in {errno.ENOSYS, errno.EINVAL}:
                raise PatcherSecurityError(
                    "Atomic conditional rename is unsupported by this Linux kernel."
                ) from error
            raise PatcherSecurityError(f"Atomic replacement failed: {error}") from error

        try:
            exchanged_state = self._read_target(parent_fd, temporary_name)
        except PatcherSecurityError as error:
            self._rollback_exchange(parent_fd, temporary_name, target_name)
            raise PatcherSecurityError(
                f"Atomic replacement could not verify the exchanged target: {error}"
            ) from error

        # Identity alone would miss an in-place rewrite of the same inode, which
        # would destroy bytes that were never in the reviewed diff or the backup.
        if (
            not exchanged_state.exists
            or not self._same_inode(exchanged_state.identity, target_state.identity)
            or exchanged_state.raw_content != target_state.raw_content
        ):
            self._rollback_exchange(parent_fd, temporary_name, target_name)
            raise PatcherSecurityError(
                "Atomic replacement refused because the target changed before commit."
            )
        return temporary_name

    @staticmethod
    def _post_commit_result(
        file_path: Path,
        backup_path: Optional[Path],
        diff: str,
        durability_error: Optional[OSError],
    ) -> PatchResult:
        if durability_error is None:
            return PatchResult(
                success=True,
                file_path=file_path,
                backup_path=backup_path,
                diff=diff,
            )
        # The replacement is already committed, so this is never reported as a
        # failed application; it is a warning the caller must surface instead.
        return PatchResult(
            success=True,
            file_path=file_path,
            backup_path=backup_path,
            diff=diff,
            warning=(
                "Replacement committed, but post-commit cleanup or durability "
                f"sync failed: {durability_error}"
            ),
        )

    def _verify_target_unchanged(
        self, parent_fd: int, target_name: str, target_state: _TargetState
    ) -> None:
        try:
            current_stat = os.stat(target_name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            if target_state.exists:
                raise PatcherSecurityError(
                    "Patch target disappeared before replacement."
                )
            return
        except OSError as error:
            raise PatcherSecurityError(
                f"Unable to verify patch target safely: {error}"
            ) from error

        if stat.S_ISLNK(current_stat.st_mode):
            raise PatcherSecurityError("Target became a symlink before replacement.")
        if not stat.S_ISREG(current_stat.st_mode):
            raise PatcherSecurityError("Target type changed before replacement.")
        if not target_state.exists:
            raise PatcherSecurityError("A target appeared before replacement.")
        if self._identity(current_stat) != target_state.identity:
            raise PatcherSecurityError("Patch target changed before replacement.")

    def validate_file(self, file_path: Path) -> Tuple[bool, Optional[str]]:
        """Validate a patch target using descriptor-relative, no-follow operations."""
        platform_error = self._secure_platform_error()
        if platform_error:
            return False, platform_error
        try:
            parts = self._target_parts(file_path)
            parent_fd, target_name = self._open_parent_directory(parts)
            try:
                self._read_target(parent_fd, target_name)
            finally:
                os.close(parent_fd)
            return True, None
        except PatcherSecurityError as error:
            return False, str(error)

    def generate_diff(self, file_path: Path, new_content: str) -> Optional[str]:
        """Generate a diff only after safely reading the target descriptor."""
        valid, _ = self.validate_file(file_path)
        if not valid:
            return None
        try:
            parts = self._target_parts(file_path)
            parent_fd, target_name = self._open_parent_directory(parts)
            try:
                target_state = self._read_target(parent_fd, target_name)
            finally:
                os.close(parent_fd)
            return self._make_diff(target_name, target_state.content, new_content)
        except PatcherSecurityError:
            return None

    def apply_patch(self, file_path: Path, new_content: str) -> PatchResult:
        """Apply a patch atomically without following target or parent symlinks."""
        platform_error = self._secure_platform_error()
        if platform_error:
            return PatchResult(success=False, error=platform_error)

        root_fd: Optional[int] = None
        parent_fd: Optional[int] = None
        temporary_name: Optional[str] = None
        try:
            parts = self._target_parts(file_path)
            root_fd = self._open_project_root()
            parent_fd = self._descend_parent(root_fd, parts)
            target_name = parts[-1]
            target_state = self._read_target(parent_fd, target_name)
            diff = self._make_diff(target_name, target_state.content, new_content)
            if not diff:
                return PatchResult(success=True, diff=None)

            changed_lines = [
                line for line in diff.splitlines() if line.startswith(("+", "-"))
            ]
            if len(changed_lines) > MAX_PATCH_LINES:
                return PatchResult(
                    success=False, error="Patch too large (Max 100 lines changed)."
                )

            try:
                encoded_content = new_content.encode("utf-8")
            except UnicodeEncodeError as error:
                return PatchResult(
                    success=False,
                    error=f"Replacement content is not valid UTF-8 text: {error}",
                )

            if target_state.exists:
                backup_path = self._write_backup(
                    root_fd, target_name, target_state.raw_content
                )
            else:
                backup_path = None

            temporary_name = self._write_temporary_file(
                parent_fd, encoded_content, target_state.mode
            )
            self._verify_target_unchanged(parent_fd, target_name, target_state)
            exchanged_old_name = self._atomic_commit(
                parent_fd,
                temporary_name,
                target_name,
                target_state,
            )
            temporary_name = None
            post_commit_error: Optional[OSError] = None
            if exchanged_old_name is not None:
                try:
                    os.unlink(exchanged_old_name, dir_fd=parent_fd)
                except OSError as error:
                    post_commit_error = error
            try:
                os.fsync(parent_fd)
            except OSError as error:
                post_commit_error = post_commit_error or error
            return self._post_commit_result(
                file_path,
                backup_path,
                diff,
                post_commit_error,
            )
        except PatcherRollbackError as error:
            # The previous directory entry is the only surviving copy of the
            # original file, so it must be left in place for manual recovery.
            temporary_name = None
            return PatchResult(
                success=False, error=f"Failed to apply patch safely: {error}"
            )
        except (OSError, PatcherSecurityError) as error:
            return PatchResult(
                success=False, error=f"Failed to apply patch safely: {error}"
            )
        finally:
            if temporary_name is not None and parent_fd is not None:
                self._unlink_quietly(parent_fd, temporary_name)
            if parent_fd is not None:
                os.close(parent_fd)
            if root_fd is not None:
                os.close(root_fd)


patcher = Patcher()
