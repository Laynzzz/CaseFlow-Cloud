variable "account_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.account_id))
    error_message = "Use the explicitly authorized 12-digit AWS account."
  }
}
variable "region" {
  type    = string
  default = "us-east-1"
  validation {
    condition     = var.region == "us-east-1"
    error_message = "This initial profile pins the us-east-1 RDS trust bundle; review the CA, AMI and prices before selecting another region."
  }
}
variable "name" {
  type    = string
  default = "caseflow-rehearsal"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,23}$", var.name))
    error_message = "Name must be 3–24 lowercase letters/digits/hyphens."
  }
}
variable "expires_at" { type = string }
variable "availability_zones" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b"]
  validation {
    condition     = length(var.availability_zones) == 2
    error_message = "Exactly two selected AZs are required."
  }
}
variable "hosted_zone_id" { type = string }
variable "app_hostname" {
  type = string
  validation {
    condition     = can(regex("^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$", var.app_hostname)) && length(split(".", var.app_hostname)) >= 2
    error_message = "Use a controlled lowercase DNS hostname without a URL scheme or path."
  }
}
variable "auth_hostname" {
  type = string
  validation {
    condition     = can(regex("^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$", var.auth_hostname)) && length(split(".", var.auth_hostname)) >= 2 && var.auth_hostname != var.app_hostname
    error_message = "Use a distinct controlled lowercase authentication hostname."
  }
}
variable "ami_id" {
  type        = string
  description = "Verified Amazon Linux 2023 x86_64 AMI in the selected region. No latest-AMI lookup is performed."
  validation {
    condition     = can(regex("^ami-[a-f0-9]{8,17}$", var.ami_id))
    error_message = "Pass a verified regional AL2023 x86_64 AMI ID."
  }
}
variable "api_image" {
  type        = string
  description = "Pushed ECR API image built with the external HTTPS VITE_OIDC_URL."
  validation {
    condition     = can(regex("^[0-9]{12}\\.dkr\\.ecr\\.us-east-1\\.amazonaws\\.com/.+@sha256:[a-f0-9]{64}$", var.api_image))
    error_message = "Use an immutable regional ECR image digest."
  }
}
variable "worker_image" {
  type = string
  validation {
    condition     = can(regex("^[0-9]{12}\\.dkr\\.ecr\\.us-east-1\\.amazonaws\\.com/.+@sha256:[a-f0-9]{64}$", var.worker_image))
    error_message = "Use an immutable regional ECR image digest."
  }
}
variable "postgres_version" {
  type        = string
  description = "Exact regional PostgreSQL 18 version verified before planning."
  validation {
    condition     = can(regex("^18\\.[0-9]+$", var.postgres_version))
    error_message = "The profile requires a reviewed PostgreSQL 18 minor version."
  }
}
variable "enable_services" {
  type        = bool
  default     = false
  description = "Set true only after the one-off bootstrap task and identity readiness succeed."
}
variable "deletion_protection" {
  type    = bool
  default = true
}
variable "trace_sample_rate" {
  type        = number
  default     = 0.1
  description = "Default 10 percent sampling; use 1 only for a bounded trace evidence run."
  validation {
    condition     = var.trace_sample_rate >= 0 && var.trace_sample_rate <= 1
    error_message = "Trace sampling must be between 0 and 1."
  }
}

locals {
  ca_path        = "/certs/rds-ca.pem"
  ca_pem         = file("${path.module}/rds-us-east-1-bundle.pem")
  secret_names   = toset(["migrator", "api", "worker", "keycloak-db", "keycloak-admin", "demo-password", "keycloak-realm"])
  app_origin     = "https://${var.app_hostname}"
  auth_origin    = "https://${var.auth_hostname}"
  kafka_image    = "apache/kafka:4.2.1@sha256:2d2f77837385f202b1947fc3ed62421de344f0ced47dde360ca5afdad11b51fa"
  keycloak_image = "quay.io/keycloak/keycloak:26.7.3@sha256:e03b95891c214fba3ab72f12f40c983211549e817c5fce8d0f37761db04ae185"
}
