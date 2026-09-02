import re
import shlex
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set


class RiskLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCKED = "BLOCKED"

    @property
    def color(self) -> str:
        return {
            RiskLevel.LOW: "green",
            RiskLevel.MEDIUM: "yellow",
            RiskLevel.HIGH: "bold red",
            RiskLevel.BLOCKED: "bold blink red",
        }[self]

    @property
    def policy(self) -> str:
        return {
            RiskLevel.LOW: "AUTO (Minimal confirmation)",
            RiskLevel.MEDIUM: "CONFIRM (Standard confirmation)",
            RiskLevel.HIGH: "WARNING (Multi-step confirmation)",
            RiskLevel.BLOCKED: "DENY (Execution strictly prohibited)",
        }[self]


@dataclass
class RiskRule:
    pattern: str
    level: RiskLevel
    reason: str
    label: str
    alternative: Optional[str] = None


@dataclass
class RiskAnalysis:
    command: str
    level: RiskLevel
    matches: List[RiskRule]

    @property
    def policy(self) -> str:
        return self.level.policy


@dataclass(frozen=True)
class SupportedMediumInstall:
    binary: str
    subcommand: str
    args: List[str]


SUPPORTED_MEDIUM_INSTALL_COMMANDS: Dict[str, Set[str]] = {
    "pip": {"install"},
    "pip3": {"install"},
    "npm": {"install", "i"},
    "yarn": {"install", "add"},
    "cargo": {"install"},
}

PACKAGE_INSTALL_RULE = RiskRule(
    pattern=r"\b(pip|pip3|npm|yarn|cargo)\b",
    level=RiskLevel.MEDIUM,
    reason="Installing packages can execute arbitrary code from a registry.",
    label="Package Installation",
    alternative="Verify the package name and source before installing.",
)


def parse_supported_medium_install(command: str) -> Optional[SupportedMediumInstall]:
    """Parse and validate whether a command matches the supported MEDIUM package install matrix.

    Supported matrix:
      - pip install <args...>
      - pip3 install <args...>
      - npm install <args...>
      - npm i <args...>
      - yarn install [args...]
      - yarn add <args...>
      - cargo install <args...>

    Returns a SupportedMediumInstall object if valid, None otherwise.
    Fails closed on malformed input or empty commands.
    """
    try:
        args = shlex.split(command)
    except Exception:
        return None

    if not args:
        return None

    binary = args[0].lower()

    # Reject nested interpreters explicitly
    nested_interpreters = {
        "python",
        "python3",
        "sh",
        "bash",
        "zsh",
        "dash",
        "ksh",
        "csh",
        "tcsh",
        "perl",
        "ruby",
        "node",
    }
    if binary in nested_interpreters:
        return None

    allowed_subcommands = SUPPORTED_MEDIUM_INSTALL_COMMANDS.get(binary)
    if allowed_subcommands is None:
        return None

    if len(args) < 2:
        return None

    subcommand = args[1].lower()
    if subcommand not in allowed_subcommands:
        return None

    return SupportedMediumInstall(
        binary=binary,
        subcommand=subcommand,
        args=args[2:],
    )


class RiskEngine:
    def __init__(self):
        self.rules: List[RiskRule] = [
            # BLOCKED
            RiskRule(
                r"rm\s+-rf\s+/",
                RiskLevel.BLOCKED,
                "Attempting to delete the root directory.",
                "Root Deletion",
                "Never run this. Use surgical deletes if necessary.",
            ),
            RiskRule(
                r"rm\s+-rf\s+~",
                RiskLevel.BLOCKED,
                "Attempting to delete the home directory.",
                "Home Deletion",
                "Delete specific folders inside home instead.",
            ),
            RiskRule(
                r"\b(mkfs|format)\b",
                RiskLevel.BLOCKED,
                "Disk formatting or filesystem creation detected.",
                "Disk Wipe",
                "Use safer partition managers if you must modify disks.",
            ),
            RiskRule(
                r"cat\s+\.env\b",
                RiskLevel.BLOCKED,
                "Directly printing environment secrets.",
                "Secret Exposure",
                "Use 'grep' for specific non-sensitive keys if needed.",
            ),
            RiskRule(
                r"\b(printenv|env)\b",
                RiskLevel.BLOCKED,
                "Listing all environment variables can expose secrets.",
                "Environment Dump",
                "Check specific variables instead (e.g., 'echo $VAR').",
            ),
            # HIGH
            RiskRule(
                r"\bsudo\b",
                RiskLevel.HIGH,
                "Command requires administrative privileges.",
                "Superuser Access",
                "Avoid sudo unless absolutely necessary for system-wide changes.",
            ),
            RiskRule(
                r"(curl|wget)\s+.*\|\s*(sh|bash|zsh)",
                RiskLevel.HIGH,
                "Piping remote scripts directly to a shell is dangerous.",
                "Remote Script Execution",
                "Download the script first, inspect it, then run it manually.",
            ),
            RiskRule(
                r"chmod\s+777",
                RiskLevel.HIGH,
                "Granting full read/write/execute to everyone is a security risk.",
                "Insecure Permissions",
                "Use more restrictive permissions (e.g., 755 or 644).",
            ),
            RiskRule(
                r"\b(ufw|iptables|firewall-cmd)\b",
                RiskLevel.HIGH,
                "Modifying firewall rules can expose the system.",
                "Firewall Change",
                "Consult security guidelines before opening ports.",
            ),
            # MEDIUM (Non-package installation rules)
            RiskRule(
                r"rm\s+-rf\s+",
                RiskLevel.MEDIUM,
                "Recursive force-delete can be destructive if path is wrong.",
                "Recursive Delete",
                "Double-check the path or use 'rm -ri' for safety.",
            ),
            RiskRule(
                r"git\s+clean\s+-fd",
                RiskLevel.MEDIUM,
                "Force-deleting untracked files in git.",
                "Git Clean",
                "Use 'git clean -n' first to see what will be deleted.",
            ),
            # General Risky Keywords (useful for prompt scanning)
            RiskRule(
                r"\bdelete\b",
                RiskLevel.MEDIUM,
                "Explicit 'delete' action requested.",
                "Delete Keyword",
                "Ensure you specify the target precisely.",
            ),
            RiskRule(
                r"\b(wipe|format)\b",
                RiskLevel.HIGH,
                "Destructive 'wipe' or 'format' action requested.",
                "Destructive Keyword",
                "Verify the target device or directory.",
            ),
            RiskRule(
                r"\bsecrets?\b",
                RiskLevel.HIGH,
                "Accessing or manipulating secrets detected.",
                "Secrets Keyword",
                "Never share or print secrets in plain text.",
            ),
        ]

    def analyze(self, command: str) -> RiskAnalysis:
        found_matches = []
        highest_level = RiskLevel.LOW

        # 1. Check structural package installation policy
        if parse_supported_medium_install(command) is not None:
            found_matches.append(PACKAGE_INSTALL_RULE)
            highest_level = RiskLevel.MEDIUM

        # 2. Check remaining regex rules
        for rule in self.rules:
            if re.search(rule.pattern, command, re.IGNORECASE):
                found_matches.append(rule)
                # Elevate risk level if this rule is higher than current
                current_levels = list(RiskLevel)
                if current_levels.index(rule.level) > current_levels.index(
                    highest_level
                ):
                    highest_level = rule.level

        return RiskAnalysis(command=command, level=highest_level, matches=found_matches)


risk_engine = RiskEngine()
