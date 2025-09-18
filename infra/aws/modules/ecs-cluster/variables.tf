variable "cluster_name" {
  type = string
}

variable "logs_region" {
  type = string
}

variable "rds_credentials_secret_arn" {
  type = string
}

variable "auth_configuration_secret_arn" {
  type = string
}

variable "secrets_encryption_key_arn" {
  type = string
}

variable "execution_role_name" {
  type = string
}
