#!/usr/bin/env bash

set -eou pipefail

script_dir="$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)"
root_dir="${script_dir}/.."
workroom_dir="${root_dir}/workroom"

export PRIVATE_OPENAPI_FILE="${workroom_dir}/packages/agent-server-interface/private.openapi.json"
export PUBLIC_OPENAPI_FILE="${workroom_dir}/packages/agent-server-interface/public.openapi.json"

cd "${root_dir}"

# [Generate Interface] #############################################################################
make sync
make run-openapi-spec
echo "Generating TS types for the interface..."
cd "${root_dir}/workroom/packages/agent-server-interface" && \
  npm run build:all
