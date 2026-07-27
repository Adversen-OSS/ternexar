import os
from pathlib import Path
from typing import List, Set, TypedDict
from ternexar.workspace_config import workspace_config

SAFE_ROOTS = [
    "~/",
    "~/projects",
    "~/code",
    "~/dev",
    "~/Desktop",
    "~/Documents"
]

SKIP_FOLDERS = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    "target",
    ".cache",
    ".local",
    ".ssh",
    ".gnupg"
}

MAX_DEPTH = 4
MAX_RESULTS = 20

class ProjectMatch(TypedDict):
    name: str
    path: str
    match_type: str

class ProjectLocator:
    def __init__(self):
        self._default_roots = []
        for r in SAFE_ROOTS:
            path = Path(r).expanduser().resolve()
            if path.exists() and path.is_dir():
                if path not in self._default_roots:
                    self._default_roots.append(path)

    @property
    def roots(self):
        """Backwards compatibility for tests."""
        return self._default_roots

    @roots.setter
    def roots(self, value):
        """Allows tests to override search roots."""
        self._default_roots = [Path(p).expanduser().resolve() for p in value]

    def _get_all_roots(self) -> List[Path]:
        """Combine default roots and custom workspace roots."""
        roots = list(self._default_roots)
        custom_roots = workspace_config.get_roots()
        for r in custom_roots:
            path = Path(r).expanduser().resolve()
            if path.exists() and path.is_dir() and path not in roots:
                roots.append(path)
        return roots

    def locate(self, query: str) -> List[ProjectMatch]:
        """Search for directories matching the query within safe roots."""
        results: List[ProjectMatch] = []
        seen_paths: Set[str] = set()
        query = query.lower()

        roots = self._get_all_roots()
        for root in roots:
            if len(results) >= MAX_RESULTS:
                break
            self._search_recursive(root, query, 0, results, seen_paths)

        return results[:MAX_RESULTS]

    def _search_recursive(
        self,
        current_dir: Path,
        query: str,
        depth: int,
        results: List[ProjectMatch],
        seen_paths: Set[str],
    ):
        if depth > MAX_DEPTH or len(results) >= MAX_RESULTS:
            return

        try:
            with os.scandir(current_dir) as entries:
                for entry in entries:
                    if len(results) >= MAX_RESULTS:
                        break

                    # Skip hidden files/folders and specific generated folders
                    if entry.name.startswith(".") or entry.name in SKIP_FOLDERS:
                        continue

                    if entry.is_dir():
                        entry_path = str(Path(entry.path).resolve())
                        
                        # Check for match
                        if query in entry.name.lower():
                            if entry_path not in seen_paths:
                                match_type = "exact" if query == entry.name.lower() else "partial"
                                results.append({
                                    "name": entry.name,
                                    "path": entry_path,
                                    "match_type": match_type
                                })
                                seen_paths.add(entry_path)

                        # Recursive search
                        self._search_recursive(Path(entry.path), query, depth + 1, results, seen_paths)
        except (PermissionError, OSError):
            # Gracefully handle permission errors or other OS issues
            pass

locator = ProjectLocator()
