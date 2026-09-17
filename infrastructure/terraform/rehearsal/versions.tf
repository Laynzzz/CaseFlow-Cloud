terraform {
  required_version = ">= 1.16.2, < 1.17.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "6.62.0" }
  }
  backend "s3" {}
}

provider "aws" {
  region              = var.region
  allowed_account_ids = [var.account_id]
  default_tags {
    tags = { Project = "caseflow", Environment = "rehearsal", ExpiresAt = var.expires_at, ManagedBy = "terraform" }
  }
}
