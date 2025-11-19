#!/usr/bin/env bash

#
# Script for deploying / updating our internal "main" Azure instance
#

set -euo pipefail

# Component tags on CI ECR
SPAR_TAG="2.1.21_ec51afea6.20251119T082059Z"
MCP_RUNTIME_TAG="1.0.0_91f9670.20251118T094215Z"
DATA_SERVER_TAG="1.4.0_952c28f.20251106T060331Z"

# Export Terraform output
tf_output=$(terraform output -json)
ACR_REGISTRY_NAME=$(echo "${tf_output}" | jq -r '.acr_registry_name.value')
export ACR_REGISTRY_NAME
RESOURCE_GROUP_NAME=$(echo "${tf_output}" | jq -r '.resource_group_name.value')
export RESOURCE_GROUP_NAME
APP_ENVIRONMENT_ID=$(echo "${tf_output}" | jq -r '.app_environment_id.value')
export APP_ENVIRONMENT_ID
APP_UAI_ID=$(echo "${tf_output}" | jq -r '.app_uai_id.value')
export APP_UAI_ID
KEY_VAULT_URI=$(echo "${tf_output}" | jq -r '.key_vault_uri.value')
export KEY_VAULT_URI
ACR_LOGIN_SERVER=$(echo "${tf_output}" | jq -r '.acr_login_server.value')
export ACR_LOGIN_SERVER

# Copy CI images to Azure
az acr login --name "${ACR_REGISTRY_NAME}"

export SPAR_IMAGE_REF="${ACR_LOGIN_SERVER}/s4te-spar:${SPAR_TAG}"
docker tag \
  "024848458368.dkr.ecr.us-east-1.amazonaws.com/ci/ace/spar:${SPAR_TAG}" \
  "${SPAR_IMAGE_REF}"
docker push "${SPAR_IMAGE_REF}"

export MCP_RUNTIME_IMAGE_REF="${ACR_LOGIN_SERVER}/s4te-mcp-runtime:${MCP_RUNTIME_TAG}"
docker tag \
  "024848458368.dkr.ecr.us-east-1.amazonaws.com/ci/ace/mcp-runtime:${MCP_RUNTIME_TAG}" \
  "${MCP_RUNTIME_IMAGE_REF}"
docker push "${MCP_RUNTIME_IMAGE_REF}"

export DATA_SERVER_IMAGE_REF="${ACR_LOGIN_SERVER}/s4te-data-server:${DATA_SERVER_TAG}"
docker tag \
  "024848458368.dkr.ecr.us-east-1.amazonaws.com/ci/data/data-server:${DATA_SERVER_TAG}" \
  "${DATA_SERVER_IMAGE_REF}"
docker push "${DATA_SERVER_IMAGE_REF}"

# Our CI deployment configuration
export RELEASE_NAME="main"
export DB_NAME="agents_teamedition1"

# Run deploy script
exec ./app-configuration/deploy.sh
