from typing import Optional

from ternexar.config import config_manager
from ternexar.health import health_checker
from ternexar.ollama_client import OllamaError, ollama_client
from ternexar.ui import ui

def handle_ask(
    prompt: str, 
    model_override: Optional[str] = None, 
    temperature_override: Optional[float] = None
):
    """
    Orchestrates the 'ask' flow: 
    Validation -> Health Check -> Inference -> UI Rendering
    """
    # 1. Validation
    if not prompt or not prompt.strip():
        ui.error("Empty prompt. Please provide a question.")
        ui.hint("Example: [cyan]tx ask \"How does a transformer work?\"[/]")
        return

    # 2. Config Loading
    default_model = config_manager.get("model", "default", "gemma4:latest")
    default_temp = config_manager.get("model", "temperature", 0.7)
    
    model = model_override or default_model
    temp = temperature_override if temperature_override is not None else default_temp

    # 3. Silent Health Checks
    # We check service first, then model
    service_res = health_checker.check_ollama_service()
    if not service_res.success:
        ui.error(service_res.message)
        if service_res.fix_command:
            ui.hint(f"Try running: [cyan]{service_res.fix_command}[/]")
        return

    model_res = health_checker.check_model(model)
    if not model_res.success:
        ui.error(model_res.message)
        if model_res.fix_command:
            ui.hint(f"Try running: [cyan]{model_res.fix_command}[/]")
        return

    # 4. Inference with UI Spinner
    ui.info(f"TERNEXAR ASK • [dim]model: {model}[/]")
    
    try:
        with ui.status(f"Thinking with {model}...") as status:
            response_text = ollama_client.generate(
                model=model,
                prompt=prompt,
                options={"temperature": temp}
            )
        
        # 5. Render Response
        ui.ai_response(response_text, model)
        
    except OllamaError as e:
        ui.error(e.message)
        if e.fix_command:
            ui.hint(f"Fix: [cyan]{e.fix_command}[/]")
    except Exception as e:
        ui.error(f"An unexpected error occurred: {str(e)}")
