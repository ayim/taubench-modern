#!/bin/sh

set -e

# Signal handling for graceful shutdown
cleanup() {
    [ ! -z "$AGENT_PID" ] && kill -TERM "$AGENT_PID" 2>/dev/null || true
    [ ! -z "$WORKROOM_PID" ] && kill -TERM "$WORKROOM_PID" 2>/dev/null || true
    wait; exit 0
}
trap cleanup TERM INT

# Determine which services to start
DISABLED_SERVICE="${DISABLED_SERVICE:-}"
START_AGENT_SERVER=true
START_WORKROOM=true

# Parse comma-separated disabled services
if [ -n "$DISABLED_SERVICE" ]; then
    case ",$DISABLED_SERVICE," in
        *,agent-server,*)
            START_AGENT_SERVER=false
            echo "Agent-server disabled via DISABLED_SERVICE"
            ;;
    esac
    case ",$DISABLED_SERVICE," in
        *,workroom,*)
            START_WORKROOM=false
            echo "Workroom disabled via DISABLED_SERVICE"
            ;;
    esac

    # Validate that at least one service is enabled
    if [ "$START_AGENT_SERVER" = "false" ] && [ "$START_WORKROOM" = "false" ]; then
        echo "Error: Cannot disable both agent-server and workroom services"
        exit 1
    fi
fi

# Start agent-server if enabled
if [ "$START_AGENT_SERVER" = "true" ]; then
    echo "Starting agent-server..."
    exec /usr/local/bin/agent-server --host 0.0.0.0 --port ${AGENT_SERVER_PORT} &

    AGENT_PID=$!
    echo "Agent-server started (PID: $AGENT_PID)"
fi

# Start workroom if enabled
if [ "$START_WORKROOM" = "true" ]; then
    echo "Starting workroom..."
    cd /app/workroom
    node ./backend/dist/index.js &
    WORKROOM_PID=$!
    echo "Workroom started (PID: $WORKROOM_PID)"
fi

# Wait for all services
echo "Services started, waiting for them to finish..."
wait
