import os
from pathlib import Path
from typing import List, Dict

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

class ProjectLocator:
    def __init__(self):
        self.roots = []
        for r in SAFE_ROOTS:
            path = Path(r).expanduser().resolve()
            if path.exists() and path.is_dir():
                if path not in self.roots:
                    self.roots.append(path)

    def locate(self, query: str) -> List[Dict]:
        """Search for directories matching the query within safe roots."""
        results = []
        query = query.lower()

        for root in self.roots:
            if len(results) >= MAX_RESULTS:
                break
            self._search_recursive(root, query, 0, results)

        return results[:MAX_RESULTS]

    def _search_recursive(self, current_dir: Path, query: str, depth: int, results: List[Dict]):
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
                        # Check for match
                        if query in entry.name.lower():
                            match_type = "exact" if query == entry.name.lower() else "partial"
                            results.append({
                                "name": entry.name,
                                "path": str(Path(entry.path)),
                                "match_type": match_type
                            })

                        # Recursive search
                        self._search_recursive(Path(entry.path), query, depth + 1, results)
        except (PermissionError, OSError):
            # Gracefully handle permission errors or other OS issues
            pass

locator = ProjectLocator()
