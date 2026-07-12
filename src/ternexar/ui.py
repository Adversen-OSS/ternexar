from typing import Optional

import toml
from rich.align import Align
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.status import Status
from rich.text import Text
from rich.table import Table
from rich.theme import Theme

PURPLE = "#8A2BE2"
CYAN = "#00FFFF"

THEME = Theme(
    {
        "info": f"bold {CYAN}",
        "warning": "bold yellow",
        "error": "bold red",
        "success": "bold green",
        "brand": f"bold {PURPLE}",
        "dim": "dim white",
    }
)


class UI:
    def __init__(self):
        self.console = Console(theme=THEME)
        self._splash_cache = None  # Cache for pre-computed splash screen

    def _build_splash(self):
        """Pre-compute and cache the gradient ASCII banner."""
        if self._splash_cache is not None:
            return self._splash_cache
        
        banner_text = """
████████╗███████╗██████╗ ███╗   ██╗███████╗██╗  ██╗ █████╗ ██████╗
╚══██╔══╝██╔════╝██╔══██╗████╗  ██║██╔════╝╚██╗██╔╝██╔══██╗██╔══██╗
   ██║   █████╗  ██████╔╝██╔██╗ ██║█████╗   ╚███╔╝ ███████║██████╔╝
   ██║   ██╔══╝  ██╔══██╗██║╚██╗██║██╔══╝   ██╔██╗ ██╔══██║██╔══██╗
   ██║   ███████╗██║  ██║██║ ╚████║███████╗██╔╝ ██╗██║  ██║██║  ██║
   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝
"""
        lines = banner_text.strip("\n").split("\n")
        cached_lines = []

        for line in lines:
            text = Text(line)
            length = len(line)

            for i in range(length):
                r1, g1, b1 = 138, 43, 226
                r2, g2, b2 = 0, 255, 255

                ratio = i / max(length - 1, 1)
                r = int(r1 + (r2 - r1) * ratio)
                g = int(g1 + (g2 - g1) * ratio)
                b = int(b1 + (b2 - b1) * ratio)

                color = f"#{r:02x}{g:02x}{b:02x}"
                text.stylize(color, i, i + 1)

            cached_lines.append(text)
        
        self._splash_cache = cached_lines
        return cached_lines

    def splash(self):
        """Render the TERNEXAR premium banner."""
        cached_lines = self._build_splash()
        
        for text in cached_lines:
            self.console.print(text)

        self.console.print(
            "[dim]local-first AI command center • Ollama-ready • v2.1[/]\n"
        )

    def render_operator_routing_feedback(self, intent: str, route: str, safety: str):
        """Render transparent routing feedback for the operator."""
        self.console.print(f"\n[brand]OPERATOR ROUTE[/]")
        grid = Table.grid(expand=True)
        grid.add_column(style="dim cyan", width=15)
        grid.add_column(style="bold white")

        grid.add_row("Intent:", intent)
        grid.add_row("Route:", route)
        grid.add_row("Safety:", f"[bold green]{safety}[/]")
        
        self.console.print(Panel(grid, border_style=CYAN, padding=(0, 1)))


    def operator_welcome(self):
        """Render the Operator Mode welcome panel."""
        self.splash()
        self.panel(
            "[bold green]LOW-only execution[/] • [bold cyan]@file read-only[/] • [bold white]safety-first[/]\n"
            "[dim]Exit: Ctrl+D or exit[/]",
            title="[brand]TERNEXAR OPERATOR[/]",
            style=CYAN
        )

    def render_operator_exit(self):
        """Render a clean exit message for the operator."""
        self.console.print(f"\n[brand]TERNEXAR[/] session closed. [dim]Stay safe.[/]\n")

    def render_execution_result(self, command: str, stdout: str, stderr: str, exit_code: int):
        """Render the results of a command execution."""
        self.console.print(f"\n[brand]EXECUTION RESULT[/]")
        
        # Command Panel
        self.console.print(Panel(
            Text(command, style="bold white"),
            title="Command",
            border_style=CYAN,
            padding=(0, 1)
        ))

        if stdout:
            self.console.print(Panel(
                Text(stdout.strip()),
                title="STDOUT",
                border_style="green",
                padding=(0, 1)
            ))

        if stderr:
            self.console.print(Panel(
                Text(stderr.strip(), style="bold red"),
                title="STDERR",
                border_style="red",
                padding=(0, 1)
            ))

        status_style = "bold green" if exit_code == 0 else "bold red"
        self.console.print(f"Exit Status: [{status_style}]EXITCODE {exit_code}[/]\n")

    def render_refusal(self, command: str, reason: str):
        """Render a high-visibility refusal message."""
        self.console.print(f"\n[bold red]EXECUTION REFUSED[/]")
        self.console.print(Panel(
            Text(command, style="bold white"),
            title="Command",
            border_style="red",
            padding=(0, 1)
        ))
        self.console.print(f"[error]Reason:[/] {reason}\n")

    def render_minimal_confirmation(self, command: str):
        """Show a minimal confirmation message before execution."""
        self.console.print(f"[info]Executing LOW-risk command:[/] [bold white]{command}[/]")

    def panel(
        self,
        content: str,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        style: str = PURPLE,
    ):
        panel = Panel(
            Align.center(Text.from_markup(content), vertical="middle"),
            title=title,
            subtitle=subtitle,
            border_style=style,
            padding=(1, 2),
        )
        self.console.print(panel)

    def warning_panel(self, message: str, title: str = "SAFETY WARNING"):
        """Render a high-visibility warning panel for risky actions."""
        panel = Panel(
            Text.from_markup(f"[bold yellow]{message}[/]"),
            title=f"[bold red]{title}[/]",
            border_style="orange_red1",
            padding=(1, 2),
        )
        self.console.print(panel)

    def ai_response(self, content: str, model: str, title: str = "TERNEXAR"):
        """Render AI generated content as Markdown in a branded panel."""
        md = Markdown(content)
        panel = Panel(
            md,
            title=f"[brand]{title}[/]",
            subtitle=f"[dim]model: {model}[/]",
            border_style=CYAN,
            padding=(1, 2),
        )
        self.console.print(panel)

    def status(self, message: str) -> Status:
        return self.console.status(f"[bold {PURPLE}]{message}[/]")

    def check_line(
        self,
        name: str,
        success: bool,
        warning: bool = False,
        skipped: bool = False,
    ):
        if success:
            symbol = "[bold green]✔[/]"
        elif warning:
            symbol = "[bold yellow]![/]"
        elif skipped:
            symbol = "[bold blue]?[/]"
        else:
            symbol = "[bold red]✘[/]"

        self.console.print(f"{symbol} {name}")

    def error(self, message: str):
        self.console.print(f"[error]ERROR:[/] {message}")

    def warning(self, message: str):
        self.console.print(f"[warning]WARNING:[/] {message}")

    def success(self, message: str):
        self.console.print(f"[success]SUCCESS:[/] {message}")

    def info(self, message: str):
        self.console.print(f"[info]{message}[/]")

    def hint(self, message: str):
        self.console.print(f"\n[dim]Hint: {message}[/]")

    def render_analysis_result(self, result):
        """Render the results of an issue analysis."""
        self.console.print(f"\n[brand]TERNEXAR ANALYZER[/]")
        
        # Detection Panel
        self.console.print(Panel(
            Text.from_markup(result.detected_issue or "No issue detected."),
            title="Detection",
            border_style=CYAN,
            padding=(0, 1)
        ))

        if result.explanation:
            self.console.print(Panel(
                Text(result.explanation),
                title="Explanation",
                border_style="dim white",
                padding=(0, 1)
            ))

        # Safety Verdict
        verdict_color = {
            "SAFE": "bold green",
            "BLOCKED": "bold red",
            "REFUSED": "bold yellow"
        }.get(result.safety_verdict, "white")
        
        self.console.print(f"Safety Verdict: [{verdict_color}]{result.safety_verdict}[/]")
        if result.reason:
            self.console.print(f"[dim]Reason: {result.reason}[/]")
        
        if result.diff:
            self.render_diff_preview(result.diff)

    def render_diff_preview(self, diff: str):
        """Render a unified diff with color highlighting."""
        self.console.print(f"\n[brand]PROPOSED PATCH[/]")
        
        diff_lines = diff.splitlines()
        styled_diff = Text()
        
        for line in diff_lines:
            if line.startswith("+"):
                styled_diff.append(line + "\n", style="green")
            elif line.startswith("-"):
                styled_diff.append(line + "\n", style="red")
            elif line.startswith("@@"):
                styled_diff.append(line + "\n", style="cyan")
            else:
                styled_diff.append(line + "\n", style="white")

        self.console.print(Panel(
            styled_diff,
            title="Unified Diff",
            border_style="dim white",
            padding=(0, 1)
        ))

    def render_patch_applied(self, result):
        """Render a success message after applying a patch."""
        self.console.print(f"\n[success]✔ Patch applied successfully.[/]")
        if result.file_path:
            self.console.print(f"Modified: [bold white]{result.file_path}[/]")
        if result.backup_path:
            self.console.print(f"Backup: [dim]{result.backup_path}[/]")
        self.console.print("\n")

    def render_patch_cancelled(self):
        """Render a cancellation message."""
        self.console.print(f"\n[info]Patch cancelled. No files were modified.[/]\n")

    def render_patch_failed(self, error: str):
        """Render a failure message for patching."""
        self.console.print(f"\n[error]FAILED:[/] {error}\n")

    def config_view(self, config_data: dict):
        self.console.print(
            Panel(toml.dumps(config_data), title="Config", border_style=CYAN)
        )

    def render_risk_report(self, analysis):
        """Render a detailed command risk analysis report."""
        self.console.print(f"\n[brand]COMMAND RISK ANALYSIS[/]")
        
        # Command Panel
        self.console.print(Panel(
            Text(analysis.command, style="bold white"),
            title="Command",
            border_style=CYAN,
            padding=(0, 1)
        ))

        # Risk Summary
        level_color = analysis.level.color
        self.console.print(f"Risk Level: [{level_color}]{analysis.level.value}[/]")
        self.console.print(f"Policy: [dim]{analysis.policy}[/]\n")

        if analysis.matches:
            table = Table(show_header=True, header_style=f"bold {PURPLE}", box=None)
            table.add_column("Pattern", style="cyan")
            table.add_column("Reason", style="white")
            table.add_column("Alternative", style="dim green")

            for match in analysis.matches:
                table.add_row(
                    match.label,
                    match.reason,
                    match.alternative or "N/A"
                )
            
            self.console.print(table)
        else:
            self.console.print("[success]No known risky patterns detected.[/]")
        
        self.console.print("\n")

    def render_gate_report(self, result):
        """Render a detailed execution gate report."""
        self.console.print(f"\n[brand]EXECUTION POLICY GATE[/]")

        # Command Panel
        self.console.print(Panel(
            Text(result.command, style="bold white"),
            title="Command",
            border_style=CYAN,
            padding=(0, 1)
        ))

        # Decision Grid
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="dim cyan")
        table.add_column("Value")

        risk_color = result.risk_level.color
        gate_color = {
            "PASS": "bold green",
            "HOLD": "bold yellow",
            "BLOCK": "bold red"
        }.get(result.gate_decision.value, "white")

        table.add_row("Risk Level", f"[{risk_color}]{result.risk_level.value}[/]")
        table.add_row("Patterns", ", ".join(result.matched_patterns))
        table.add_row("Policy Decision", f"[bold white]{result.policy.value}[/]")
        table.add_row("Gate Decision", f"[{gate_color}]{result.gate_decision.value}[/]")
        table.add_row("Reason", result.reason)
        
        self.console.print(table)

        # Future Instruction
        self.console.print(Panel(
            Text(result.future_instruction, style="italic white"),
            title="[dim]Future tx do behavior[/]",
            border_style="dim white",
            padding=(0, 1)
        ))
        self.console.print("\n")

    def render_confirmation_report(self, result):
        """Render a detailed confirmation protocol report."""
        self.console.print(f"\n[brand]CONFIRMATION PROTOCOL[/]")

        # Command Panel
        self.console.print(Panel(
            Text(result.command, style="bold white"),
            title="Command",
            border_style=CYAN,
            padding=(0, 1)
        ))

        # Policy Table
        table = Table(show_header=True, header_style=f"bold {PURPLE}", box=None, padding=(0, 2))
        table.add_column("Key", style="dim cyan")
        table.add_column("Value")

        risk_color = result.risk_level.color
        gate_color = {
            "PASS": "bold green",
            "HOLD": "bold yellow",
            "BLOCK": "bold red"
        }.get(result.gate_decision.value, "white")

        table.add_row("Risk Level", f"[{risk_color}]{result.risk_level.value}[/]")
        table.add_row("Gate Decision", f"[{gate_color}]{result.gate_decision.value}[/]")
        table.add_row("Policy Decision", f"[bold white]{result.policy.value}[/]")
        table.add_row("Confirmation Mode", f"[bold white]{result.mode}[/]")
        
        self.console.print(table)

        # Future Interaction Panel
        interaction_style = {
            "MINIMAL_CONFIRMATION": "bold green",
            "STANDARD_CONFIRMATION": "bold yellow",
            "STRONG_CONFIRMATION": "bold red",
            "REFUSED": "bold blink red"
        }.get(result.mode, "white")

        # Update wording for LOW as per v1.0 requirements
        future_behavior = result.future_behavior
        if result.risk_level.value == "LOW":
            future_behavior = "Eligible for execution with visible/auditable minimal confirmation."

        self.console.print(Panel(
            Text(future_behavior, style=interaction_style),
            title="[dim]Future tx do behavior[/]",
            border_style=interaction_style,
            padding=(0, 1)
        ))

        # Safety Recommendation
        self.console.print(f"\n[dim]Reason: {result.reason}[/]")
        if result.recommendation:
            self.console.print(f"[success]Recommendation:[/] {result.recommendation}")
        
        self.console.print("\n")

    def render_audit_log(self, records):
        """Render the audit log table."""
        self.console.print(f"\n[brand]TERNEXAR AUDIT LOG[/]")
        
        if not records:
            self.console.print("[dim]No records found.[/]\n")
            return

        table = Table(show_header=True, header_style=f"bold {PURPLE}", box=None, padding=(0, 1))
        table.add_column("Timestamp", style="dim", width=20)
        table.add_column("Action", style="cyan")
        table.add_column("Command", style="white")
        table.add_column("Risk", width=10)
        table.add_column("Verdict", width=15)

        for rec in records:
            # Color coding for risk and verdict
            risk_color = "green" if rec["risk_level"] == "LOW" else "yellow" if rec["risk_level"] == "MEDIUM" else "red"
            verdict_color = "bold green" if rec["result"] == "DRY_ELIGIBLE" else "bold yellow" if rec["result"] == "HELD" else "bold red"
            
            # Simple ISO timestamp truncation for display
            ts = rec["timestamp"].split(".")[0].replace("T", " ")

            table.add_row(
                ts,
                rec["action_type"],
                rec["command"],
                f"[{risk_color}]{rec['risk_level']}[/]",
                f"[{verdict_color}]{rec['result']}[/]"
            )

        self.console.print(table)
        self.console.print("\n")

    def render_runner_check(self, result):
        """Render the runner simulation check report."""
        self.console.print(f"\n[brand]RUNNER SIMULATION CHECK[/]")

        # Command Panel
        self.console.print(Panel(
            Text(result.command, style="bold white"),
            title="Command",
            border_style=CYAN,
            padding=(0, 1)
        ))

        # Status Table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="dim cyan")
        table.add_column("Value")

        risk_color = result.risk_level.color
        verdict_style = {
            "DRY_ELIGIBLE": "bold green",
            "HELD": "bold yellow",
            "DENIED": "bold red"
        }.get(result.verdict.value, "white")

        table.add_row("Risk Level", f"[{risk_color}]{result.risk_level.value}[/]")
        table.add_row("Gate Status", f"[bold white]{result.gate_decision.value}[/]")
        table.add_row("Confirmation", f"[bold white]{result.confirmation_mode}[/]")
        
        self.console.print(table)

        # Verdict Panel
        self.console.print(Panel(
            Align.center(Text(result.verdict.value, style=verdict_style)),
            title="[bold sky_blue1]SIMULATED RUNNER DECISION[/]",
            border_style="sky_blue1",
            padding=(1, 2)
        ))

        self.console.print(f"[dim]Reason: {result.reason}[/]")
        self.console.print("\n[dim blink]DRY RUN ONLY - NO COMMANDS EXECUTED[/]\n")

    def render_preview_report(self, task: str, actions):
        """Render the TERNEXAR v1.0 Preview report."""
        self.console.print("\n" + "=" * 80)
        self.console.print(Align.center("[bold blink red]DRY RUN ONLY - NO COMMANDS EXECUTED[/]"))
        self.console.print("=" * 80 + "\n")

        self.console.print(f"[info]TASK:[/] [bold white]{task}[/]\n")

        table = Table(show_header=True, header_style=f"bold {PURPLE}", box=None, padding=(0, 1))
        table.add_column("#", style="dim", width=3)
        table.add_column("Command", style="bold white")
        table.add_column("Risk", width=10)
        table.add_column("Policy", style="dim")
        table.add_column("Status", width=10)

        for i, action in enumerate(actions, 1):
            risk_color = action.analysis.level.color
            status_style = "bold green" if action.status == "STAGED" else "bold red"
            
            table.add_row(
                str(i),
                action.command,
                f"[{risk_color}]{action.analysis.level.value}[/]",
                action.policy,
                f"[{status_style}]{action.status}[/]"
            )

        self.console.print(table)

        # Final Summary
        staged_count = sum(1 for a in actions if a.status == "STAGED")
        blocked_count = sum(1 for a in actions if a.status == "BLOCKED")

        self.console.print("\n" + "-" * 40)
        self.console.print(f"Summary: [bold green]{staged_count} Staged[/] | [bold red]{blocked_count} Blocked[/]")
        
        if blocked_count > 0:
            self.warning("\nSome commands were BLOCKED for safety. Use 'tx risk <command>' for details.")
        
        self.console.print("-" * 40 + "\n")
        self.console.print(f"[dim]Note: Staged commands would require confirmation in a future execution module.[/]")
        self.console.print("\n")

    def render_locate_results(self, query: str, results: list):
        """Render the results of a project search."""
        self.console.print(f"\n[brand]PROJECT LOCATOR[/]")
        self.console.print(f"[dim]Query: {query}[/]\n")

        if not results:
            self.console.print("[yellow]No projects found matching that query in safe roots.[/]\n")
            return

        table = Table(show_header=True, header_style=f"bold {PURPLE}", box=None, padding=(0, 2))
        table.add_column("Project Name", style="bold white")
        table.add_column("Path", style="cyan")
        table.add_column("Match", style="dim")

        for res in results:
            table.add_row(
                res["name"],
                res["path"],
                res["match_type"]
            )

        self.console.print(table)
        self.console.print(f"\n[dim]Found {len(results)} results. Use 'tx view <path>' to inspect.[/]\n")

    def render_workspace_tree(self, path: str, tree_data: dict):
        """Render a visual tree of the workspace."""
        from rich.tree import Tree
        
        self.console.print(f"\n[brand]WORKSPACE VIEWER[/]")
        self.console.print(f"[dim]Path: {path}[/]\n")

        if "error" in tree_data:
            self.error(tree_data["error"])
            return

        def add_to_tree(rich_tree, data):
            for child in data.get("children", []):
                if child["type"] == "directory":
                    style = f"bold {PURPLE}"
                    branch = rich_tree.add(f"[bold {CYAN}]📁 {child['name']}[/]", style=style)
                    add_to_tree(branch, child)
                else:
                    rich_tree.add(f"📄 {child['name']}")

        root_tree = Tree(f"[bold white]📂 {tree_data['name']}[/]")
        add_to_tree(root_tree, tree_data)
        
        self.console.print(root_tree)
        self.console.print("\n[dim]Hidden and generated folders were skipped for safety.[/]\n")

    def render_scan_report(self, scan_data: dict):
        """Render a detailed project scan report."""
        self.console.print(f"\n[brand]WORKSPACE INTELLIGENCE[/]")
        
        if "error" in scan_data:
            self.error(scan_data["error"])
            return

        # Project Info Panel
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="dim cyan")
        table.add_column("Value")

        type_color = {
            "PYTHON": "bold blue",
            "NODE": "bold green",
            "RUST": "bold orange1",
            "GO": "bold cyan",
            "JAVA": "bold red",
            "STATIC_WEB": "bold yellow"
        }.get(scan_data["project_type"], "white")

        table.add_row("Path", scan_data["path"])
        table.add_row("Project Type", f"[{type_color}]{scan_data['project_type']}[/]")
        table.add_row("Important Files", ", ".join(scan_data["important_files"]))
        
        self.console.print(Panel(table, border_style=CYAN))

        if scan_data.get("readme_preview"):
            self.console.print(f"\n[bold white]README PREVIEW[/]")
            self.console.print(Panel(
                Text(scan_data["readme_preview"], style="dim italic"),
                border_style="dim white",
                padding=(0, 1)
            ))

        if scan_data.get("sensitive_files_skipped"):
            self.console.print(f"\n[info]✔ Sensitive files were skipped and not read.[/]")
        
        self.console.print("\n")

    def render_setup_preview(self, setup_data: dict):
        """Render a high-fidelity project setup preview report."""
        self.console.print(f"\n[brand]SETUP ASSISTANT[/]")
        
        if "error" in setup_data:
            self.error(setup_data["error"])
            return

        # Project Summary
        type_color = {
            "PYTHON": "bold blue",
            "NODE": "bold green",
            "RUST": "bold orange1",
            "GO": "bold cyan",
            "JAVA": "bold red",
            "STATIC_WEB": "bold yellow"
        }.get(setup_data["project_type"], "white")

        self.console.print(f"Project: [bold white]{setup_data['path']}[/]")
        self.console.print(f"Type: [{type_color}]{setup_data['project_type']}[/]")
        self.console.print(f"Files: [dim]{', '.join(setup_data['important_files'])}[/]\n")

        self.console.print("=" * 60)
        self.console.print(Align.center("[bold red]SETUP PREVIEW ONLY - NO COMMANDS EXECUTED[/]"))
        self.console.print("=" * 60 + "\n")

        table = Table(show_header=True, header_style=f"bold {PURPLE}", box=None, padding=(0, 1))
        table.add_column("Command", style="bold white")
        table.add_column("Risk", width=10)
        table.add_column("Gate", width=10)
        table.add_column("Status", width=20)

        for step in setup_data["steps"]:
            risk_color = {
                "LOW": "green",
                "MEDIUM": "yellow",
                "HIGH": "bold red",
                "BLOCKED": "bold red",
                "INFO": "dim cyan"
            }.get(step["risk_level"], "white")

            status_color = {
                "PREVIEW_ONLY": "bold blue",
                "SHELL_INSTRUCTION": "dim white",
                "RECOMMENDATION": "green"
            }.get(step["status"], "white")

            table.add_row(
                step["command"],
                f"[{risk_color}]{step['risk_level']}[/]",
                step["gate_decision"],
                f"[{status_color}]{step['status']}[/]"
            )

        self.console.print(table)
        self.console.print("\n[dim]Use 'tx risk <command>' to see detailed safety analysis.[/]")
        self.console.print("[dim]Use 'tx view <path>' to explore project structure safely.[/]\n")

    def render_install_preview(self, data: dict):
        """Render a deterministic installer profile preview report."""
        self.console.print(f"\n[brand]INSTALLER PROFILE PREVIEW[/]")
        
        # Tool Info
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="dim cyan")
        table.add_column("Value")

        table.add_row("Tool Requested", data["requested_tool"])
        table.add_row("Profile Name", f"[bold white]{data['profile_name']}[/]")
        table.add_row("Detected OS", data["detected_os"])
        table.add_row("Status", f"[bold white]{data['status']}[/]")
        
        self.console.print(Panel(table, border_style=CYAN))

        if data.get("global_warnings"):
            for w in data["global_warnings"]:
                self.warning(w)

        self.console.print("\n" + "=" * 60)
        self.console.print(Align.center("[bold red]INSTALL PREVIEW ONLY - NO COMMANDS EXECUTED[/]"))
        self.console.print("=" * 60 + "\n")

        if data["status"] == "AVAILABLE" and data.get("steps"):
            table = Table(show_header=True, header_style=f"bold {PURPLE}", box=None, padding=(0, 1))
            table.add_column("Command", style="bold white")
            table.add_column("Risk", width=10)
            table.add_column("Gate", width=10)
            table.add_column("Confirmation", width=25)

            for step in data["steps"]:
                risk_color = step["risk_level"].color
                gate_color = "bold green" if step["gate_decision"] == "PASS" else "bold yellow" if step["gate_decision"] == "HOLD" else "bold red"
                
                table.add_row(
                    step["command"],
                    f"[{risk_color}]{step['risk_level'].value}[/]",
                    f"[{gate_color}]{step['gate_decision']}[/]",
                    f"[dim]{step['confirmation_mode']}[/]"
                )

            self.console.print(table)

            if data.get("verification_command"):
                self.console.print(f"\n[info]Verification Command:[/] [bold white]{data['verification_command']}[/]")
        
        elif data["status"] == "NEEDS_VERIFICATION":
            self.warning_panel(
                "No trusted installer profile is available yet for this tool on your OS.\n"
                "Suggestions are withheld for safety until a deterministic profile is verified.",
                title="VERIFICATION REQUIRED"
            )
        elif data["status"] == "UNKNOWN_TOOL":
            self.error("Unknown tool. TERNEXAR does not have a profile for this request.")
        
        self.console.print('\n[dim]Note: Use tx install "<tool>" for confirmed execution of verified profiles.[/]\n')

    def render_version_check_result(self, data: dict):
        """Render the results of a version check."""
        self.console.print(f"\n[brand]VERSION CHECK[/]")
        
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="dim cyan")
        table.add_column("Value")

        status_value = data["status"].value if hasattr(data["status"], "value") else data["status"]
        status_color = {
            "INSTALLED": "bold green",
            "NOT_INSTALLED": "bold yellow",
            "NEEDS_VERIFICATION": "bold cyan",
            "UNKNOWN_TOOL": "bold red",
            "CHECK_FAILED": "bold red",
            "REFUSED": "bold red"
        }.get(status_value, "white")

        table.add_row("Tool Requested", data["requested_tool"])
        table.add_row("Normalized Tool", f"[bold white]{data['normalized_tool']}[/]")
        table.add_row("Status", f"[{status_color}]{status_value}[/]")
        
        if data.get("executable"):
            table.add_row("Executable", data["executable"])
        if data.get("command"):
            table.add_row("Check Command", f"[dim]{data['command']}[/]")
        if data.get("version_output"):
            table.add_row("Version Output", f"[bold white]{data['version_output']}[/]")
        
        self.console.print(Panel(table, border_style=CYAN))

        if data.get("notes"):
            self.console.print(f"[dim]Notes: {data['notes']}[/]")

        # Safety Disclaimer
        self.console.print("\n" + "=" * 60)
        self.console.print(Align.center("[bold red]VERSION CHECK ONLY - NO INSTALL COMMANDS EXECUTED[/]"))
        self.console.print("=" * 60 + "\n")

    def render_install_preflight_report(self, data: dict):
        """Render a comprehensive installer preflight readiness report."""
        self.console.print(f"\n[brand]INSTALLER PREFLIGHT REPORT[/]")
        
        # High-visibility disclaimer
        self.console.print("\n" + "=" * 80)
        self.console.print(Align.center("[bold red]INSTALL PREFLIGHT ONLY - NO INSTALL COMMANDS EXECUTED[/]"))
        self.console.print("=" * 80 + "\n")

        # Tool & Status Summary
        summary_table = Table(show_header=False, box=None, padding=(0, 2))
        summary_table.add_column("Key", style="dim cyan")
        summary_table.add_column("Value")

        version_status = data["version_status"].value
        v_color = "bold green" if version_status == "INSTALLED" else "bold yellow"
        
        summary_table.add_row("Tool Requested", data["requested_tool"])
        summary_table.add_row("Normalized Tool", f"[bold white]{data['normalized_tool']}[/]")
        summary_table.add_row("Current Status", f"[{v_color}]{version_status}[/]")
        
        if data["version_output"]:
            summary_table.add_row("Installed Version", f"[bold white]{data['version_output']}[/]")
        
        summary_table.add_row("Detected OS", data["os_key"])
        summary_table.add_row("Profile Status", f"[bold white]{data['profile_status'].value}[/]")
        
        self.console.print(Panel(summary_table, border_style=CYAN, title="Preflight Summary"))

        # Commands Preview
        if data["steps"]:
            self.console.print(f"\n[bold white]FUTURE INSTALLER COMMANDS (ANALYSIS ONLY)[/]")
            cmd_table = Table(show_header=True, header_style=f"bold {PURPLE}", box=None, padding=(0, 1))
            cmd_table.add_column("Command", style="bold white")
            cmd_table.add_column("Risk", width=10)
            cmd_table.add_column("Gate", width=10)
            cmd_table.add_column("Confirmation", width=25)

            for step in data["steps"]:
                risk_color = step["risk_level"].color
                gate_color = "bold green" if step["gate_decision"].value == "PASS" else "bold yellow" if step["gate_decision"].value == "HOLD" else "bold red"
                
                cmd_table.add_row(
                    step["command"],
                    f"[{risk_color}]{step['risk_level'].value}[/]",
                    f"[{gate_color}]{step['gate_decision'].value}[/]",
                    f"[dim]{step['confirmation_mode']}[/]"
                )
            self.console.print(cmd_table)
        
        # Final Verdict
        verdict = data["verdict"].value
        verdict_style = {
            "ALREADY_INSTALLED": "bold green",
            "READY_FOR_FUTURE_CONFIRMED_EXECUTION": "bold green",
            "NOT_READY_NEEDS_VERIFICATION": "bold cyan",
            "NOT_READY_UNKNOWN_TOOL": "bold red",
            "NOT_READY_UNSUPPORTED_OS": "bold red",
            "REFUSED": "bold red",
            "CHECK_FAILED": "bold red"
        }.get(verdict, "white")

        self.console.print("\n")
        self.console.print(Panel(
            Align.center(Text(verdict, style=verdict_style)),
            title="[bold sky_blue1]FINAL PREFLIGHT VERDICT[/]",
            border_style="sky_blue1",
            padding=(1, 2)
        ))

        if data["notes"]:
            self.console.print(f"[dim]Notes: {data['notes']}[/]")

        self.console.print('\n[dim]Note: Use tx install "<tool>" for confirmed execution of verified profiles.[/]\n')

    def render_workspace_list(self, roots: list):
        """Render the list of custom workspace roots."""
        from pathlib import Path
        self.console.print(f"\n[brand]WORKSPACE ROOTS[/]")
        
        if not roots:
            self.console.print("[dim]No custom workspace roots configured.[/]\n")
            return

        table = Table(show_header=True, header_style=f"bold {PURPLE}", box=None, padding=(0, 2))
        table.add_column("Root Path", style="bold white")
        table.add_column("Status", style="cyan")
        table.add_column("Safety", style="dim")

        for r in roots:
            path = Path(r)
            status = "[green]Exists[/]" if path.exists() else "[red]Missing[/]"
            table.add_row(r, status, "Safe/Config Only")

        self.console.print(table)
        self.console.print("\n[dim]These roots are used by 'tx locate' to find projects.[/]\n")

    def render_workspace_add_result(self, success: bool, message: str):
        """Render the result of adding a workspace root."""
        if success:
            self.console.print(f"\n[success]SUCCESS:[/] Added workspace root: [bold white]{message}[/]")
            self.console.print("[dim]TERNEXAR will now search this directory during 'tx locate'.[/]\n")
        else:
            self.console.print(f"\n[error]REFUSED:[/] {message}")
            self.console.print("[dim]Path was not added to TERNEXAR configuration.[/]\n")

    def render_workspace_remove_result(self, success: bool, message: str):
        """Render the result of removing a workspace root."""
        if success:
            self.console.print(f"[success]SUCCESS:[/] Removed workspace root: {message}")
        else:
            self.console.print(f"[error]ERROR:[/] {message}")

    def render_operator_locate_results(self, query: str, results: list):
        """Render integrated operator locate results with suggestions."""
        if not results:
            self.console.print(f"\n[yellow]I couldn't find any projects matching '{query}'.[/]")
            self.console.print("[dim]Try adding a workspace root: [/][bold white]tx workspace add <path>[/]")
            return

        self.console.print(f"\n[brand]LOCATOR[/] Found [bold white]{len(results)}[/] matches for '[info]{query}[/]':")
        
        for i, res in enumerate(results, 1):
            self.console.print(f"  {i}. [bold white]{res['name']}[/] [dim]({res['path']})[/]")

        if len(results) == 1:
            res = results[0]
            self.console.print(f"\n[success]Match identified.[/] What would you like to do?")
            self.console.print(f"  • [bold cyan]scan my {res['name']} project[/]")
            self.console.print(f"  • [bold cyan]show files in {res['name']}[/]")
        else:
            self.console.print(f"\n[info]Multiple matches found.[/] Please be more specific or use [bold white]tx view <path>[/].")
        self.console.print("")

    def render_install_execution_header(self, tool_name: str):
        """Render a high-visibility header for confirmed installer execution."""
        self.console.print("\n" + "=" * 80)
        self.console.print(Align.center("[bold yellow]CONFIRMED INSTALLER EXECUTION[/]"))
        self.console.print(Align.center(f"[bold white]Tool: {tool_name}[/]"))
        self.console.print("=" * 80)
        self.console.print(f"\n[info]ONLY VERIFIED INSTALLER PROFILE COMMANDS MAY RUN.[/]")
        self.console.print(f"[info]NO ARBITRARY COMMANDS WILL BE EXECUTED.[/]\n")

    def render_install_step(self, current: int, total: int, command: str):
        """Render the status of a single installation step."""
        self.console.print(f"\n[brand][STEP {current}/{total}][/] Executing: [bold white]{command}[/]")

    def render_install_result(self, status, tool_name: str, message: str):
        """Render the final result of an installation attempt."""
        color = "bold green" if status.value == "SUCCESS" else "bold red"
        if status.value == "CANCELLED":
            color = "bold yellow"
            
        self.console.print("\n" + "=" * 80)
        self.console.print(Align.center(f"[{color}]INSTALLATION {status.value}[/]"))
        self.console.print(Align.center(f"[bold white]Tool: {tool_name}[/]"))
        self.console.print("=" * 80)
        self.console.print(f"\n{message}\n")

    def render_recovery_report(self, report):
        """Render the TERNEXAR v2.1 Safe Recovery Report."""
        self.console.print(f"\n[brand]SAFE RECOVERY ENGINE[/]")
        
        # High-visibility header
        self.console.print("\n" + "=" * 80)
        self.console.print(Align.center("[bold red]RECOVERY PREVIEW ONLY - NO REPAIR APPLIED[/]"))
        self.console.print("=" * 80 + "\n")

        # Classification Table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="dim cyan")
        table.add_column("Value")

        domain_color = {
            "APT_PACKAGE_MANAGER": "bold blue",
            "NPM_NODE": "bold green",
            "PYTHON_PIP": "bold blue",
            "GIT": "bold orange1",
            "PERMISSION": "bold red",
            "PORT_IN_USE": "bold yellow",
            "FILESYSTEM_PATH": "cyan",
            "BLOCKED_DESTRUCTIVE_REQUEST": "bold blink red"
        }.get(report.profile.domain.value, "white")

        table.add_row("Failure Domain", f"[{domain_color}]{report.profile.domain.value}[/]")
        table.add_row("Recovery Profile", f"[bold white]{report.profile.id}[/]")
        
        if report.source_file:
            table.add_row("Input Source", f"[dim]{report.source_file}[/]")
        
        status_color = "bold green" if report.status == "PREVIEW_ONLY" else "bold red"
        table.add_row("Safety Status", f"[{status_color}]{report.status}[/]")
        
        self.console.print(Panel(table, border_style=CYAN, title="Diagnosis Summary"))

        # Root Cause
        self.console.print(f"\n[bold white]ROOT CAUSE EXPLANATION[/]")
        self.console.print(Panel(
            Text(report.profile.explanation),
            border_style="dim white",
            padding=(0, 1)
        ))

        # Repair Plan
        self.console.print(f"\n[bold white]SAFE REPAIR PLAN (PREVIEW)[/]")
        plan_text = ""
        for i, step in enumerate(report.profile.repair_plan, 1):
            plan_text += f"{i}. {step}\n"
        
        self.console.print(Panel(
            Text(plan_text.strip()),
            border_style=CYAN,
            padding=(0, 1)
        ))

        # Diff Preview if available
        if report.profile.diff_template:
            self.render_diff_preview(report.profile.diff_template)

        # Safety Reminder
        self.console.print(f"\n[dim yellow]Next Steps:[/] Manual repair is required. Future versions may add confirmed repair apply.")
        self.console.print(f"[dim]Audit Record: {report.safety_decision}[/]\n")


ui = UI()
