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

    def splash(self):
        """Render the TERNEXAR premium banner."""
        banner_text = """
████████╗███████╗██████╗ ███╗   ██╗███████╗██╗  ██╗ █████╗ ██████╗
╚══██╔══╝██╔════╝██╔══██╗████╗  ██║██╔════╝╚██╗██╔╝██╔══██╗██╔══██╗
   ██║   █████╗  ██████╔╝██╔██╗ ██║█████╗   ╚███╔╝ ███████║██████╔╝
   ██║   ██╔══╝  ██╔══██╗██║╚██╗██║██╔══╝   ██╔██╗ ██╔══██║██╔══██╗
   ██║   ███████╗██║  ██║██║ ╚████║███████╗██╔╝ ██╗██║  ██║██║  ██║
   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝
"""
        lines = banner_text.strip("\n").split("\n")

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

            self.console.print(text)

        self.console.print(
            "[dim]local-first AI command center • Ollama-ready • v1.1[/]\n"
        )

    def operator_welcome(self):
        """Render the Operator Mode welcome panel."""
        self.splash()
        self.panel(
            "[bold green]LOW-only execution[/] • [bold cyan]@file read-only[/] • [bold white]safety-first[/]",
            title="[brand]TERNEXAR OPERATOR[/]",
            style=CYAN
        )
        self.console.print("\n")

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


ui = UI()
