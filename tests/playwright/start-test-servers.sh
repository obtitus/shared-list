#!/bin/bash

# Start multiple test servers on different ports
# This script is used by Playwright to run isolated test servers

echo "Starting test servers..."

# Function to check if server is up
check_server() {
  local port=$1
  local max_attempts=30
  local attempt=1

  while [ $attempt -le $max_attempts ]; do
    if curl -f -s "http://localhost:$port/api" > /dev/null 2>&1; then
      echo "Server on port $port is ready"
      return 0
    fi
    echo "Waiting for server on port $port (attempt $attempt/$max_attempts)..."
    sleep 1
    ((attempt++))
  done

  echo "Server on port $port failed to start"
  return 1
}

# First, start all servers
echo "Starting all servers..."
for port in {8001..8007}; do
  echo "Starting server on port $port"
  PORT=$port uv run python app/main.py &
  pid=$!
  echo $pid > "server_$port.pid"
done

# Then, check each server
echo "Checking server readiness..."
for port in {8001..8007}; do
  if ! check_server $port; then
    echo "Failed to start server on port $port"
    exit 1
  fi
done

echo "All test servers started and ready"

# Write a summary of PIDs for cleanup
echo "Server PIDs:"
for port in {8001..8007}; do
  if [ -f "server_$port.pid" ]; then
    pid=$(cat "server_$port.pid")
    echo "Port $port: PID $pid"
  fi
done
