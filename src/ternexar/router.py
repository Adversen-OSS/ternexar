import re
import os
from enum import Enum
from typing import Optional, List, Tuple
from pathlib import Path

from ternexar.risk import risk_engine, RiskLevel
from ternexar.do import is_in_allowlist
from ternexar.ui import ui

SAFE_EXTENSIONS = {".py", ".md", ".toml", ".txt", ".json", ".yaml", ".yml"}
SENSITIVE_KEYWORDS = {"secret", "token", "key", "password"}
MAX_FILE_SIZE = 100 * 1024  # 100 KB

class Intent(Enum):
    DO = "DO"
    ASK = "ASK"
    PLAN = "PLAN"
    PREVIEW = "PREVIEW"
    LOCATE = "LOCATE"
    SETUP = "SETUP"
    SCAN = "SCAN"
    VIEW = "VIEW"
    ANALYZE = "ANALYZE"
    INSTALL_REQUEST = "INSTALL_REQUEST"
    REFUSE = "REFUSE"
    UNKNOWN = "UNKNOWN"

class Router:
    def __init__(self):
        self.question_starters = {"what", "how", "explain", "why", "who", "where", "when", "can", "is", "are"}
        self.system_install_keywords = {"install python", "install node", "install docker", "install claude", "install codex", "install rust", "install go", "install java"}
        self.setup_keywords = {"setup", "prepare", "install dependencies", "run this project"}
        self.locate_keywords = {"find", "locate", "where is", "where is my", "search"}
        self.scan_keywords = {"scan", "inspect", "project type", "analyze project structure"}
        self.view_keywords = {"view", "show files", "list files", "project tree", "show project"}
        self.analyze_keywords = {"fix", "analyze", "debug", "broken", "error", "modulenotfounderror", "importerror"}

    def classify_intent(self, text: str) -> Intent:
        """Classify user intent based on heuristics and safety checks with v1.6 priority."""
        clean_text = text.strip().lower()
        if not clean_text:
            return Intent.UNKNOWN

        # 1. Explicit dangerous/destructive/secret input (Existing Risk Engine)
        analysis = risk_engine.analyze(text)
        if analysis.level in [RiskLevel.HIGH, RiskLevel.BLOCKED]:
            return Intent.REFUSE

        # 2. Installer/System Install Request
        if any(kw in clean_text for kw in self.system_install_keywords):
            return Intent.INSTALL_REQUEST
        
        # 3. Setup/Dependency Project Request
        if any(kw in clean_text for kw in self.setup_keywords):
            return Intent.SETUP

        # 4. Locate/Find/Where Request
        if any(clean_text.startswith(kw) for kw in self.locate_keywords):
            return Intent.LOCATE
        if "my" in clean_text and "project" in clean_text and "find" in clean_text:
             return Intent.LOCATE

        # 5. Scan/Inspect/Project Type Request
        if any(kw in clean_text for kw in self.scan_keywords):
            return Intent.SCAN

        # 6. View/Show Files/Tree Request
        if any(kw in clean_text for kw in self.view_keywords):
            return Intent.VIEW

        # 7. Fix/Debug/Error (ANALYZE)
        if any(kw in clean_text for kw in self.analyze_keywords):
            # Special case: "analyze project structure" is SCAN, not ANALYZE
            if "project structure" not in clean_text:
                return Intent.ANALYZE

        # 8. Raw LOW allowlisted command
        if is_in_allowlist(text):
            return Intent.DO

        # 9. Questions (ASK)
        first_word = clean_text.split()[0] if clean_text.split() else ""
        if first_word in self.question_starters or clean_text.endswith("?"):
            return Intent.ASK

        # 10. Default to PLAN for general tasks
        return Intent.PLAN

    def extract_tool_name(self, text: str) -> Optional[str]:
        """Extract a likely tool name from an install request."""
        clean_text = text.lower().strip()
        
        # Look for "install <tool>" pattern
        match = re.search(r"install\s+([\w\s\.\-3]+)", clean_text)
        if match:
            tool = match.group(1).strip()
            # Basic cleanup: remove trailing fluff like "for me", "please", etc.
            tool = re.sub(r"\s+(for me|please|now|on my system)$", "", tool)
            return tool
        return None

    def extract_target(self, text: str) -> Optional[str]:
        """Extract a likely project name or path target from the text."""
        clean_text = text.lower()
        
        # If "this project" is mentioned, implied current directory
        if "this project" in clean_text:
            return "."

        # Remove common keywords to find the subject
        subject = clean_text
        keywords_to_strip = (
            list(self.locate_keywords) + 
            list(self.scan_keywords) + 
            list(self.view_keywords) + 
            list(self.setup_keywords) +
            ["my", "project", "in"]
        )
        
        # Use word boundaries to avoid stripping fragments inside names (like 'in' in 'indexproject')
        import re
        for kw in sorted(keywords_to_strip, key=len, reverse=True):
            subject = re.sub(rf"\b{re.escape(kw)}\b", "", subject)
            
        subject = subject.strip()
        # Clean up any leftover punctuation or multiple spaces
        subject = re.sub(r"\s+", " ", subject).strip()
        return subject if subject else None

    def resolve_context(self, text: str) -> Tuple[str, List[str]]:
        """Extract @file references and validate them for safety."""
        pattern = r"(?:^|\s)@([\w\.\-/]+)"
        matches = re.findall(pattern, text)
        
        valid_context = []
        cleaned_text = text
        
        for path_str in matches:
            file_path = Path(path_str).resolve()
            
            # Remove the @path from the text to avoid redundancy
            cleaned_text = cleaned_text.replace(f"@{path_str}", "").strip()

            # Safety Checks
            if not file_path.exists():
                ui.warning(f"File not found: @{path_str}")
                continue
            
            if not file_path.is_file():
                ui.warning(f"Not a file: @{path_str}")
                continue

            # 1. Hidden files / sensitive folders
            if file_path.name.startswith(".") or ".git" in file_path.parts or ".ssh" in file_path.parts:
                ui.warning(f"Access denied to hidden or sensitive path: @{path_str}")
                continue

            # 2. Extension check
            if file_path.suffix.lower() not in SAFE_EXTENSIONS:
                ui.warning(f"Unsupported file type: @{path_str} (Allowed: {', '.join(SAFE_EXTENSIONS)})")
                continue

            # 3. Sensitive keywords in filename
            if any(kw in file_path.name.lower() for kw in SENSITIVE_KEYWORDS):
                ui.warning(f"Sensitive filename blocked: @{path_str}")
                continue

            # 4. Size limit
            if file_path.stat().st_size > MAX_FILE_SIZE:
                ui.warning(f"File too large: @{path_str} (Max 100KB)")
                continue

            # 5. Outside project check (basic check against CWD)
            try:
                file_path.relative_to(Path.cwd())
            except ValueError:
                ui.warning(f"Access denied: @{path_str} is outside the project directory.")
                continue

            # Read content
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    valid_context.append(f"[CONTEXT: @{path_str}]\n{content}")
            except Exception as e:
                ui.warning(f"Failed to read @{path_str}: {str(e)}")

        return cleaned_text, valid_context

router = Router()
