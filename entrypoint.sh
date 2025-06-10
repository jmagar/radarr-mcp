#!/bin/bash

echo "Starting Radarr MCP Server..."
echo "RADARR_URL: ${RADARR_URL}"
echo "RADARR_MCP_HOST: ${RADARR_MCP_HOST:-127.0.0.1}"
echo "RADARR_MCP_PORT: ${RADARR_MCP_PORT:-4200}"
echo "LOG_LEVEL: ${LOG_LEVEL:-INFO}"

# Check required environment variables
if [ -z "$RADARR_URL" ]; then
    echo "ERROR: RADARR_URL environment variable is required"
    exit 1
fi

if [ -z "$RADARR_API_KEY" ]; then
    echo "ERROR: RADARR_API_KEY environment variable is required"
    exit 1
fi

# Wait for Radarr to be available
echo "Waiting for Radarr to be available at $RADARR_URL..."
timeout=60
while [ $timeout -gt 0 ]; do
    if curl -s -o /dev/null -w "%{http_code}" "$RADARR_URL/api" | grep -q "200\|401\|403"; then
        echo "Radarr is available"
        break
    fi
    echo "Waiting for Radarr... ($timeout seconds remaining)"
    sleep 5
    timeout=$((timeout - 5))
done

if [ $timeout -le 0 ]; then
    echo "WARNING: Radarr may not be available, starting MCP server anyway"
fi

# Start the MCP server
exec python radarr-mcp-server.py 