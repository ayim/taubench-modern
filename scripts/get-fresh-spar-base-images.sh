#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)"

for img in $(grep -E "ARG (GOLANG|NODEJS)_BASE_IMAGE=" "${script_dir}/../Dockerfile.spar" | cut -d= -f2 | tr -d '"' | cut -d@ -f1); do
  digest="$(
    docker pull --platform linux/amd64 -q "${img}" \
      | xargs docker inspect --format='{{index .RepoDigests 0}}' | cut -d@ -f2
  )"
  echo "${img}@${digest}"
done
