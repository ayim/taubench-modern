#!/bin/bash

# Script to wait for SPAR stack services to become healthy
# Usage: ./scripts/wait-for-spar-health.sh [service]
#   service: optional, one of "spar" (default) or "agent-server"

set -e

# Function to wait for a service to be healthy
wait_for_healthy() {
  local service=$1
  local max_attempts=60  # 5 minutes with 5s intervals
  local attempt=1
  
  echo "Waiting for $service to be healthy..."
  while [ $attempt -le $max_attempts ]; do
    # Use docker compose ps with table format and grep for simpler parsing
    local status_line=$(docker compose ps --format "table {{.Service}}\t{{.State}}\t{{.Health}}" | grep "^$service" || echo "")
    
    if [ -n "$status_line" ]; then
      local state=$(echo "$status_line" | awk '{print $2}')
      local health=$(echo "$status_line" | awk '{print $3}')
      
      # Check if service is healthy or running (for services without healthcheck)
      if [ "$health" = "healthy" ] || ([ "$state" = "running" ] && [ "$health" = "" ]); then
        echo "$service is ready (state: $state, health: $health)"
        return 0
      fi
      
      echo "Attempt $attempt/$max_attempts: $service state is '$state', health is '$health', waiting..."
    else
      echo "Attempt $attempt/$max_attempts: $service not found, waiting..."
    fi
    
    sleep 5
    attempt=$((attempt + 1))
  done
  
  echo "ERROR: $service failed to become healthy after $max_attempts attempts"
  return 1
}

service="${1:-spar}"

# Show initial container status for debugging
echo "Initial container status:"
docker compose ps

# Wait for core infrastructure (postgres is always required)
wait_for_healthy "postgres" || exit 1

case "${service}" in
  spar)
    # Full SPAR stack: needs telemetry services + spar
    wait_for_healthy "influx-db" || exit 1
    wait_for_healthy "otel-collector" || exit 1
    wait_for_healthy "spar" || exit 1
    ;;
  agent-server)
    # Agent-server only: no telemetry services needed
    wait_for_healthy "agent-server" || exit 1
    ;;
  *)
    echo "ERROR: unknown service '${service}'. Expected 'spar' or 'agent-server'."
    exit 1
    ;;
esac

# Final status check
echo "All services are ready!"
docker compose ps

# Show recent logs for verification
docker compose logs --tail=50
