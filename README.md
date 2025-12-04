# Jexida Agent CLI

A terminal agent CLI that connects to a remote MCP server via SSH, uses Ollama + phi3 for LLM reasoning, and implements a tool protocol that allows the model to propose shell commands with user confirmation.

## Features

- **Interactive REPL**: Clean terminal interface with command history
- **LLM Integration**: Uses Ollama + phi3 on remote server for natural language understanding
- **Tool Protocol**: Model can propose shell commands with JSON-based protocol
- **User Confirmation**: All shell commands require explicit user approval
- **Rich UI**: Beautiful terminal UI using Rich library with panels and colors
- **Routines**: Predefined command sequences stored in configuration
- **SSH Integration**: Seamless remote command execution

## Installation

### Prerequisites

- Python 3.10 or higher
- SSH client installed and configured (OpenSSH on Windows 10+)
- Access to remote server with Ollama installed

### Install from Source

1. Clone or navigate to this repository:
```bash
cd C:\Dev\JexidaMCP
```

2. Install in development mode:
```bash
pip install -e .
```

This will install the `jexida` command-line tool.

## Configuration

### Initial Setup

On first run, Jexida will use default configuration:
- Host: `192.168.1.224`
- User: `jexida`
- Model: `phi3`

### Custom Configuration

Create a configuration file at:
- **Windows**: `%APPDATA%\.jexida\config.toml`
- **Unix/Linux/Mac**: `~/.jexida/config.toml`

Example `config.toml`:

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

## Usage

### Start Jexida

```bash
jexida
```

Or if not installed as a script:

```bash
python -m jexida_cli.main
```

### Commands

#### Meta Commands (not sent to LLM)

- `/exit` or `/quit` - Exit the application
- `/help` - Show available commands
- `/clear` - Clear screen and redraw header
- `/shell` - Open interactive SSH shell
- `/cmd <command>` - Run a single remote command
- `/routines` - List available routines
- `/run <routine>` - Execute a named routine

#### Chat Mode

Any input that doesn't start with `/` is treated as a chat message to the LLM agent.

The agent can:
- Answer questions naturally
- Propose shell commands (with your confirmation)
- Use available routines when appropriate

### Example Session

```
JEXIDA> why is the sky blue?

[PROMPT panel]
why is the sky blue?

[AGENT RESPONSE panel]
The sky is blue because of Rayleigh scattering...

[STATUS panel]
host  : 192.168.1.224
user  : jexida
model : phi3
```

```
JEXIDA> check if docker is running

[PROMPT panel]
check if docker is running

[PLAN panel]
Command: systemctl is-active docker
Reason: Check if Docker service is active

Run this command on jexida@192.168.1.224? [y/N] y

[COMMAND OUTPUT panel]
active

[STATUS panel]
host  : 192.168.1.224
user  : jexida
model : phi3
code  : 0
```

## How It Works

1. **User Input**: You type a message or command
2. **LLM Processing**: Message is sent to Ollama on remote server via SSH
3. **Response Parsing**: Response is parsed for JSON tool protocol
4. **Command Proposal**: If model proposes a command, you're asked for confirmation
5. **Execution**: Approved commands run on remote server via SSH
6. **History**: Results are added to conversation history for context

## Tool Protocol

The LLM uses a JSON-based protocol to communicate:

**Answer type:**
```json
{
  "type": "answer",
  "text": "Your explanation here..."
}
```

**Shell command type:**
```json
{
  "type": "shell",
  "command": "sudo apt update",
  "reason": "Update package lists as requested"
}
```

If JSON parsing fails, the response is treated as plain text.

## Project Structure

```
jexida_cli/
├── __init__.py      # Package initialization
├── main.py          # Entry point, REPL loop
├── config.py        # Configuration management
├── ssh_client.py    # SSH command execution
├── agent.py         # LLM integration, tool protocol
└── ui.py            # Rich terminal UI components
```

## Development

### Running Tests

(Test suite to be added)

### Code Style

The project uses Black for formatting (line length: 100).

### Dependencies

- `rich` - Terminal UI and formatting
- `typer` - CLI framework
- `toml` - Configuration file parsing

## Troubleshooting

### SSH Connection Issues

- Ensure SSH is configured and you can connect manually: `ssh jexida@192.168.1.224`
- Check that SSH keys are set up or password authentication is enabled
- Verify the host and user in your config file

### Ollama Errors

- Ensure Ollama is installed and running on the remote server
- Verify the model name (default: `phi3`) exists: `ssh jexida@192.168.1.224 "ollama list"`
- Check that the model is accessible: `ssh jexida@192.168.1.224 "ollama run phi3 'test'"`

### JSON Parsing Issues

If the model doesn't return valid JSON, the response will be treated as plain text. This is expected behavior for natural language responses that don't require commands.

## License

(To be determined)

## Contributing

(Contributions welcome - to be expanded)

