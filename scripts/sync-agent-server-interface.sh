#!/usr/bin/env bash

set -eou pipefail

# We run a temporary instance of Agent Server on a non-standard port to make sure we have the latest code running
TMP_AGENT_SERVER_PORT="28123"
SCRIPT_DIR="$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)"
ROOT_DIR="${SCRIPT_DIR}/.."
WORKROOM_DIR="${ROOT_DIR}/workroom"
PRIVATE_OPENAPI_JSON="${WORKROOM_DIR}/packages/agent-server-interface/private.openapi.json"
PUBLIC_OPENAPI_JSON="${WORKROOM_DIR}/packages/agent-server-interface/public.openapi.json"

# [Boot Agent Server] ##############################################################################

echo "Starting Agent Server for spec introspection..."

cd "${ROOT_DIR}"

make sync
PORT="${TMP_AGENT_SERVER_PORT}" make run-server &> /dev/null &
server_pid="${!}"

kill_server() {
  kill "${server_pid}"
}
trap kill_server EXIT

for i in {1..10}; do
  sleep 2

  if curl -sf "http://localhost:${TMP_AGENT_SERVER_PORT}/api/v2/ok" > /dev/null; then
    break
  fi

  echo "Agent Server not responsive yet (try #${i})..."

  if [ "${i}" -eq 10 ]; then
    echo "Agent Server failed to respond after 10 attempts"
    exit 1
  fi
done

# [Generate Interface] #############################################################################

echo "Synchronizing OpenAPI specifications..."

cd "${WORKROOM_DIR}"

curl \
  --silent \
  --fail-with-body \
  --show-error \
  "http://localhost:${TMP_AGENT_SERVER_PORT}/api/v2/openapi.json" > "${PRIVATE_OPENAPI_JSON}"

curl \
  --silent \
  --fail-with-body \
  --show-error \
  "http://localhost:${TMP_AGENT_SERVER_PORT}/api/public/v1/openapi.json" > "${PUBLIC_OPENAPI_JSON}"

echo "Generating TS types for the interface..."
cd "${ROOT_DIR}/workroom/packages/agent-server-interface" && \
  npm run build:all
