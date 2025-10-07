#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)"

if [ -z "${OPERATION:-}" ]; then
  echo "Error: OPERATION environment variable is not set. Specify either 'deploy' or 'teardown'."
  exit 1
fi

case "${OPERATION}" in
  deploy)
    "${script_dir}/deploy.sh"
    ;;
  teardown)
    "${script_dir}/teardown.sh"
    ;;
  *)
    echo "Error: Invalid OPERATION '${OPERATION}'. Must be 'deploy' or 'teardown'"
    exit 1
    ;;
esac
