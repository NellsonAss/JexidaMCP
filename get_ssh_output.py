#!/usr/bin/env python3
# Note: This script requires python3 (not python) on most Linux systems
"""
Helper script to execute SSH commands and capture output to JSON.

This script uses the codebase's SSHClient to execute commands on remote servers
and writes structured JSON output that can be read by other tools.

ALWAYS writes a JSON output file, even on errors.

Usage:
    python get_ssh_output.py <host> <user> <command> [output_file]

Examples:
    # Simple commands work fine
    python3 get_ssh_output.py 192.168.1.224 jexida "ls -la /opt/jexida-mcp" output.json
    
    # Use stdin to avoid shell interpretation issues
    echo "echo Hello" | python3 get_ssh_output.py 192.168.1.224 jexida - output.json
    
    # For commands with special characters, use stdin or proper quoting
    echo "echo Hello" | python3 get_ssh_output.py 192.168.1.224 jexida - output.json

Note: Use python3 (not python) on Linux systems.
      For commands with special characters, use stdin (pass - as command).
"""
import sys
import json
import traceback
from pathlib import Path

# Add current directory to path to import jexida_cli
sys.path.insert(0, str(Path(__file__).parent))

try:
    from jexida_cli.ssh_client import SSHClient
except ImportError as e:
    # If import fails, we'll handle it in the main function
    SSHClient = None
    IMPORT_ERROR = str(e)


def write_result_file(output_file: Path, result: dict) -> None:
    """Write result dictionary to JSON file."""
    try:
        # Ensure parent directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    except Exception as e:
        # Last resort: try writing to current directory
        fallback_file = Path("ssh_result_fallback.json")
        try:
            with open(fallback_file, "w", encoding="utf-8") as f:
                json.dump({
                    **result,
                    "error": f"Failed to write to {output_file}: {str(e)}",
                    "fallback_file": str(fallback_file)
                }, f, indent=2, ensure_ascii=False)
            print(f"ERROR: Could not write to {output_file}, wrote to {fallback_file} instead", file=sys.stderr)
        except:
            # If even fallback fails, print to stderr
            print(f"CRITICAL: Could not write result file. Result: {json.dumps(result, indent=2)}", file=sys.stderr)


def main():
    """Execute SSH command and write results to JSON file."""
    # Parse arguments
    # Support reading command from stdin if '-' is passed as command argument
    if len(sys.argv) < 4:
        error_result = {
            "host": "",
            "user": "",
            "command": "",
            "success": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": "Usage: python get_ssh_output.py <host> <user> <command> [output_file]\n"
                      "       python get_ssh_output.py <host> <user> - [output_file]  (read command from stdin)",
            "error": "Invalid arguments",
            "traceback": None
        }
        output_file = Path("ssh_result.json")
        write_result_file(output_file, error_result)
        script_name = Path(__file__).name
        print(f"Usage: python3 {script_name} <host> <user> <command> [output_file]")
        print(f"       python3 {script_name} <host> <user> - [output_file]  (read command from stdin)")
        print(f"\nExamples:")
        print(f'  python3 {script_name} 192.168.1.224 jexida "ls -la /opt" result.json')
        print(f'  echo "echo Hello" | python3 {script_name} 192.168.1.224 jexida - result.json')
        print(f"\nNote: Use python3 (not python) on Linux systems")
        print(f"      For commands with ! characters, avoid them or use single quotes")
        print(f"Error result written to: {output_file.absolute()}")
        sys.exit(1)

    host = sys.argv[1]
    user = sys.argv[2]
    command_arg = sys.argv[3]
    output_file_str = sys.argv[4] if len(sys.argv) > 4 else "ssh_result.json"
    output_file = Path(output_file_str).resolve()
    
    # Read command from stdin if '-' is passed
    if command_arg == "-":
        command = sys.stdin.read().strip()
        if not command:
            error_result = {
                "host": host,
                "user": user,
                "command": "",
                "success": False,
                "exit_code": 1,
                "stdout": "",
                "stderr": "No command provided via stdin",
                "error": "Empty command from stdin",
                "traceback": None
            }
            write_result_file(output_file, error_result)
            print("Error: No command provided via stdin", file=sys.stderr)
            sys.exit(1)
    else:
        command = command_arg

    # Initialize result structure with defaults
    result = {
        "host": host,
        "user": user,
        "command": command,
        "success": False,
        "exit_code": -1,
        "stdout": "",
        "stderr": "",
        "error": None,
        "traceback": None
    }

    try:
        # Check if SSHClient is available
        if SSHClient is None:
            result["error"] = f"Failed to import SSHClient: {IMPORT_ERROR}"
            result["stderr"] = result["error"]
            write_result_file(output_file, result)
            print(f"Import error: {result['error']}", file=sys.stderr)
            print(f"Error result written to: {output_file.absolute()}")
            sys.exit(1)

        # Execute command using SSHClient
        client = SSHClient(host=host, user=user)
        stdout, stderr, exit_code = client.execute_command(command)

        # Update result with command output
        result["exit_code"] = exit_code
        result["stdout"] = stdout
        result["stderr"] = stderr
        result["success"] = exit_code == 0

        # Write JSON output
        write_result_file(output_file, result)

        # Print summary to stdout (for manual runs)
        print(f"Command executed: {command}")
        print(f"Exit code: {exit_code}")
        print(f"Output written to: {output_file.absolute()}")
        if stdout:
            preview = stdout[:500] + ("..." if len(stdout) > 500 else "")
            print(f"\nStdout ({len(stdout)} chars):\n{preview}")
        if stderr:
            preview = stderr[:500] + ("..." if len(stderr) > 500 else "")
            print(f"\nStderr ({len(stderr)} chars):\n{preview}")

        sys.exit(0 if result["success"] else 1)

    except Exception as e:
        # Capture exception details
        error_msg = str(e)
        tb_str = traceback.format_exc()

        result["error"] = error_msg
        result["traceback"] = tb_str
        result["stderr"] = f"{error_msg}\n\n{tb_str}"

        # Always write error result
        write_result_file(output_file, result)

        print(f"Error: {error_msg}", file=sys.stderr)
        print(f"Error details written to: {output_file.absolute()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
