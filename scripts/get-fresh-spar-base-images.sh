#!/usr/bin/env bash

set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"

dockerfiles=(
  "${repo_root}/Dockerfile.spar"
  "${repo_root}/workroom/mcp-runtime/Dockerfile"
)

for dockerfile_path in "${dockerfiles[@]}"; do
  echo "$(tput bold)Processing:$(tput sgr0) ${dockerfile_path#"${repo_root}/"}"
  for stale_ref in $(grep -E "ARG (GOLANG|NODEJS)_BASE_IMAGE=" "${dockerfile_path}" | cut -d= -f2 | tr -d '"'); do
    ref_without_digest="$(echo "${stale_ref}" | cut -d@ -f1)"
    latest_digest="$(
      docker pull --platform linux/amd64 -q "$(echo "${stale_ref}" | cut -d@ -f1)" \
        | xargs docker inspect --format='{{index .RepoDigests 0}}' | cut -d@ -f2
    )"
    updated_ref="${ref_without_digest}@${latest_digest}"
    if [[ "${stale_ref}" != "${updated_ref}" ]]; then
      tmp_file="$(mktemp)"
      sed -e "s/${stale_ref}/${updated_ref}/" "${dockerfile_path}" > "${tmp_file}"
      mv "${tmp_file}" "${dockerfile_path}"
      echo "  $(tput bold)Updated:$(tput sgr0)"
      echo "     ${stale_ref}"
      echo "  => ${updated_ref}"
    else
      echo "  $(tput bold)Already fresh:$(tput sgr0)"
      echo "     ${updated_ref}"
    fi
  done
  echo ""
done
