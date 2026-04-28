from typing import Optional

import toml
from rich.align import Align
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.status import Status
from rich.text import Text
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
            "[dim]local-first AI command center • Ollama-ready • v0.2[/]\n"
        )

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

    def ai_response(self, content: str, model: str):
        """Render AI generated content as Markdown in a branded panel."""
        md = Markdown(content)
        panel = Panel(
            md,
            title=f"[brand]TERNEXAR[/]",
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

    def info(self, message: str):
        self.console.print(f"[info]{message}[/]")

    def hint(self, message: str):
        self.console.print(f"\n[dim]Hint: {message}[/]")

    def config_view(self, config_data: dict):
        self.console.print(
            Panel(toml.dumps(config_data), title="Config", border_style=CYAN)
        )


ui = UI()
