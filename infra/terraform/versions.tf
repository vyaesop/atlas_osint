terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Use a remote backend in real deployments (commented for first-run).
  # backend "s3" {
  #   bucket = "atlas-terraform-state"
  #   key    = "atlas/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.region
}
