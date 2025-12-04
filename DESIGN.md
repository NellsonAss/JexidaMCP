# Jexida Agent CLI - Design Document

## Overview

Jexida is a local command-line application that connects to a remote MCP server via SSH, uses Ollama + phi3 for LLM reasoning, and implements a tool protocol that allows the model to propose shell commands with user confirmation.

## Architecture

### Components

1. **main.py** - Entry point, REPL loop, command routing
2. **config.py** - Configuration management (host, user, model, routines)
3. **ssh_client.py** - SSH abstraction for command execution
4. **agent.py** - LLM integration, prompt building, tool protocol parsing
5. **ui.py** - Rich terminal UI components (panels, styling)

### Data Flow: Single Chat + Optional Shell Turn

```
User Input
    ↓
main.py (REPL loop)
    ↓
    ├─→ Meta command (/exit, /help, etc.) → Execute locally
    └─→ Normal text → agent.py
                        ↓
                    Build prompt with:
                    - System message (role + tool contract)
                    - Conversation history (last N turns)
                    - User message
                        ↓
                    ssh_client.py → Execute: `ollama run phi3` via SSH
                        ↓
                    Raw text response
                        ↓
                    agent.py → Parse JSON tool protocol
                        ↓
                    ┌─────────────────┬─────────────────┐
                    │                 │                 │
            type: "answer"      type: "shell"      JSON parse fails
                    │                 │                 │
                    ↓                 ↓                 ↓
            Display in        Show command +      Treat as plain
            RESPONSE panel    reason in PLAN      answer, display
                              panel, ask for      in RESPONSE panel
                              confirmation
                                      │
                                      ↓
                              User confirms?
                                      │
                              ┌───────┴───────┐
                              │               │
                            Yes              No
                              │               │
                              ↓               ↓
                    ssh_client.py      Note as "not
                    Execute command    executed", continue
                    on remote
                              │
                              ↓
                    Capture stdout/stderr
                    + exit code
                              │
                              ↓
                    Display in COMMAND
                    OUTPUT panel
                              │
                              ↓
                    Add tool result to
                    conversation history
                              │
                              ↓
                    Return to REPL loop
```

## Tool Protocol

### JSON Schema

The LLM can return two types of responses:

**1. Answer (plain text response):**
```json
{
  "type": "answer",
  "text": "The sky is blue because of Rayleigh scattering..."
}
```

**2. Shell command request:**
```json
{
  "type": "shell",
  "command": "sudo apt update && sudo apt upgrade -y",
  "reason": "Update the system packages as you requested."
}
```

### Fallback Behavior

- If JSON parsing fails, treat the entire response as a plain text answer
- This allows the model to respond naturally when it doesn't need to run commands

### System Prompt Template

The system prompt sent to phi3 includes:

1. **Role definition**: "You are a terminal agent assistant..."
2. **Tool contract**: Explanation of the JSON schema and when to use each type
3. **Context**: Current host, user, available routines
4. **Conversation history**: Last N turns (user messages, agent responses, tool results)

## Conversation History

### In-Memory Storage

- Store as a list of message dictionaries
- Each message has:
  - `role`: "user", "assistant", or "tool"
  - `content`: The message text
  - `timestamp`: Optional, for debugging

### Context Window Management

- Keep last N turns (default: 10)
- When limit exceeded, keep:
  - Most recent system prompt
  - Last N/2 user messages
  - Last N/2 assistant responses
  - All tool results from those turns

### Tool Result Format

When a command is executed, add to history as:
```python
{
    "role": "tool",
    "content": f"Command: {command}\nExit code: {exit_code}\nOutput:\n{stdout}\n{stderr}"
}
```

## SSH Client Design

### Choice: subprocess over paramiko

**Decision**: Use `subprocess` to call local `ssh` command instead of paramiko.

**Rationale**:
- Simpler for v1 (no additional dependency)
- Works well on Windows with OpenSSH client
- Easier to handle interactive shell (`/shell` command)
- User already has SSH working
- Can switch to paramiko later if needed for advanced features

### Methods

1. **`execute_command(command: str) -> tuple[str, str, int]`**
   - Returns: (stdout, stderr, exit_code)
   - Executes: `ssh user@host "command"`

2. **`execute_ollama(prompt: str) -> str`**
   - Executes: `ssh user@host "echo 'prompt' | ollama run model"`
   - Returns raw text response

3. **`open_interactive_shell() -> None`**
   - Spawns: `ssh user@host`
   - Blocks until user exits

## Configuration

### File Format: TOML

Location: `~/.jexida/config.toml` (or `%USERPROFILE%\.jexida\config.toml` on Windows)

```toml
[connection]
host = "192.168.1.224"
user = "jexida"

[model]
name = "phi3"

[routines]
update_system = { description = "Update and upgrade packages", cmd = "sudo apt update && sudo apt upgrade -y" }
docker_list = { description = "List running containers", cmd = "docker ps" }
restart_ollama = { description = "Restart Ollama service", cmd = "sudo systemctl restart ollama" }
test_container = { description = "Run a small Ubuntu container", cmd = "docker run --rm ubuntu:22.04 bash -lc 'echo Hello from inside a container && uname -a'" }
```

### Defaults

If config file doesn't exist, use:
- host: "192.168.1.224"
- user: "jexida"
- model: "phi3"
- routines: empty dict

## UI Design

### Color Scheme

- **Borders**: Dim colors (gray/cyan)
- **Headers/Titles**: Bright but not neon (cyan/blue)
- **Body text**: Normal terminal colors
- **Status**: Green for success, red for errors, yellow for warnings

### Panel Types

1. **PROMPT** - User's input
2. **AGENT RESPONSE** - LLM answer text
3. **PLAN** - Proposed shell command with reason
4. **COMMAND OUTPUT** - stdout/stderr from executed command
5. **STATUS** - Host, user, model, exit code
6. **REMOTE COMMAND** - For `/cmd` and `/run` commands

### Layout

- Use `rich.Panel` for each section
- Add spacing between panels
- Keep headers minimal but informative
- Support scrolling (rich handles this automatically)

## Command Reference

### Meta Commands (not sent to LLM)

- `/exit` - Quit the application
- `/help` - Show available commands
- `/shell` - Open interactive SSH shell
- `/cmd <command>` - Run a single remote command
- `/routines` - List available routines
- `/run <routine>` - Execute a named routine
- `/clear` - Clear screen and redraw header

### Normal Text

Any input that doesn't start with `/` is treated as a chat message to the LLM agent.

## Error Handling

1. **SSH connection failures**: Show clear error message, suggest checking connection
2. **JSON parse errors**: Fall back to treating response as plain text
3. **Command execution failures**: Show exit code and stderr clearly
4. **Config file errors**: Use defaults, warn user
5. **Ollama errors**: Show error output, suggest checking remote server

## Future Enhancements (Post-v1)

- Persistent conversation history (save to file)
- Multiple model support
- Streaming responses from Ollama
- More sophisticated tool types (file operations, etc.)
- Command templates with variables
- History search/navigation
- Configurable context window size
- Better Windows terminal integration

