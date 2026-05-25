variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (staging, prod, etc.)"
  type        = string
  default     = "staging"
}

variable "project" {
  description = "Project name for tagging"
  type        = string
  default     = "NimbusKart"
}

variable "owner" {
  description = "Team or person responsible for these resources"
  type        = string
  default     = "platform-team"
}

variable "ssh_ingress_cidr" {
  description = "CIDR block allowed to SSH into instances. CHANGE THIS in production!"
  type        = string
  default     = "10.0.0.0/8"   # We changed this from 0.0.0.0/0 — explained below
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.20.0.0/16"
}

variable "stopped_instance_age_threshold_days" {
  description = "Flag instances stopped longer than this many days"
  type        = number
  default     = 14
}
