import os
from pathlib import Path
from typing import List, Dict, Optional

UNSAFE_PATHS = [
    "/", "/etc", "/usr", "/var", "/proc", "/sys", "/dev", "/bin", "/sbin", "/lib", "/root", "/boot"
]

SENSITIVE_PATTERNS = [
    ".env", "*.key", "*.pem", "credentials*", "secrets*", "token*", "password*"
]

METADATA_FILES = {
    "pyproject.toml": "PYTHON",
    "requirements.txt": "PYTHON",
    "setup.py": "PYTHON",
    "package.json": "NODE",
    "vite.config.js": "NODE",
    "vite.config.ts": "NODE",
    "next.config.js": "NODE",
    "next.config.mjs": "NODE",
    "Cargo.toml": "RUST",
    "go.mod": "GO",
    "pom.xml": "JAVA",
    "build.gradle": "JAVA",
    "index.html": "STATIC_WEB",
    "README.md": "METADATA"
}

SKIP_FOLDERS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build", "target"
}

MAX_READ_SIZE = 100 * 1024  # 100 KB

class WorkspaceManager:
    def is_path_safe(self, path: str) -> bool:
        """Check if the path is outside protected system directories."""
        abs_path = str(Path(path).resolve())
        for unsafe in UNSAFE_PATHS:
            if abs_path == unsafe or abs_path.startswith(f"{unsafe}/"):
                # Special case: allow users to scan their own subdirectories if they happen to be in /home
                # but UNSAFE_PATHS covers root-level system folders.
                # Usually /home is safe.
                if abs_path.startswith("/home/"):
                    return True
                return False
        return True

    def is_file_safe(self, file_path: Path) -> bool:
        """Check if a file is safe to read (not sensitive, not binary, not too large)."""
        if file_path.name.startswith("."):
            return False
            
        name = file_path.name.lower()
        for pattern in SENSITIVE_PATTERNS:
            if Path(name).match(pattern.lower()):
                return False

        if not file_path.exists():
            return False

        if file_path.stat().st_size > MAX_READ_SIZE:
            return False

        # Basic binary check
        try:
            with open(file_path, 'tr') as f:
                f.read(512)
        except (UnicodeDecodeError, PermissionError):
            return False

        return True

    def get_tree(self, path: str, max_depth: int = 3) -> Dict:
        """Generate a safe folder tree structure."""
        if not self.is_path_safe(path):
            return {"error": "Path is protected or unsafe."}

        root_path = Path(path).resolve()
        if not root_path.exists() or not root_path.is_dir():
            return {"error": "Path does not exist or is not a directory."}

        return self._build_tree_recursive(root_path, 0, max_depth)

    def _build_tree_recursive(self, current_path: Path, depth: int, max_depth: int) -> Dict:
        node = {
            "name": current_path.name or str(current_path),
            "type": "directory",
            "children": []
        }

        if depth >= max_depth:
            return node

        try:
            with os.scandir(current_path) as entries:
                for entry in sorted(entries, key=lambda e: e.name):
                    if entry.name.startswith(".") or entry.name in SKIP_FOLDERS:
                        continue

                    if entry.is_dir():
                        node["children"].append(self._build_tree_recursive(Path(entry.path), depth + 1, max_depth))
                    elif entry.is_file():
                        node["children"].append({
                            "name": entry.name,
                            "type": "file"
                        })
        except PermissionError:
            pass

        return node

    def scan(self, path: str) -> Dict:
        """Scan project for type, dependencies, and metadata."""
        if not self.is_path_safe(path):
            return {"error": "Path is protected or unsafe."}

        root_path = Path(path).resolve()
        if not root_path.exists() or not root_path.is_dir():
            return {"error": "Path does not exist or is not a directory."}

        detected_types = set()
        important_files = []
        
        try:
            with os.scandir(root_path) as entries:
                for entry in entries:
                    if entry.name in METADATA_FILES:
                        detected_types.add(METADATA_FILES[entry.name])
                        important_files.append(entry.name)
                    
                    # Also check for src/ to hint at Node/Python/etc
                    if entry.is_dir() and entry.name == "src":
                        important_files.append("src/")
        except PermissionError:
            return {"error": "Permission denied."}

        # Refine type detection
        project_type = "UNKNOWN"
        if "PYTHON" in detected_types:
            project_type = "PYTHON"
        elif "NODE" in detected_types:
            project_type = "NODE"
        elif "RUST" in detected_types:
            project_type = "RUST"
        elif "GO" in detected_types:
            project_type = "GO"
        elif "JAVA" in detected_types:
            project_type = "JAVA"
        elif "STATIC_WEB" in detected_types:
            project_type = "STATIC_WEB"

        # Try to read README if it exists
        readme_content = None
        readme_path = root_path / "README.md"
        if readme_path.exists() and self.is_file_safe(readme_path):
            try:
                readme_content = readme_path.read_text(errors='ignore')[:500] + "..."
            except Exception:
                pass

        return {
            "path": str(root_path),
            "project_type": project_type,
            "important_files": sorted(important_files),
            "readme_preview": readme_content,
            "sensitive_files_skipped": True
        }

workspace_manager = WorkspaceManager()
