import typer

from ternexar import __version__
from ternexar.ui import ui

app = typer.Typer(
    name="tx",
    help="TERNEXAR: A premium, safety-first AI command center.",
    rich_markup_mode="rich",
    no_args_is_help=False,
)

config_app = typer.Typer(help="Manage TERNEXAR configuration.")
app.add_typer(config_app, name="config")

workspace_app = typer.Typer(help="Manage custom workspace roots.")
app.add_typer(workspace_app, name="workspace")

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
        # Lazy import to avoid loading boot_sequence on every CLI invocation
        from ternexar.boot import boot_sequence
        boot_sequence.run(show_splash=not no_splash)


@app.command()
def operator():
    """Enter the interactive TERNEXAR Operator Composer."""
    # Lazy imports for operator command
    from ternexar.composer import handle_operator
    handle_operator()


@app.command()
def locate(
    name: str = typer.Argument(..., help="The project name or fragment to search for.")
):
    """Search safe user folders for matching project directories."""
    # Lazy imports for locate command
    from ternexar.locator import locator
    results = locator.locate(name)
    ui.render_locate_results(name, results)


@app.command()
def view(
    path: str = typer.Argument(..., help="The path to the project to view.")
):
    """Show a read-only, safe project folder tree."""
    # Lazy imports for view command
    from ternexar.workspace import workspace_manager
    tree_data = workspace_manager.get_tree(path)
    ui.render_workspace_tree(path, tree_data)


@app.command()
def scan(
    path: str = typer.Argument(..., help="The path to the project to scan.")
):
    """Read safe metadata and detect project type and dependencies."""
    # Lazy imports for scan command
    from ternexar.workspace import workspace_manager
    scan_data = workspace_manager.scan(path)
    ui.render_scan_report(scan_data)


@app.command(name="setup-preview")
def setup_preview(
    path: str = typer.Argument(".", help="The path to the project to preview setup for.")
):
    """Analyze a project folder and generate a safe setup preview."""
    # Lazy imports for setup-preview command
    from ternexar.setup_assistant import setup_assistant
    setup_data = setup_assistant.get_preview(path)
    ui.render_setup_preview(setup_data)


@app.command(name="install-preview")
def install_preview(
    tool: str = typer.Argument(..., help="The tool name to preview installation for (e.g., 'python3').")
):
    """Preview deterministic installation steps for a supported tool."""
    # Lazy imports for install-preview command
    from ternexar.installer_profiles import handle_install_preview
    handle_install_preview(tool)


@app.command(name="version-check")
def version_check(
    tool: str = typer.Argument(..., help="The tool name to check version for (e.g., 'python3').")
):
    """Safely check if a tool is installed and report its version."""
    # Lazy imports for version-check command
    from ternexar.version_check import handle_version_check
    handle_version_check(tool)


@app.command(name="install-preflight")
def install_preflight(
    tool: str = typer.Argument(..., help="The tool name to run a preflight readiness check for (e.g., 'python3').")
):
    """Run a safe installer readiness check before future real execution."""
    # Lazy imports for install-preflight command
    from ternexar.install_preflight import handle_install_preflight
    handle_install_preflight(tool)


@app.command(name="install")
def install(
    tool: str = typer.Argument(..., help="The tool name to install (e.g., 'python3').")
):
    """Execute a verified installer profile after preflight and strong confirmation."""
    # Lazy imports for install command
    from ternexar.installer_execute import installer_executor
    installer_executor.execute_install(tool)


@workspace_app.command("add")
def workspace_add(
    path: str = typer.Argument(..., help="The path to add as a custom workspace root.")
):
    """Add a custom workspace root to search for projects."""
    # Lazy imports for workspace add command
    from ternexar.workspace_config import workspace_config
    success, message = workspace_config.add_root(path)
    ui.render_workspace_add_result(success, message)


@workspace_app.command("list")
def workspace_list():
    """Show configured custom workspace roots."""
    # Lazy imports for workspace list command
    from ternexar.workspace_config import workspace_config
    roots = workspace_config.get_roots()
    ui.render_workspace_list(roots)


@workspace_app.command("remove")
def workspace_remove(
    path: str = typer.Argument(..., help="The path to remove from workspace roots.")
):
    """Remove a custom workspace root from configuration."""
    # Lazy imports for workspace remove command
    from ternexar.workspace_config import workspace_config
    success, message = workspace_config.remove_root(path)
    ui.render_workspace_remove_result(success, message)


@workspace_app.command("clear")
def workspace_clear():
    """Clear all custom workspace roots."""
    # Lazy imports for workspace clear command
    from ternexar.workspace_config import workspace_config
    if typer.confirm("Clear all workspace roots?", default=False):
        workspace_config.clear_roots()
        ui.success("Workspace roots cleared.")
    else:
        ui.info("Operation cancelled.")


