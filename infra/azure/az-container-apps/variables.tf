variable "subscription_id" {
  type        = string
  description = "The subscription under which the resources should be created"
}

variable "infra_id" {
  type        = string
  description = "A unique prefix to include in the names of the created resources (e.g. s4aimyorg)"
  validation {
    condition     = can(regex("^[a-z0-9]+$", var.infra_id)) && length(var.infra_id) <= 15
    error_message = "Lowercase alphanumeric characters only, max 15 characters"
  }
}

variable "infra_location" {
  type        = string
  description = "The location (e.g. 'West Europe', 'East US') to provision the infrastructure in"
}

variable "key_vault_administrators_object_id" {
  type        = string
  description = "Object ID for the principal (group) that should retain administrator access to the Key Vault provisioned"
}
