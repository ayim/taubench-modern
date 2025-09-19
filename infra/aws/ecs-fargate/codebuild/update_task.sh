#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)"
task_definition_template="${script_dir}/template.ecs-task-def.json"
repo_root="$(git rev-parse --show-toplevel)"

# These (required) variables are injected by CodeBuild
# The variables are either carried from Terraform, or supplied when starting the build
required_vars=(
  # From Terraform
  ALB_TARGET_GROUP_ARN
  ALB_TARGETS_SECURITY_GROUP_ID
  AWS_REGION
  ECS_CLUSTER_NAME
  ECS_TASK_EXECUTION_ROLE_ARN
  AUTH_CONFIGURATION_SECRET_ARN
  RDS_CREDENTIALS_SECRET_ARN
  VPC_SUBNETS
  # Supplied when starting the build
  RELEASE_NAME
  SPAR_IMAGE_REF
)

for var in "${required_vars[@]}"; do
  if [[ -z "${!var}" ]]; then
    echo "Error: ${var} is not set" >&2
    exit 1
  elif [[ "${!var}" == "PLACEHOLDER" ]]; then
    echo "Error: ${var} has PLACEHOLDER value" >&2
    exit 1
  fi
done

data_server_tag=$(cat compose.yml | sed -n '/x-data-server-image:/s/.*data-server:\([^"]*\).*/\1/p')

export DB_NAME="agents_${RELEASE_NAME//-/_}" # PostgreSQL database names should use underscores for separating words
export DATA_SERVER_IMAGE_REF="024848458368.dkr.ecr.us-east-1.amazonaws.com/ci/data/data-server:${data_server_tag}"
export PSQL_IMAGE_REF="024848458362.dkr.ecr.us-east-1.amazonaws.com/docker-hub/library/postgres:13-alpine"

envsubst < "${task_definition_template}"

# Update Task Definition
task_definition_revision=$(
  aws ecs register-task-definition \
    --region "${AWS_REGION}" \
    --family "${RELEASE_NAME}" \
    --cli-input-json "$(envsubst < "${task_definition_template}")" | jq ".taskDefinition.revision"
)

# Create / Update Service
if aws ecs describe-services \
  --cluster "${ECS_CLUSTER_NAME}" \
  --services "${RELEASE_NAME}" \
  --query "services[?status=='ACTIVE'].serviceName" \
  --output text 2> /dev/null | grep -q "${RELEASE_NAME}"; then

  echo "Updating existing service ${RELEASE_NAME}"
  aws ecs update-service \
    --no-cli-pager \
    --cluster "${ECS_CLUSTER_NAME}" \
    --service "${RELEASE_NAME}" \
    --task-definition "${RELEASE_NAME}:${task_definition_revision}" \
    --network-configuration "awsvpcConfiguration={subnets=[${VPC_SUBNETS}],securityGroups=[${ALB_TARGETS_SECURITY_GROUP_ID}]}" \
    --force-new-deployment \
    --desired-count 1
else
  echo "Creating new service ${RELEASE_NAME}"
  aws ecs create-service \
    --no-cli-pager \
    --cluster "${ECS_CLUSTER_NAME}" \
    --service-name "${RELEASE_NAME}" \
    --task-definition "${RELEASE_NAME}:${task_definition_revision}" \
    --network-configuration "awsvpcConfiguration={subnets=[${VPC_SUBNETS}],securityGroups=[${ALB_TARGETS_SECURITY_GROUP_ID}]}" \
    --load-balancers "targetGroupArn=${ALB_TARGET_GROUP_ARN},containerName=spar,containerPort=8001" \
    --launch-type FARGATE \
    --desired-count 1
fi