@app.command()
def analyze(
    task: str = typer.Argument(..., help="The task or error message to analyze and fix safely.")
):
    """Analyze a broken Python app or error and suggest safe patches."""
    # Lazy imports for analyze command
    from ternexar.analyze import handle_analyze
    handle_analyze(task)


@app.command()
def recover(
    error: str = typer.Argument(..., help="The error text or log fragment to diagnose.")
):
    """Diagnose a system or project failure and show a safe recovery preview."""
    # Lazy imports for recover command
    from ternexar.recovery import handle_recover
    handle_recover(error)


@app.command(name="recover-file")
def recover_file(
    path: str = typer.Argument(..., help="The path to a safe log or error file to diagnose.")
):
    """Read a safe text file and diagnose its content for recovery."""
    # Lazy imports for recover-file command
    from ternexar.recovery import handle_recover_file
    handle_recover_file(path)


@app.command()
def ask(
    prompt: str = typer.Argument(..., help="The question or prompt for the AI."),
    model: str = typer.Option(None, "--model", "-m", help="Override default model."),
    temperature: float = typer.Option(
        None, "--temp", "-t", help="Override default temperature."
    ),
):
    """Ask TERNEXAR a question using the local AI model."""
    # Lazy imports for ask command
    from ternexar.ask import handle_ask
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
    # Lazy imports for plan command
    from ternexar.plan import handle_plan
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
    # Lazy imports for preview command
    from ternexar.preview import handle_preview
    handle_preview(task, model_override=model, temperature_override=temperature)


@app.command()
def do(
    command: str = typer.Argument(..., help="The shell command to execute safely (LOW risk only).")
):
    """Execute a safe, allowlisted shell command after safety validation."""
    # Lazy imports for do command
    from ternexar.do import handle_do
    handle_do(command)


@app.command()
def gate(
    command: str = typer.Argument(..., help="The shell command to evaluate through the safety gate.")
):
    """Evaluate a command against the execution safety gate."""
    # Lazy imports for gate command
    from ternexar.gate import handle_gate
    handle_gate(command)


@app.command()
def confirm(
    command: str = typer.Argument(..., help="The shell command to simulate confirmation for.")
):
    """Simulate the confirmation protocol for a specific command."""
    # Lazy imports for confirm command
    from ternexar.confirm import handle_confirm
    handle_confirm(command)


@app.command(name="runner-check")
def runner_check(
    command: str = typer.Argument(..., help="The shell command to simulate through the runner."),
):
    """Simulate a command through the full safety pipeline without execution."""
    # Lazy imports for runner-check command
    from ternexar.runner import runner_skeleton
    result = runner_skeleton.evaluate(command)
    ui.render_runner_check(result)


@app.command()
def risk(
    command: str = typer.Argument(..., help="The shell command to analyze for risk.")
):
    """Classify the risk level of a specific shell command."""
    # Lazy imports for risk command
    from ternexar.risk import risk_engine
    analysis = risk_engine.analyze(command)
    ui.render_risk_report(analysis)


@app.command()
def doctor():
    """Run a deep diagnostic for config, Ollama, and model readiness."""
    # Lazy imports for doctor command
    from ternexar.boot import boot_sequence
    boot_sequence.run(show_splash=True, deep_diagnostic=True)


@app.command()
def version():
    """Show TERNEXAR version."""
    ui.info(f"TERNEXAR v{__version__}")


@config_app.command("init")
def config_init():
    """Initialize default configuration."""
    # Lazy imports for config init command
    from ternexar.config import CONFIG_FILE, config_manager
    config_manager.ensure_config()
    ui.info(f"Configuration initialized at {CONFIG_FILE}")


@config_app.command("view")
def config_view():
    """View current configuration."""
    # Lazy imports for config view command
    from ternexar.config import config_manager
    config_data = config_manager.load()
    ui.config_view(config_data)


@config_app.command("path")
def config_path():
    """Show configuration file path."""
    # Lazy imports for config path command
    from ternexar.config import CONFIG_FILE
    ui.info(str(CONFIG_FILE))


@config_app.command("reset")
def config_reset():
    """Reset configuration to defaults."""
    # Lazy imports for config reset command
    from ternexar.config import config_manager
    config_manager.reset()
    ui.info("Configuration reset to defaults.")


@audit_app.command(name="view")
def audit_view(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of records to show.")
):
    """View recent safety audit logs."""
    # Lazy imports for audit view command
    from ternexar.audit import audit_manager
    records = audit_manager.get_records(limit=limit)
    ui.render_audit_log(records)


@audit_app.command(name="clear")
def audit_clear():
    """Securely clear the local audit log."""
    # Lazy imports for audit clear command
    from ternexar.audit import audit_manager
    if typer.confirm("Are you sure you want to clear the audit log?"):
        audit_manager.clear_logs()
        ui.success("Audit log cleared successfully.")
    else:
        ui.info("Operation cancelled.")
