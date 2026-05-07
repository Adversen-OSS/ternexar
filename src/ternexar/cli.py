import typer

from ternexar.confirm import handle_confirm
from ternexar.gate import handle_gate
from ternexar import __version__
from ternexar.ask import handle_ask
from ternexar.plan import handle_plan
from ternexar.preview import handle_preview
from ternexar.risk import risk_engine
from ternexar.boot import boot_sequence
from ternexar.config import CONFIG_FILE, config_manager
from ternexar.audit import audit_manager
from ternexar.runner import runner_skeleton
from ternexar.ui import ui

app = typer.Typer(
    name="tx",
    help="TERNEXAR: A premium, safety-first AI command center.",
    rich_markup_mode="rich",
    no_args_is_help=False,
)

config_app = typer.Typer(help="Manage TERNEXAR configuration.")
app.add_typer(config_app, name="config")

audit_app = typer.Typer(help="Manage and view TERNEXAR safety audit logs.")
app.add_typer(audit_app, name="audit")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    no_splash: bool = typer.Option(
        False,
        "--no-splash",
        help="Run health checks without showing the TERNEXAR banner.",
    ),
):
    """Run the standard boot sequence and health check."""
    if ctx.invoked_subcommand is None:
        boot_sequence.run(show_splash=not no_splash)


@app.command()
def ask(
    prompt: str = typer.Argument(..., help="The question or prompt for the AI."),
    model: str = typer.Option(None, "--model", "-m", help="Override default model."),
    temperature: float = typer.Option(
        None, "--temp", "-t", help="Override default temperature."
    ),
):
    """Ask TERNEXAR a question using the local AI model."""
    handle_ask(prompt, model_override=model, temperature_override=temperature)


@app.command()
def plan(
    task: str = typer.Argument(..., help="The task you want to generate a plan for."),
    model: str = typer.Option(None, "--model", "-m", help="Override default model."),
    temperature: float = typer.Option(
        None, "--temp", "-t", help="Override default temperature."
    ),
):
    """Generate a safe terminal action plan for a specific task."""
    handle_plan(task, model_override=model, temperature_override=temperature)


@app.command()
def preview(
    task: str = typer.Argument(..., help="The task you want to preview."),
    model: str = typer.Option(None, "--model", "-m", help="Override default model."),
    temperature: float = typer.Option(
        None, "--temp", "-t", help="Override default temperature."
    ),
):
    """Dry-run preview of what TERNEXAR would do for a specific task."""
    handle_preview(task, model_override=model, temperature_override=temperature)


@app.command()
def gate(
    command: str = typer.Argument(..., help="The shell command to evaluate through the safety gate.")
):
    """Evaluate a command against the execution safety gate."""
    handle_gate(command)


@app.command()
def confirm(
    command: str = typer.Argument(..., help="The shell command to simulate confirmation for.")
):
    """Simulate the confirmation protocol for a specific command."""
    handle_confirm(command)


@app.command(name="runner-check")
def runner_check(
    command: str = typer.Argument(..., help="The shell command to simulate through the runner."),
):
    """Simulate a command through the full safety pipeline without execution."""
    result = runner_skeleton.evaluate(command)
    ui.render_runner_check(result)


@app.command()
def risk(
    command: str = typer.Argument(..., help="The shell command to analyze for risk.")
):
    """Classify the risk level of a specific shell command."""
    analysis = risk_engine.analyze(command)
    ui.render_risk_report(analysis)


@app.command()
def doctor():
    """Run a deep diagnostic for config, Ollama, and model readiness."""
    boot_sequence.run(show_splash=True, deep_diagnostic=True)


@app.command()
def version():
    """Show TERNEXAR version."""
    ui.info(f"TERNEXAR v{__version__}")


@config_app.command("init")
def config_init():
    """Initialize default configuration."""
    config_manager.ensure_config()
    ui.info(f"Configuration initialized at {CONFIG_FILE}")


@config_app.command("view")
def config_view():
    """View current configuration."""
    config_data = config_manager.load()
    ui.config_view(config_data)


@config_app.command("path")
def config_path():
    """Show configuration file path."""
    ui.info(str(CONFIG_FILE))


@config_app.command("reset")
def config_reset():
    """Reset configuration to defaults."""
    config_manager.reset()
    ui.info("Configuration reset to defaults.")


@audit_app.command(name="view")
def audit_view(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of records to show.")
):
    """View recent safety audit logs."""
    records = audit_manager.get_records(limit=limit)
    ui.render_audit_log(records)


@audit_app.command(name="clear")
def audit_clear():
    """Securely clear the local audit log."""
    if typer.confirm("Are you sure you want to clear the audit log?"):
        audit_manager.clear_logs()
        ui.success("Audit log cleared successfully.")
    else:
        ui.info("Operation cancelled.")
