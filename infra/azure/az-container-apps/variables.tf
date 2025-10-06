variable "developer_group_object_id" {
  type        = string
  description = "Object ID for developers group"
}

variable "subscription_id" {
  type        = string
  description = "The subscription under which the resources should be created"
}

variable "infra_id" {
  type        = string
  description = "An identifier to include in the names of the created resources"
  default     = "s4teamedition1"
}
