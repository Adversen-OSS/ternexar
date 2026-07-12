import difflib
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from ternexar.ui import ui

# Re-use safety constants from router if possible, but keep local for patcher-specific rigor
SAFE_EXTENSIONS = {".py", ".md", ".toml", ".txt", ".json", ".yaml", ".yml", ""}
SENSITIVE_KEYWORDS = {"secret", "token", "key", "password", "credential"}
MAX_FILE_SIZE = 100 * 1024  # 100 KB
MAX_PATCH_LINES = 100

BLOCKED_FOLDERS = {".git", ".ssh", ".venv", "node_modules", "__pycache__", "dist", "build"}

@dataclass
class PatchResult:
    success: bool
    file_path: Optional[Path] = None
    backup_path: Optional[Path] = None
    error: Optional[str] = None
    diff: Optional[str] = None

class Patcher:
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.backup_dir = self.project_root / ".ternexar" / "backups"

    def _ensure_backup_dir(self):
        if not self.backup_dir.exists():
            self.backup_dir.mkdir(parents=True, exist_ok=True)

    def validate_file(self, file_path: Path) -> Tuple[bool, Optional[str]]:
        """Strict validation of a file for patching."""
        try:
            resolved_path = file_path.resolve()
        except Exception:
            return False, "Invalid file path."

        # 1. Project-local check
        try:
            resolved_path.relative_to(self.project_root)
        except ValueError:
            return False, "File is outside the project root."

        # 2. Hidden file/folder check
        if any(part.startswith(".") and part != ".ternexar" for part in resolved_path.parts):
            # Special exception for files explicitly allowed if we ever need them, 
            # but generally block hidden things.
            if resolved_path.name != "requirements.txt": # requirements.txt is not hidden, but just being safe
                if any(part.startswith(".") for part in resolved_path.parts if part != "."):
                     return False, "Access denied to hidden path."

        # 3. Blocked folders
        if any(folder in resolved_path.parts for folder in BLOCKED_FOLDERS):
            return False, f"Access denied to restricted folder."

        # 4. Extension check
        if resolved_path.suffix.lower() not in SAFE_EXTENSIONS and resolved_path.name != "requirements.txt":
            return False, f"Unsupported file extension: {resolved_path.suffix}"

        # 5. Sensitive keywords in filename
        if any(kw in resolved_path.name.lower() for kw in SENSITIVE_KEYWORDS):
            return False, "Sensitive file blocked."

        # 6. File exists and is a file
        if resolved_path.exists():
            if not resolved_path.is_file():
                return False, "Target is not a file."
            
            # 7. Size limit
            if resolved_path.stat().st_size > MAX_FILE_SIZE:
                return False, "File too large (Max 100KB)."

            # 8. Text file check (basic)
            try:
                with open(resolved_path, "tr", encoding="utf-8") as f:
                    f.read(1024)
            except UnicodeDecodeError:
                return False, "Binary files are not supported."
        
        return True, None

    def generate_diff(self, file_path: Path, new_content: str) -> Optional[str]:
        """Generate a unified diff between current file and new content."""
        if not file_path.exists():
            # For new files like requirements.txt
            old_content = ""
            old_lines = []
            file_label = f"a/{file_path.name}"
        else:
            old_content = file_path.read_text(encoding="utf-8")
            old_lines = old_content.splitlines(keepends=True)
            file_label = f"a/{file_path.name}"

        if old_content == new_content:
            return None

        new_lines = new_content.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=file_label,
            tofile=f"b/{file_path.name}",
            lineterm=""
        )
        
        diff_text = "\n".join(diff)
        if not diff_text:
            return None
        
        return diff_text

    def apply_patch(self, file_path: Path, new_content: str) -> PatchResult:
        """Apply a patch safely with backup and atomic write."""
        valid, error = self.validate_file(file_path)
        if not valid:
            return PatchResult(success=False, error=error)

        # Patch size check
        new_lines = new_content.splitlines()
        if len(new_lines) > MAX_PATCH_LINES:
             # This is a bit loose, usually patch size means diff lines, 
             # but user said "patch changes <= 100 lines".
             # We'll check the diff lines in a real implementation if needed.
             pass

        diff = self.generate_diff(file_path, new_content)
        if not diff:
            return PatchResult(success=True, diff=None)

        # Re-check diff line count
        diff_lines = diff.splitlines()
        if len([line for line in diff_lines if line.startswith("+") or line.startswith("-")]) > MAX_PATCH_LINES:
             return PatchResult(success=False, error="Patch too large (Max 100 lines changed).")

        try:
            self._ensure_backup_dir()
            
            backup_path = None
            if file_path.exists():
                # Create backup with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                rel_path = file_path.relative_to(self.project_root)
                backup_filename = f"{rel_path.name}_{timestamp}.tx.bak"
                backup_path = self.backup_dir / backup_filename
                shutil.copy2(file_path, backup_path)

            # Atomic write
            temp_file = file_path.with_suffix(f"{file_path.suffix}.tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(new_content)
            
            os.replace(temp_file, file_path)
            
            return PatchResult(
                success=True, 
                file_path=file_path, 
                backup_path=backup_path, 
                diff=diff
            )

        except Exception as e:
            return PatchResult(success=False, error=f"Failed to apply patch: {str(e)}")

patcher = Patcher()
