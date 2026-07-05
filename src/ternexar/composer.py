import sys
from prompt_toolkit.application import Application
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.formatted_text import HTML

from ternexar.router import router, Intent
from ternexar.do import handle_do
from ternexar.ask import handle_ask
from ternexar.plan import handle_plan
from ternexar.preview import handle_preview
from ternexar.locator import locator
from ternexar.setup_assistant import setup_assistant
from ternexar.workspace import workspace_manager
from ternexar.analyze import handle_analyze
from ternexar.recovery import handle_recover
from ternexar.installer_profiles import handle_install_preview
from ternexar.version_check import handle_version_check
from ternexar.install_preflight import handle_install_preflight
from ternexar.installer_execute import installer_executor
from prompt_toolkit.layout.processors import Processor, Transformation
from prompt_toolkit.layout.utils import explode_text_fragments

from ternexar.ui import ui

OPERATOR_STYLE = Style.from_dict({
    "composer-bar": "bg:#2b2b2b #ffffff",
    "prompt": "bg:#2b2b2b #00FFFF bold",
    "placeholder": "bg:#2b2b2b #666666 italic",
})

class PlaceholderProcessor(Processor):
    """Custom processor to display placeholder text when the buffer is empty."""
    def __init__(self, placeholder_text: str):
        self.placeholder_text = placeholder_text

    def apply_transformation(self, transformation_input):
        if not transformation_input.document.text:
            return Transformation(explode_text_fragments([("class:placeholder", self.placeholder_text)]))
        return Transformation(transformation_input.fragments)

def _handle_named_project(text: str, intent_label: str):
    """Helper to resolve a target project and return its path if possible."""
    target = router.extract_target(text)
    if not target or target == ".":
        return "."

    results = locator.locate(target)
    if not results:
        ui.warning(f"No projects found matching '{target}'.")
        ui.hint("Try adding a workspace root: [bold white]tx workspace add <path>[/]")
        return None
    
    if len(results) > 1:
        ui.render_operator_locate_results(target, results)
        return None
        
    res = results[0]
    ui.info(f"Target identified: [bold white]{res['name']}[/] [dim]({res['path']})[/]")
    return res["path"]

