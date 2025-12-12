# SSH Command Execution Pattern

## Overview

**Note:** In devcontainers and Linux environments, terminal output capture works directly. You can use SSH commands normally and see output directly. The `get_ssh_output.py` helper script is still useful for structured JSON output, but not required for basic terminal capture.

For Windows PowerShell environments, SSH commands should be executed using the `get_ssh_output.py` helper script, which writes structured JSON output that can be read and parsed.

## Standard Pattern

### In Containers/Linux (Recommended)

**Direct SSH commands work fine - output is captured automatically:**

```bash
ssh jexida@192.168.1.224 "echo 'Hello from remote server'"
```

The terminal tool captures stdout, stderr, and exit codes directly.

### In Windows PowerShell (Workaround)

**Use this pattern when terminal capture doesn't work:**

1. **Execute command via helper script:**
   ```bash
   python3 get_ssh_output.py <host> <user> <command> [output_file]
   ```

2. **Read the generated JSON file** to get structured output

3. **Parse and reason** based on the JSON structure

## Usage Examples

### Simple Commands
```bash
python3 get_ssh_output.py 192.168.1.224 jexida "ls -la /opt/jexida-mcp" result.json
```

### Commands with Special Characters (Use Stdin)
```bash
echo "echo 'Hello!'" | python3 get_ssh_output.py 192.168.1.224 jexida - result.json
```

### Commands from Scripts
```bash
command="ls -la /opt"
python3 get_ssh_output.py 192.168.1.224 jexida "$command" result.json
```

## JSON Output Structure

The script ALWAYS writes a JSON file with this structure:

```json
{
  "host": "192.168.1.224",
  "user": "jexida",
  "command": "echo Hello from remote server",
  "success": true,
  "exit_code": 0,
  "stdout": "Hello from remote server\n",
  "stderr": "",
  "error": null,
  "traceback": null
}
```

### Fields
- `host`: Remote host address
- `user`: SSH username
- `command`: Command that was executed
- `success`: Boolean indicating if command succeeded (exit_code == 0)
- `exit_code`: Command exit code
- `stdout`: Standard output from command
- `stderr`: Standard error from command
- `error`: Error message if script had an exception (null if no error)
- `traceback`: Full traceback if script had an exception (null if no error)

## Important Notes

### For Direct SSH (Containers/Linux)
- SSH commands work normally - output is captured automatically
- Use standard SSH syntax: `ssh user@host "command"`
- Exit codes, stdout, and stderr are all captured

### For JSON Wrapper Script (Windows PowerShell)
1. **Use `python3` not `python`** on Linux systems
2. **For commands with special characters** (especially `!`), use stdin approach:
   ```bash
   echo "command" | python3 get_ssh_output.py host user - output.json
   ```
3. **The script ALWAYS writes a JSON file**, even on errors
4. **Default output file** is `ssh_result.json` if not specified
5. **The script creates parent directories** automatically for output paths

## Implementation Details

- Uses `jexida_cli.ssh_client.SSHClient` for execution
- Commands are base64-encoded to avoid shell interpretation issues
- Remote execution uses: `echo <base64> | base64 -d | sh`
- All errors are captured and written to JSON

## When NOT to Use This Pattern

- Interactive commands that require user input
- Commands that need real-time output streaming
- Commands that require TTY attachment

For these cases, ask the user to run the command manually and paste the results.






