#!/usr/bin/env bash

# These (required) variables are injected by CodeBuild
# The variables are either carried from Terraform, or supplied when starting the build
required_vars=(
  # From Terraform
  ALB_LISTENER_ARN
  ALB_TARGETS_SECURITY_GROUP_ID
  AWS_REGION
  ECS_CLUSTER_NAME
  ECS_TASK_EXECUTION_ROLE_ARN
  AUTH_CONFIGURATION_SECRET_ARN
  RDS_CREDENTIALS_SECRET_ARN
  VPC_ID
  VPC_SUBNETS
  # Supplied when starting the build
  BRANCH_NAME
  SPAR_IMAGE_REF
)

# Convert branch name to lowercase alphanumeric release identifier
RELEASE_NAME="$(
  echo "${BRANCH_NAME}" \
    | tr -dC "[:alnum:]" \
    | tr "[:upper:]" "[:lower:]"
)"
export RELEASE_NAME

for var in "${required_vars[@]}"; do
  if [[ -z "${!var}" ]]; then
    echo "Error: ${var} is not set" >&2
    exit 1
  elif [[ "${!var}" == "PLACEHOLDER" ]]; then
    echo "Error: ${var} has PLACEHOLDER value" >&2
    exit 1
  fi
done

set -euo pipefail

script_dir="$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)"
task_definition_template="${script_dir}/../../template.ecs-task-def.json"
data_server_tag=$(cat compose.yml | sed -n '/x-data-server-image:/s/.*data-server:\([^"]*\).*/\1/p')

export DB_NAME="agents_${RELEASE_NAME}"
export DATA_SERVER_IMAGE_REF="024848458368.dkr.ecr.us-east-1.amazonaws.com/ci/data/data-server:${data_server_tag}"
export PSQL_IMAGE_REF="024848458362.dkr.ecr.us-east-1.amazonaws.com/docker-hub/library/postgres:17-alpine"
# Intermediary OIDC redirect URI, exported from infra/aws/modules/oidc-bounce-lambda/outputs.tf
export OIDC_BOUNCE_FUNCTION_URL="https://gh3hejttujva6f73f2uvi3f5rq0ywnzb.lambda-url.us-east-1.on.aws/"

# Check if Target Group exists, create if not
target_group_name="${RELEASE_NAME}-tg"
target_group_arn=$(
  aws elbv2 describe-target-groups \
    --names "${target_group_name}" \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text || echo ""
)

if [ -z "${target_group_arn}" ]; then
  echo "Creating target group ${target_group_name}..."
  target_group_arn=$(aws elbv2 create-target-group \
    --name "${target_group_name}" \
    --protocol HTTP \
    --port 8001 \
    --vpc-id "${VPC_ID}" \
    --target-type ip \
    --health-check-enabled \
    --health-check-protocol HTTP \
    --health-check-path "/" \
    --health-check-interval-seconds 30 \
    --health-check-timeout-seconds 5 \
    --healthy-threshold-count 2 \
    --unhealthy-threshold-count 2 \
    --matcher HttpCode='"200,302"' \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text \
    --tags Key=branch_name,Value="${BRANCH_NAME}")
else
  echo "Target group ${target_group_name} already exists"
fi

# Check if Listener Rule exists with this path pattern
path_pattern="/tenants/${RELEASE_NAME}/*"
existing_rule=$(aws elbv2 describe-rules \
  --listener-arn "${ALB_LISTENER_ARN}" \
  --query "Rules[?Conditions[?Field=='path-pattern' && Values[0]=='${path_pattern}']].RuleArn" \
  --output text)

if [ -z "${existing_rule}" ]; then
  # Find next available priority
  max_priority=$(aws elbv2 describe-rules \
    --listener-arn "${ALB_LISTENER_ARN}" \
    --query 'Rules[?Priority!=`default`].Priority' \
    --output text | tr '\t' '\n' | sort -n | tail -1)
  priority=$((${max_priority:-0} + 1))

  echo "Creating listener rule for ${path_pattern} with priority ${priority}..."
  aws elbv2 create-rule \
    --listener-arn "${ALB_LISTENER_ARN}" \
    --priority "${priority}" \
    --conditions "Field=path-pattern,Values=${path_pattern}" \
    --actions "Type=forward,TargetGroupArn=${target_group_arn}" \
    --tags Key=branch_name,Value="${BRANCH_NAME}"
else
  echo "Listener rule for ${path_pattern} already exists"
fi

# Update Task Definition
task_definition_revision=$(
  aws ecs register-task-definition \
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
    --load-balancers "targetGroupArn=${target_group_arn},containerName=spar,containerPort=8001" \
    --launch-type FARGATE \
    --desired-count 1
fi
