variable "region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region."
}

variable "project" {
  type        = string
  default     = "atlas"
  description = "Name prefix for all resources."
}

variable "vpc_cidr" {
  type    = string
  default = "10.40.0.0/16"
}

variable "kubernetes_version" {
  type    = string
  default = "1.30"
}

variable "node_instance_types" {
  type    = list(string)
  default = ["m6i.large"]
}

variable "node_desired_size" {
  type    = number
  default = 3
}

variable "postgres_instance_class" {
  type    = string
  default = "db.r6g.large"
}

variable "postgres_allocated_storage" {
  type    = number
  default = 100
}

variable "db_username" {
  type    = string
  default = "atlas"
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "Set via TF_VAR_db_password or a secret manager — never commit."
}

variable "redis_node_type" {
  type    = string
  default = "cache.r6g.large"
}

variable "opensearch_instance_type" {
  type    = string
  default = "r6g.large.search"
}

variable "opensearch_instance_count" {
  type    = number
  default = 2
}
