variable "ecs_runtime_role_arn" {
  type = string
}

variable "infra_id" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "vpc_subnet_ids" {
  type = set(string)
}

variable "ecs_tasks_security_group_id" {
  type        = string
  description = "Security group ID of the ECS tasks that need to access EFS"
}
