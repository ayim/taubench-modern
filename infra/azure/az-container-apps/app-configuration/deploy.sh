#!/usr/bin/env bash

script_dir="$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)"

export PSQL_IMAGE_REF="postgres:16"

required_vars=(
  RESOURCE_GROUP_NAME # Application Resource Group Name
  APP_ENVIRONMENT_ID # Container App Environment ID
  APP_UAI_ID # Application UAI (User Assigned Identity) ID
  KEY_VAULT_URI # Application Key Vault URI
  SPAR_IMAGE_REF # Docker image reference for the SPAR component
  DATA_SERVER_IMAGE_REF # Docker image reference for the Data Server component
  MCP_RUNTIME_IMAGE_REF # Docker image reference for the MCP Runtime component
  ACR_LOGIN_SERVER # ACR registry login server
)

for var in "${required_vars[@]}"; do
  if [[ -z "${!var}" ]]; then
    echo "Error: ${var} is not set" >&2
    exit 1
  fi
done

set -euo pipefail

# Name used for the application database, use $DB_NAME or default to "sema4aiteamedition"
export DB_NAME="${DB_NAME:-sema4aiteamedition}"
# Name used for the Container App, use $RELEASE_NAME or default to "sema4aiteamedition"
export RELEASE_NAME="${RELEASE_NAME:-sema4aiteamedition}"

if az containerapp show \
  --name "${RELEASE_NAME}" \
  --resource-group "${RESOURCE_GROUP_NAME}" \
  &>/dev/null; then

  echo "Container App '${RELEASE_NAME}' exists. Updating..."
  az containerapp update \
    --name "${RELEASE_NAME}" \
    --resource-group "${RESOURCE_GROUP_NAME}" \
    --yaml <(envsubst < "${script_dir}/template.app-configuration.json")
else
  echo "Container App '${RELEASE_NAME}' does not exist. Creating..."
  az containerapp create \
    --name "${RELEASE_NAME}" \
    --resource-group "${RESOURCE_GROUP_NAME}" \
    --yaml <(envsubst < "${script_dir}/template.app-configuration.json")
fi
