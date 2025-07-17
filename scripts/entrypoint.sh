#!/bin/bash

# Run the agent server as the entry for the Docker container.
# This is necessary to:
#  - capture signals like interrupt or terminate
#  - handle environment variable substitution for properties like ports

set -e

exec /usr/local/bin/agent-server --host 0.0.0.0 --port ${AGENT_SERVER_PORT}
