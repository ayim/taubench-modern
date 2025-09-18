variable "cluster_name" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
  validation {
    condition     = length(var.subnet_ids) >= 1
    error_message = "At least one subnet must be given."
  }
}

variable "postgres_engine_version" {
  type    = string
  default = "17.5"
}

variable "cluster_deletion_protection" {
  type    = bool
  default = false
}

variable "cluster_instance_count" {
  type = number
}

variable "encryption_key_arn" {
  type = string
}

variable "admin_credentials_secret_name" {
  type        = string
  description = "Value for the secret name for the admin credentials. If not provided, no secret will be created."
  nullable    = true
  default     = null
}
