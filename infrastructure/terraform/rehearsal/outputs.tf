output "app_url" { value = local.app_origin }
output "oidc_issuer" { value = "${local.auth_origin}/realms/caseflow" }
output "repositories" { value = { for key, repo in aws_ecr_repository.app : key => repo.repository_url } }
output "cluster" { value = aws_ecs_cluster.main.name }
output "bootstrap_task_definition" { value = aws_ecs_task_definition.bootstrap.arn }
output "network_configuration" {
  value = { awsvpcConfiguration = { subnets = aws_subnet.public[*].id, securityGroups = [aws_security_group.tasks.id], assignPublicIp = "ENABLED" } }
}
output "auxiliary_instance_id" { value = aws_instance.auxiliary.id }
output "retained_resources" {
  value = {
    database    = aws_db_instance.main.id
    objects     = aws_s3_bucket.objects.id
    data_volume = aws_ebs_volume.auxiliary.id
    secrets     = { for key, secret in aws_secretsmanager_secret.runtime : key => secret.arn }
    logs        = aws_cloudwatch_log_group.services.name
  }
}
