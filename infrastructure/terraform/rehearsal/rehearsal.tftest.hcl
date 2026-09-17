mock_provider "aws" {}

variables {
  account_id       = "123456789012"
  expires_at       = "2026-09-18T00:00:00Z"
  hosted_zone_id   = "Z0123456789EXAMPLE"
  app_hostname     = "caseflow.example.com"
  auth_hostname    = "auth.caseflow.example.com"
  ami_id           = "ami-0123456789abcdef0"
  postgres_version = "18.6"
  api_image        = "123456789012.dkr.ecr.us-east-1.amazonaws.com/caseflow/api@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  worker_image     = "123456789012.dkr.ecr.us-east-1.amazonaws.com/caseflow/worker@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
}

run "safe_rehearsal_defaults" {
  command = plan
  assert {
    condition     = aws_db_instance.main.instance_class == "db.t4g.micro" && aws_instance.auxiliary.instance_type == "m7i-flex.large"
    error_message = "Default rehearsal sizes must match the reviewed Free-plan instance selection."
  }
  assert {
    condition     = alltrue([for service in aws_ecs_service.application : service.desired_count == 0])
    error_message = "Application tasks must remain stopped until role/secret/identity bootstrap succeeds."
  }
  assert {
    condition     = aws_db_instance.main.publicly_accessible == false && aws_db_instance.main.deletion_protection && aws_db_instance.main.manage_master_user_password
    error_message = "The database must be private and protected, with its master credential managed outside Terraform."
  }
  assert {
    condition     = aws_s3_bucket.objects.force_destroy == false && aws_s3_bucket_public_access_block.objects.block_public_policy
    error_message = "Teardown must not silently delete objects or expose the bucket."
  }
  assert {
    condition     = length(aws_vpc_security_group_ingress_rule.https.cidr_ipv4) > 0 && aws_vpc_security_group_ingress_rule.https.from_port == 443 && aws_vpc_security_group_ingress_rule.https.to_port == 443
    error_message = "The public ingress rule must expose only HTTPS."
  }
  assert {
    condition     = local.environment.api.CASEFLOW_TRACE_SAMPLE_RATE == "0.1" && local.environment.worker.PGSSLMODE == "verify-full"
    error_message = "Cloud defaults must keep bounded sampling and hostname-verified worker database TLS."
  }
  assert {
    condition     = local.certificate_container.linuxParameters.capabilities.drop == ["ALL"]
    error_message = "Even the trusted certificate init process must drop Linux capabilities."
  }
}

run "invalid_sampling_is_rejected" {
  command = plan
  variables { trace_sample_rate = 1.1 }
  expect_failures = [var.trace_sample_rate]
}
