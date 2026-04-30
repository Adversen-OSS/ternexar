from typing import List, Optional
from dataclasses import dataclass
from ternexar.ollama_client import ollama_client
from ternexar.risk import risk_engine, RiskLevel, RiskAnalysis
from ternexar.config import config_manager
from ternexar.ui import ui

@dataclass
class PreviewAction:
    command: str
    analysis: RiskAnalysis
    policy: str
    status: str  # "STAGED" or "BLOCKED"

class PreviewManager:
    def __init__(self):
        self.system_prompt = (
            "You are TERNEXAR, a terminal automation safety expert. "
            "Your goal is to propose a sequence of shell commands to fulfill a user task. "
            "STRICT RULES:\n"
            "1. Output ONLY a numbered list of commands (e.g., 1. mkdir test).\n"
            "2. No explanations, no markdown, no chat.\n"
            "3. No destructive commands (like rm -rf /) for dangerous tasks.\n"
            "4. If the task is inherently high-risk or malicious, output: 'BLOCKED: [Reason]'.\n"
            "5. Keep it compact."
        )

    def generate_commands(self, task: str, model: str, temperature: float) -> List[str]:
        prompt = f"Task: {task}\n\nPropose a numbered list of commands to achieve this."
        response = ollama_client.generate(
            model=model,
            prompt=f"{self.system_prompt}\n\n{prompt}",
            options={"temperature": temperature}
        )
        
        commands = []
        for line in response.splitlines():
            line = line.strip()
            # Basic parsing of numbered lists (e.g., "1. command")
            if line and (line[0].isdigit() or line.startswith("- ")):
                # Strip the number/bullet
                cmd = line.split(".", 1)[-1].split("- ", 1)[-1].strip()
                if cmd:
                    commands.append(cmd)
            elif line.startswith("BLOCKED:"):
                commands.append(line)
        
        return commands

    def analyze_preview(self, task: str, commands: List[str]) -> List[PreviewAction]:
        actions = []
        for cmd in commands:
            if cmd.startswith("BLOCKED:"):
                # Special case for LLM-refused tasks
                actions.append(PreviewAction(
                    command=cmd,
                    analysis=RiskAnalysis(command=cmd, level=RiskLevel.BLOCKED, matches=[]),
                    policy="DENY",
                    status="BLOCKED"
                ))
                continue

            analysis = risk_engine.analyze(cmd)
            
            # Policy Mapping
            if analysis.level == RiskLevel.LOW:
                policy = "WOULD_RUN_IN_FUTURE_WITH_MINIMAL_CONFIRMATION"
                status = "STAGED"
            elif analysis.level == RiskLevel.MEDIUM:
                policy = "WOULD_REQUIRE_CONFIRMATION"
                status = "STAGED"
            elif analysis.level == RiskLevel.HIGH:
                policy = "WOULD_REQUIRE_STRONG_CONFIRMATION"
                status = "STAGED"
            else:  # BLOCKED
                policy = "WOULD_NOT_RUN"
                status = "BLOCKED"
            
            actions.append(PreviewAction(
                command=cmd,
                analysis=analysis,
                policy=policy,
                status=status
            ))
        return actions

    def run(self, task: str, model_override: Optional[str] = None, temperature_override: Optional[float] = None):
        config = config_manager.load()
        model = model_override or config["model"]["default"]
        temp = temperature_override or config["model"]["temperature"]

        with ui.status(f"Generating preview for: {task}..."):
            raw_commands = self.generate_commands(task, model, temp)
            preview_actions = self.analyze_preview(task, raw_commands)
        
        ui.render_preview_report(task, preview_actions)

preview_manager = PreviewManager()

def handle_preview(task: str, model_override: Optional[str] = None, temperature_override: Optional[float] = None):
    preview_manager.run(task, model_override, temperature_override)
