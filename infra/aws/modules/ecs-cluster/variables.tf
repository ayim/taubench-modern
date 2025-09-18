variable "cluster_name" {
  type = string
}

variable "logs_region" {
  type = string
}

variable "database_credentials_secret_arn" {
  type = string
}

variable "database_credentials_encryption_key_arn" {
  type = string
}

variable "execution_role_name" {
  type = string
}
