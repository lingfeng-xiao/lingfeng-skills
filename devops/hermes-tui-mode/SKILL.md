---
name: hermes-tui-mode
description: Hermes Agent TUI mode usage guide — switching between TUI and CLI, environment variable behavior, and feature comparison.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, tui, cli, terminal, configuration]
    related_skills: [hermes-agent]
---

# Hermes TUI Mode Usage

Hermes Agent provides two interactive interfaces:
- **CLI** (`hermes`) — classic prompt_toolkit + Rich terminal interface
- **TUI** (`hermes --tui`) — Ink-based (React for terminals) chat-app UI

## Launching

```bash
hermes          # Defaults to TUI if HERMES_TUI=1, else CLI
hermes --tui    # Force TUI mode
```

## Environment Variable Behavior

The `HERMES_TUI` environment variable controls the default mode. The logic in the entry point is:

```python
use_tui = getattr(args, "tui", False) or os.environ.get("HERMES_TUI") == "1"
```

This means:
- `HERMES_TUI=1` → bare `hermes` launches TUI
- `HERMES_TUI` unset or any value other than `"1"` → bare `hermes` launches CLI
- `hermes --tui` always forces TUI regardless of env var

**There is no `--no-tui` flag.** To temporarily use CLI when `HERMES_TUI=1` is set:

```bash
HERMES_TUI=0 hermes              # Single command
unset HERMES_TUI && hermes       # Current shell session only
```

## TUI-Exclusive Features

| Feature | Description |
|---------|-------------|
| Session picker | Graphical list to browse and resume past sessions |
| Model picker | Dropdown/list to switch LLM providers and models |
| Skills hub | Visual browser for searching and installing skills |
| Message queue | Queue multiple prompts for sequential processing |
| Virtual scroll history | Smooth scrolling through long conversations |
| Multiline composer | Proper multi-line prompt editing with buffer |
| Themed markdown | Richer code block and markdown rendering |

## When to Use Which

| Scenario | Recommendation |
|----------|---------------|
| Quick Q&A, floating assistant window | **TUI** |
| Browsing/resuming sessions or models | **TUI** |
| Installing or searching skills | **TUI** |
| Long-running build/script tasks | **CLI** |
| Heavy copy-paste of code/output | **CLI** |
| Piping input/output with shell tools | **CLI** |
| Running alongside other terminal work | **CLI** |

## Quick Setup Alias

To have both modes available without changing defaults, add shell aliases:

```bash
alias h="hermes"          # Uses default (TUI if HERMES_TUI=1)
alias hc="HERMES_TUI=0 hermes"  # Force CLI mode
```

## Troubleshooting

- If TUI fails to start with node_modules errors, the TypeScript build may be stale. The `--dev` flag runs from sources via tsx.
- TUI spawns a Python JSON-RPC gateway backend (`tui_gateway/`) over stdio. Stderr is captured to an in-memory log ring rather than printed to screen.
- If TUI deps are missing, run `npm install` in the `ui-tui` directory of the Hermes installation.
