variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "infra_id" {
  description = "Unique identifier for the infrastructure"
  type        = string
  default     = "moonraker"
}

variable "host_name" {
  description = "Unique identifier for the infrastructure"
  type        = string
  default     = "moonraker.sema4ai.dev"
}

variable "provision_github_deployment_role" {
  description = "Whether or not to create a role that has the permission to run the deployer CodeBuild project (used for GitHub automation)"
  type        = bool
  default     = true
}
