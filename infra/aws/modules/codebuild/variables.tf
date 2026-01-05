variable "infra_id" {
  type = string
}

variable "cluster_master_key_arn" {
  type        = string
  description = "Master cluster KMS key ARN"
}

variable "cluster_name" {
  type = string
}

variable "allowed_github_subjects_write" {
  description = "Github subjects that can update tasks. Example: repo:robocorp/action-compute-environment:*"
  type        = set(string)
  default     = []
}

variable "github_oidc_provider_arn" {
  description = "Github OIDC provider ARN. Must match the provider installed on this account."
  type        = string
}

variable "ecs_task_execution_role_arn" {
  type = string
}

variable "ecs_task_runtime_role_arn" {
  type = string
}

variable "alb_target_group_arn" {
  type = string
}

variable "alb_listener_arn" {
  type = string
}

variable "auth_configuration_secret_arn" {
  type = string
}

variable "rds_credentials_secret_arn" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "vpc_subnet_ids" {
  type = set(string)
}

variable "alb_targets_security_group_id" {
  type = string
}

variable "agent_files_region" {
  type = string
}

variable "agent_files_role_arn" {
  type = string
}

variable "agent_files_bucket_name" {
  type = string
}

variable "mcp_runtime_efs_filesystem_id" {
  type = string
}

variable "mcp_runtime_efs_access_point_id" {
  type = string
}

variable "default_security_group_id" {
  type = string
}
