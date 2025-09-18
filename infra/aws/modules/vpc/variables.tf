variable "vpc_name" {
  type = string
}

variable "vpc_cidr_block" {
  # Default VPC CIDR block with 16 bit netmask
  #  - 65 536 host addresses
  #  - IP Range 10.135.0.0 - 10.135.255.255
  type    = string
  default = "10.135.0.0/16"
}

variable "private_subnet_count" {
  type = number
  validation {
    condition     = var.private_subnet_count >= 1 && var.public_subnet_count <= 4
    error_message = "Variable private_subnet_count should be between 1 and 4."
  }
}

variable "public_subnet_count" {
  type = number
  validation {
    condition     = var.public_subnet_count >= 0 && var.public_subnet_count <= 4
    error_message = "Variable public_subnet_count should be between 0 and 4."
  }
}

variable "natgw_count" {
  type = number
  validation {
    condition     = var.natgw_count >= 0 && var.natgw_count <= var.public_subnet_count
    error_message = "Variable natgw_count should be between 0 and public_subnet_count (${var.public_subnet_count})."
  }
}