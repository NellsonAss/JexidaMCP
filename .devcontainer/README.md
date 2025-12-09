# Dev Container Setup

This project includes a Dev Container configuration for working in a Linux environment, which resolves terminal output capture issues that occur in native PowerShell.

## Prerequisites

- Docker Desktop installed and running
- VS Code with the "Dev Containers" extension installed

## Getting Started

1. **Open in Dev Container:**
   - Open VS Code in this directory
   - Press `F1` (or `Ctrl+Shift+P` on Windows/Linux)
   - Type "Dev Containers: Reopen in Container"
   - Select it and wait for the container to build

2. **The container will automatically:**
   - Install Python 3.11
   - Install project dependencies (`pip install -e .`)
   - Install server dependencies (`pip install -r mcp_server_files/requirements.txt`)
   - Set up Python linting and formatting

## Benefits

- **Terminal Output Works**: Commands executed in the container will show proper output
- **Consistent Environment**: Same Linux environment as your remote server
- **No PowerShell Issues**: Avoids Windows PowerShell output capture problems
- **SSH Still Works**: You can still SSH to your remote server from within the container

## Using SSH from Dev Container

SSH should work the same way from within the container. Make sure:
- Your SSH keys are available (they'll be mounted from your host)
- You can access the remote server from the container

## Alternative: WSL

If you prefer WSL instead of Dev Containers:

1. Install WSL2 and Ubuntu from Microsoft Store
2. Open the project in WSL: `code .` from WSL terminal
3. Install dependencies: `pip install -e .`

WSL will also resolve the terminal output capture issues.

