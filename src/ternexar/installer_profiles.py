import platform
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Dict

from ternexar.gate import gate_engine
from ternexar.confirm import confirm_engine
from ternexar.ui import ui

class ProfileStatus(Enum):
    AVAILABLE = "AVAILABLE"
    UNSUPPORTED_OS = "UNSUPPORTED_OS"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"
    UNKNOWN_TOOL = "UNKNOWN_TOOL"
    BLOCKED = "BLOCKED"

@dataclass
class PlatformProfile:
    commands: List[str]
    verification: str
    package_manager: str
    warnings: List[str]

@dataclass
class InstallerProfile:
    id: str
    name: str
    aliases: List[str]
    status: ProfileStatus
    platforms: Dict[str, PlatformProfile]
    global_warnings: List[str]

class ProfileRegistry:
    def __init__(self):
        self.profiles: List[InstallerProfile] = [
            InstallerProfile(
                id="python3",
                name="Python 3",
                aliases=["python", "python 3", "python3"],
                status=ProfileStatus.AVAILABLE,
                global_warnings=["Ensure you have an active internet connection."],
                platforms={
                    "linux-apt": PlatformProfile(
                        commands=[
                            "sudo apt update",
                            "sudo apt install python3 python3-pip"
                        ],
                        verification="python3 --version",
                        package_manager="apt",
                        warnings=["Requires sudo privileges."]
                    )
                }
            ),
            InstallerProfile(
                id="nodejs",
                name="Node.js",
                aliases=["node", "nodejs", "npm"],
                status=ProfileStatus.AVAILABLE,
                global_warnings=["Includes npm package manager."],
                platforms={
                    "linux-apt": PlatformProfile(
                        commands=[
                            "sudo apt update",
                            "sudo apt install nodejs npm"
                        ],
                        verification="node --version && npm --version",
                        package_manager="apt",
                        warnings=["Requires sudo privileges."]
                    )
                }
            ),
            InstallerProfile(
                id="codex",
                name="OpenAI Codex",
                aliases=["codex", "openai codex"],
                status=ProfileStatus.NEEDS_VERIFICATION,
                platforms={},
                global_warnings=["No trusted installer profile available yet."]
            ),
            InstallerProfile(
                id="claude-code",
                name="Claude Code",
                aliases=["claude", "claude code", "anthropic claude code"],
                status=ProfileStatus.NEEDS_VERIFICATION,
                platforms={},
                global_warnings=["No trusted installer profile available yet."]
            ),
            InstallerProfile(
                id="docker",
                name="Docker",
                aliases=["docker"],
                status=ProfileStatus.NEEDS_VERIFICATION,
                platforms={},
                global_warnings=["Docker installation varies by distro and requires verification."]
            )
        ]

    def get_profile(self, tool_name: str) -> Optional[InstallerProfile]:
        query = tool_name.strip().lower()
        for profile in self.profiles:
            if query == profile.id or query in profile.aliases:
                return profile
        return None

    def detect_os_key(self) -> str:
        """Detect OS and package manager key safely without subprocess."""
        sys_name = platform.system().lower()
        
        if sys_name == "linux":
            try:
                os_release = platform.freedesktop_os_release()
                id_like = os_release.get("ID_LIKE", "").lower()
                id_main = os_release.get("ID", "").lower()
                
                if "debian" in id_like or "ubuntu" in id_like or "debian" == id_main or "ubuntu" == id_main:
                    return "linux-apt"
            except (AttributeError, OSError):
                # Fallback: manually read /etc/os-release if platform method fails
                try:
                    with open("/etc/os-release", "r") as f:
                        content = f.read(1024) # Small read
                        if "debian" in content.lower() or "ubuntu" in content.lower():
                            return "linux-apt"
                except Exception:
                    pass
            return "linux-generic"
            
        elif sys_name == "darwin":
            return "macos"
        elif sys_name == "windows":
            return "windows"
            
        return "unknown"

profile_registry = ProfileRegistry()

def handle_install_preview(tool: str):
    """Handler for installer profile preview logic."""
    profile = profile_registry.get_profile(tool)
    os_key = profile_registry.detect_os_key()
    
    data = {
        "requested_tool": tool,
        "profile_name": profile.name if profile else "Unknown",
        "detected_os": os_key,
        "status": profile.status.value if profile else ProfileStatus.UNKNOWN_TOOL.value,
        "global_warnings": profile.global_warnings if profile else [],
        "steps": [],
        "verification_command": None
    }

    if profile and profile.status == ProfileStatus.AVAILABLE:
        platform_profile = profile.platforms.get(os_key)
        if platform_profile:
            data["verification_command"] = platform_profile.verification
            data["global_warnings"].extend(platform_profile.warnings)
            
            for cmd in platform_profile.commands:
                gate_result = gate_engine.evaluate(cmd)
                confirm_result = confirm_engine.evaluate(cmd)
                
                data["steps"].append({
                    "command": cmd,
                    "risk_level": gate_result.risk_level,
                    "gate_decision": gate_result.gate_decision.value,
                    "confirmation_mode": confirm_result.mode
                })
        else:
            data["status"] = ProfileStatus.NEEDS_VERIFICATION.value

    ui.render_install_preview(data)
