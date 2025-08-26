#!/bin/bash

# Test script for SPAR startup and health checking
# Usage: ./scripts/test-spar-startup.sh

set -e

echo "=== Testing SPAR Stack Startup ==="

# Start SPAR stack
echo "Starting SPAR stack..."
COMPOSE_PROFILES=spar-no-auth docker compose up --build -d

# Wait for services to be healthy
echo "Waiting for services to be healthy..."
./scripts/wait-for-spar-health.sh

echo "=== SPAR Stack is ready for testing! ==="
echo ""
echo "You can now:"
echo "  - Run tests: cd server && uv run pytest -m spar"
echo "  - Check logs: docker compose logs"
echo "  - Stop stack: docker compose down"
