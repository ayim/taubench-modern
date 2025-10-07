#!/usr/bin/env bash

set -euo pipefail

# These (required) variables are injected by CodeBuild
# The variables are either carried from Terraform, or supplied when starting the teardown
required_vars=(
  # From Terraform
  ALB_LISTENER_ARN
  AWS_REGION
  ECS_CLUSTER_NAME
  # Supplied when starting the teardown
  BRANCH_NAME
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

# Delete Service (force stop)
existing_service=$(
  aws ecs describe-services \
    --cluster "${ECS_CLUSTER_NAME}" \
    --services "${RELEASE_NAME}" \
    --query "services[?status!='INACTIVE'].serviceName" \
    --output text
)
if [ -z "${existing_service}" ]; then
  echo "WARNING: Couldn't find ECS service"
else
  echo "Deleting ECS Service"
  aws ecs delete-service \
    --cluster "${ECS_CLUSTER_NAME}" \
    --service "${RELEASE_NAME}" \
    --force
fi

# Delete Listener Rule
path_pattern="/tenants/${RELEASE_NAME}/*"
existing_rule_arn=$(
  aws elbv2 describe-rules \
    --listener-arn "${ALB_LISTENER_ARN}" \
    --query "Rules[?Conditions[?Field=='path-pattern' && Values[0]=='${path_pattern}']].RuleArn" \
    --output text
)
if [ -z "${existing_rule_arn}" ]; then
  echo "WARNING: Couldn't find listener rule"
else
  echo "Deleting listener rule"
  aws elbv2 delete-rule \
    --rule-arn "${existing_rule_arn}"
fi

# Delete Target Group
target_group_name="${RELEASE_NAME}-tg"
target_group_arn=$(
  aws elbv2 describe-target-groups \
    --names "${target_group_name}" \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text
)
if [ -z "${target_group_arn}" ]; then
  echo "WARNING: Couldn't find target group"
else
  echo "Deleting Target Group"
  aws elbv2 delete-target-group \
    --target-group-arn "${target_group_arn}"
fi
