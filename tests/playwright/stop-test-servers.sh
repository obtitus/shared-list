#!/bin/bash

# Stop test servers started by start-test-servers.sh

echo "Stopping test servers..."

# Kill servers using saved PIDs
for port in {8001..8007}; do
  pid_file="server_$port.pid"
  if [ -f "$pid_file" ]; then
    pid=$(cat "$pid_file")
    echo "Stopping server on port $port (PID: $pid)"
    kill $pid 2>/dev/null || echo "Process $pid already stopped"
    rm -f "$pid_file"
  else
    echo "No PID file found for port $port"
  fi
done

sleep 5
