# TERNEXAR

**Safe, local-first terminal intelligence.**

TERNEXAR is a command-line interface designed to bridge the gap between local LLMs and terminal automation. It focuses on a high-integrity workflow: understanding a task, planning the steps, and assessing the risk—all before a single character is typed into your shell.

## Safety & Philosophy

TERNEXAR operates on a strict **Ask → Plan → Risk** pipeline. We believe terminal automation should be transparent and verifiable. 

**Note:** TERNEXAR currently analyzes and plans but **does not execute** commands. Execution features are slated for future releases and will always require explicit user confirmation.

## Features

*   **v0.5: Preview Mode** – A high-fidelity dry-run environment. Simulate the full execution lifecycle (understanding, planning, and risk assessment) without running any shell commands.
*   **v0.4: Risk Engine** – A deterministic, rule-based system that classifies command risk levels (LOW, MEDIUM, HIGH, BLOCKED) using local safety heuristics.
*   **v0.3: Plan Mode** – Generates structured, multi-step terminal action plans using local Ollama models.
*   **v0.2: Ask Mode** – One-shot technical questions and command lookups via `tx ask`.
*   **v0.1: The Foundation** – Environment diagnostics (`tx doctor`), local configuration management, and a high-fidelity terminal UI.

## Installation

Ensure you have [Ollama](https://ollama.ai/) installed and running locally.

```bash
# Clone the repository and install in editable mode
pip install -e .
```

## Usage

### Ask
Query local models for quick answers or command syntax.
```bash
tx ask "How do I list all files larger than 100MB in the current directory?"
```

### Plan
Transform a natural language goal into a structured sequence of commands.
```bash
tx plan "Set up a local postgres container with a persistent volume"
```

### Preview
Dry-run a task to see exactly which commands would be staged, their risk levels, and which ones would be blocked.
```bash
tx preview "Install docker and run hello-world"
```

### Risk
Analyze the generated plan using the deterministic risk engine. This identifies potentially destructive commands (like `rm -rf` or `mkfs`) before they are staged.
```bash
tx risk "rm -rf /"
```

### Diagnostics
```bash
tx doctor         # Validate local environment and Ollama connectivity
tx config view    # Inspect active configuration
tx config path    # Locate configuration files
```

## Project Status

TERNEXAR is currently in **v0.6 (Beta)**. 
- All LLM interactions are handled locally via Ollama.
- The Risk Engine is entirely local and rule-based; it does not use LLMs to assess safety.
- **No commands are executed by the tool.**

## Future Direction
The next phase of development focuses on the **Execute** module, which will provide a secure "apply" workflow for approved plans, featuring dry-runs and granular confirmation prompts.

---
*Built for the local-first era.*
secure "apply" workflow for approved plans, featuring dry-runs and granular confirmation prompts.

---
*Built for the local-first era.*
l-first era.*
