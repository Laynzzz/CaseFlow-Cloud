# Illustrative placeholders deliberately fail validation until reviewed inputs exist.
account_id          = "REPLACE_WITH_ACCOUNT_ID"
expires_at          = "REPLACE_WITH_APPROVED_SESSION_END_UTC"
hosted_zone_id      = "REPLACE_WITH_CONTROLLED_ROUTE53_ZONE"
app_hostname        = "caseflow.example.com"
auth_hostname       = "auth.caseflow.example.com"
ami_id              = "REPLACE_WITH_VERIFIED_AL2023_AMI"
postgres_version    = "18.6" # Confirm regional availability; this is not a verified RDS selection.
api_image           = "REPLACE_WITH_PUSHED_API_IMAGE_AT_SHA256"
worker_image        = "REPLACE_WITH_PUSHED_WORKER_IMAGE_AT_SHA256"
enable_services     = false
deletion_protection = true
