#!/bin/bash
# JexidaMCP Server startup script

set -e

# Change to script directory
cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Load environment variables if .env exists
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Default values
PORT=${MCP_SERVER_PORT:-8080}
HOST=${MCP_SERVER_HOST:-0.0.0.0}
LOG_LEVEL=${MCP_LOG_LEVEL:-info}

echo "Starting JexidaMCP Server..."
echo "  Host: $HOST"
echo "  Port: $PORT"
echo "  Log Level: $LOG_LEVEL"

# Start the server
exec uvicorn main:app \
    --host "$HOST" \
    --port "$PORT" \
    --log-level "${LOG_LEVEL,,}" \
    --reload

