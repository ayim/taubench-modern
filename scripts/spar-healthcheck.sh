#!/bin/sh

case ",${DISABLED_SERVICE}," in
  *,agent-server,*)
    curl -f "http://localhost:${WORKROOM_PORT:-8001}/" || exit 1
    ;;
  *,workroom,*)
    curl -f "http://localhost:${AGENT_SERVER_PORT:-8000}/api/v2/health" || exit 1
    ;;
  *)
    curl -f "http://localhost:${AGENT_SERVER_PORT:-8000}/api/v2/health" && \
    curl -f "http://localhost:${WORKROOM_PORT:-8001}/" || exit 1
    ;;
esac