def route_operator_input(text: str):
    """Main routing logic for operator input."""
    if not text.strip():
        return

    if text.strip().lower() in ["exit", "quit"]:
        ui.info("Exiting Operator Mode...")
        sys.exit(0)

    # 1. Resolve context (@file)
    prompt_text, context_blobs = router.resolve_context(text)
    
    # Combine text with context if available
    if context_blobs:
        full_prompt = f"{prompt_text}\n\n" + "\n\n".join(context_blobs)
    else:
        full_prompt = prompt_text

    # 2. Classify intent
    intent = router.classify_intent(text)

    # 3. Route to handler
    try:
        if intent == Intent.DO:
            ui.render_operator_routing_feedback("DO", f"tx do {text}", "LOW-only execution")
            handle_do(text)
        elif intent == Intent.ASK:
            ui.render_operator_routing_feedback("ASK", "AI Assistant", "Consulting local model")
            handle_ask(full_prompt)
        elif intent == Intent.PLAN:
            ui.render_operator_routing_feedback("PLAN", "Task Planner", "Generating terminal strategy")
            handle_plan(full_prompt)
        elif intent == Intent.PREVIEW:
            ui.render_operator_routing_feedback("PREVIEW", "Action Preview", "Dry-run only")
            handle_preview(full_prompt)
        elif intent == Intent.LOCATE:
            query = router.extract_target(text) or text
            ui.render_operator_routing_feedback("LOCATE", f"tx locate {query}", "Searching safe roots")
            results = locator.locate(query)
            ui.render_operator_locate_results(query, results)
        elif intent == Intent.SETUP:
            path = _handle_named_project(text, "SETUP")
            if path:
                ui.render_operator_routing_feedback("SETUP_PREVIEW", f"tx setup-preview {path}", "Preview only")
                setup_data = setup_assistant.get_preview(path)
                ui.render_setup_preview(setup_data)
        elif intent == Intent.SCAN:
            path = _handle_named_project(text, "SCAN")
            if path:
                ui.render_operator_routing_feedback("SCAN", f"tx scan {path}", "Workspace intelligence")
                scan_data = workspace_manager.scan(path)
                ui.render_scan_report(scan_data)
        elif intent == Intent.VIEW:
            path = _handle_named_project(text, "VIEW")
            if path:
                ui.render_operator_routing_feedback("VIEW", f"tx view {path}", "Read-only tree")
                tree_data = workspace_manager.get_tree(path)
                ui.render_workspace_tree(path, tree_data)
        elif intent == Intent.ANALYZE:
            ui.render_operator_routing_feedback("ANALYZE", f"tx analyze \"{text}\"", "Safe fix mode")
            handle_analyze(text)
        elif intent == Intent.RECOVER:
            ui.render_operator_routing_feedback("RECOVER", f"tx recover \"{text}\"", "Diagnosis preview only")
            handle_recover(text)
        elif intent == Intent.VERSION_CHECK:
            tool = router.extract_version_check_tool(text) or "unknown"
            ui.render_operator_routing_feedback("VERSION_CHECK", f"tx version-check {tool}", "Version check only")
            handle_version_check(tool)
        elif intent == Intent.INSTALL_PREFLIGHT:
            tool = router.extract_preflight_tool(text) or "unknown"
            ui.render_operator_routing_feedback("INSTALL_PREFLIGHT", f"tx install-preflight {tool}", "Readiness check only")
            handle_install_preflight(tool)
        elif intent == Intent.INSTALL_REQUEST:
            tool = router.extract_tool_name(text) or "unknown"
            ui.render_operator_routing_feedback("INSTALL_REQUEST", f"tx install {tool}", "Confirmed execution pipeline")
            installer_executor.execute_install(tool)
        elif intent == Intent.REFUSE:
            ui.render_refusal(text, "Dangerous command or blocked pattern detected.")
        else:
            ui.info("Unknown input. Try a question, task, or safe command.")
            ui.hint("Examples: 'setup this project', 'scan my ternexar project', 'fix import error'")
    except SystemExit:
        # Typer/SysExit might be raised by handlers; we want to stay in the loop
        pass
    except Exception as e:
        ui.error(f"Routing error: {str(e)}")

def handle_operator():
    """Starts the interactive TERNEXAR Operator session with a modern, taller composer UI."""
    ui.operator_welcome()
    
    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        text = event.app.current_buffer.text
        event.app.exit(result=text)

    @kb.add("c-c")
    def _(event):
        event.app.current_buffer.text = ""

    @kb.add("c-d")
    def _(event):
        event.app.exit(exception=EOFError)

    while True:
        try:
            # Create a 3-row tall, vertically centered composer block
            text_area = TextArea(
                prompt="> ",
                multiline=False,
                style="class:composer-bar",
                input_processors=[PlaceholderProcessor("Type your message or @path/to/file")],
            )
            
            # Use HSplit to add padding above and below the input line
            # All elements share the composer-bar style for a unified dark gray block
            composer_layout = HSplit([
                Window(height=1, char=" ", style="class:composer-bar"),
                text_area,
                Window(height=1, char=" ", style="class:composer-bar"),
            ])
            
            app = Application(
                layout=Layout(composer_layout),
                style=OPERATOR_STYLE,
                key_bindings=kb,
                full_screen=False,
            )
            
            with patch_stdout():
                user_input = app.run()
                
            if user_input:
                route_operator_input(user_input)
                
        except KeyboardInterrupt:
            # Ctrl+C clears the line via key binding, but we catch it here too
            continue
        except EOFError:
            # Ctrl+D exits
            ui.info("\nExiting Operator Mode...")
            break
        except Exception as e:
            ui.error(f"Session error: {str(e)}")
            break

    ui.render_operator_exit()
