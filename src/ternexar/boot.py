from ternexar.ui import ui
from ternexar.config import config_manager
from ternexar.health import health_checker, StatusResult
from typing import List

class BootSequence:
    def run(self, show_splash: bool = True, deep_diagnostic: bool = False):
        if show_splash and config_manager.get("ui", "show_splash", True):
            ui.splash()

        results: List[StatusResult] = []
        
        with ui.status("Initializing TERNEXAR...") as status:
            # 1. Config Check
            status.update("Validating Configuration...")
            config_manager.ensure_config()
            config_data = config_manager.load()
            results.append(StatusResult("Configuration", True, "Config loaded successfully"))

            # 2. Ollama Binary Check
            status.update("Searching for Ollama...")
            binary_res = health_checker.check_ollama_binary()
            results.append(binary_res)

            if binary_res.success:
                # 3. Ollama Service Check
                status.update("Verifying Ollama Service...")
                service_res = health_checker.check_ollama_service()
                results.append(service_res)

                if service_res.success:
                    # 4. Model Check
                    default_model = config_data.get("model", {}).get("default", "llama3")
                    status.update(f"Verifying Model: {default_model}...")
                    model_res = health_checker.check_model(default_model)
                    results.append(model_res)
                else:
                    results.append(StatusResult("Model Check", False, "Skipped - Service unreachable", skipped=True))
            else:
                 results.append(StatusResult("Service Check", False, "Skipped - Binary missing", skipped=True))
                 results.append(StatusResult("Model Check", False, "Skipped - Binary missing", skipped=True))

        # Render results
        for res in results:
            if deep_diagnostic or not res.success:
                ui.check_line(f"{res.name}: {res.message}", res.success, res.warning, getattr(res, 'skipped', False))
            else:
                ui.check_line(res.name, res.success)

        # Final Status Panel
        all_success = all(r.success for r in results if not getattr(r, 'skipped', False))
        if all_success:
            ui.panel(f"[bold green]SYSTEM READY[/]\nTERNEXAR v0.2 is active and connected.", title="READY", style="green")
            ui.hint("type [bold cyan]tx --help[/] to explore")
        else:
            # Find the first failure to show fix command
            failure = next((r for r in results if not r.success and not getattr(r, 'skipped', False)), None)
            fix_msg = ""
            if failure and failure.fix_command:
                fix_msg = f"\n\n[bold white]FIX:[/] [cyan]{failure.fix_command}[/]"
            
            ui.panel(f"[bold red]SYSTEM BLOCKED[/]\n{failure.message if failure else 'One or more checks failed.'}{fix_msg}", title="BLOCKED", style="red")

boot_sequence = BootSequence()
