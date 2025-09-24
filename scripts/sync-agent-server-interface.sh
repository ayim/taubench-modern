#!/usr/bin/env bash

set -eou pipefail

SCRIPT_DIR="$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)"
ROOT_DIR="${SCRIPT_DIR}/.."
WORKROOM_DIR="${ROOT_DIR}/workroom"
PRIVATE_OPENAPI_JSON="${WORKROOM_DIR}/packages/agent-server-interface/private.openapi.json"
PUBLIC_OPENAPI_JSON="${WORKROOM_DIR}/packages/agent-server-interface/public.openapi.json"

cd "${ROOT_DIR}"

make sync
PRIVATE_OPENAPI_FILE="${PRIVATE_OPENAPI_JSON}" PUBLIC_OPENAPI_FILE="${PUBLIC_OPENAPI_JSON}" make run-openapi-spec &> /dev/null

# [Generate Interface] #############################################################################

echo "Generating TS types for the interface..."
cd "${ROOT_DIR}/workroom/packages/agent-server-interface" && \
  npm run build:all
