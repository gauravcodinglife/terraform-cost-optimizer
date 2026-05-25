variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
}

variable "project" {
  description = "Project tag value"
  type        = string
}

variable "environment" {
  description = "Environment tag value"
  type        = string
}

variable "owner" {
  description = "Owner tag value"
  type        = string
}

variable "ssh_ingress_cidr" {
  description = "CIDR allowed for SSH access"
  type        = string
}
