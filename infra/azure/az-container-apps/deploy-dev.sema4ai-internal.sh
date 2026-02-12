#!/usr/bin/env bash

#
# Script for deploying / updating our internal "main" Azure instance
#

set -euo pipefail

# Component tags on CI ECR
spar_ecr_ref="024848458368.dkr.ecr.us-east-1.amazonaws.com/ci/moonraker/spar:2.1.21_ec51afea6.20251119T082059Z"

# Extract image tags
spar_tag="$(cut -d: -f2 <<< ${spar_ecr_ref})"

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

# Pull, retag and push images
export SPAR_IMAGE_REF="${ACR_LOGIN_SERVER}/s4te-spar:${spar_tag}"
docker pull "${spar_ecr_ref}"
docker tag \
  "${spar_ecr_ref}" \
  "${SPAR_IMAGE_REF}"
docker push "${SPAR_IMAGE_REF}"

# Export our CI deployment configuration
export RELEASE_NAME="main"
export DB_NAME="agents_teamedition1"

# Run deploy script
exec ./app-configuration/deploy.sh
