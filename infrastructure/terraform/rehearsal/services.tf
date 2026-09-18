resource "aws_ecs_cluster" "main" { name = var.name }
resource "aws_service_discovery_private_dns_namespace" "main" {
  name = "${var.name}.internal"
  vpc  = aws_vpc.main.id
}
resource "aws_service_discovery_service" "application" {
  for_each = toset(["api", "worker"])
  name     = each.value
  dns_config {
    namespace_id   = aws_service_discovery_private_dns_namespace.main.id
    routing_policy = "MULTIVALUE"
    dns_records {
      ttl  = 10
      type = "A"
    }
  }
  health_check_custom_config { failure_threshold = 1 }
}
locals {
  logs = { logDriver = "awslogs", options = { awslogs-group = aws_cloudwatch_log_group.services.name, awslogs-region = var.region, awslogs-stream-prefix = "service" } }
  certificate_container = {
    name                   = "certificates", image = var.worker_image, essential = false, user = "0:0",
    readonlyRootFilesystem = true,
    linuxParameters        = { capabilities = { add = [], drop = ["ALL"] } },
    entryPoint             = ["python", "-c"],
    command                = ["import base64,os; from pathlib import Path; Path('${local.ca_path}').write_bytes(base64.b64decode('${base64encode(local.ca_pem)}')); os.chmod('${local.ca_path}',0o644); os.chmod('/tmp',0o1777)"],
    mountPoints            = [{ sourceVolume = "certificates", containerPath = "/certs", readOnly = false }, { sourceVolume = "temporary", containerPath = "/tmp", readOnly = false }],
    logConfiguration       = local.logs
  }
  common_environment = {
    AWS_REGION                  = var.region
    KAFKA_BOOTSTRAP_SERVERS     = "${aws_instance.auxiliary.private_ip}:29092"
    OTEL_EXPORTER_OTLP_ENDPOINT = "http://${aws_instance.auxiliary.private_ip}:4318"
    CASEFLOW_TRACE_SAMPLE_RATE  = tostring(var.trace_sample_rate)
  }
  environment = {
    api = merge(local.common_environment, {
      API_ADDRESS                     = "0.0.0.0", API_PORT = "8080",
      DB_URL                          = "jdbc:postgresql://${aws_db_instance.main.address}:5432/caseflow?sslmode=verify-full&sslrootcert=${local.ca_path}",
      OIDC_ISSUER                     = "${local.auth_origin}/realms/caseflow",
      OIDC_JWKS                       = "${local.auth_origin}/realms/caseflow/protocol/openid-connect/certs",
      CASEFLOW_STORAGE_ENDPOINT       = "", CASEFLOW_STORAGE_PUBLIC_ENDPOINT = "",
      CASEFLOW_STORAGE_BUCKET         = aws_s3_bucket.objects.id, CASEFLOW_STORAGE_REGION = var.region,
      MANAGEMENT_SERVER_ADDRESS       = "0.0.0.0", MANAGEMENT_SERVER_PORT = "9091",
      CASEFLOW_TRACING_EXPORT_ENABLED = "true", JAVA_TOOL_OPTIONS = "-XX:MaxRAMPercentage=65"
    })
    worker = merge(local.common_environment, {
      DB_HOST     = aws_db_instance.main.address, DB_PORT = "5432", DB_NAME = "caseflow",
      PGSSLMODE   = "verify-full", PGSSLROOTCERT = local.ca_path,
      S3_ENDPOINT = "", S3_BUCKET = aws_s3_bucket.objects.id, OTEL_TRACES_EXPORTER = "otlp"
    })
  }
  runtime_secrets = {
    api    = [{ name = "DB_API_PASSWORD", valueFrom = aws_secretsmanager_secret.runtime["api"].arn }, { name = "DB_MIGRATOR_PASSWORD", valueFrom = aws_secretsmanager_secret.runtime["migrator"].arn }]
    worker = [{ name = "DB_WORKER_PASSWORD", valueFrom = aws_secretsmanager_secret.runtime["worker"].arn }]
  }
}
resource "aws_ecs_task_definition" "application" {
  skip_destroy             = true # Retain immutable revisions for rollback; inventory them at teardown.
  for_each                 = toset(["api", "worker"])
  family                   = "${var.name}-${each.value}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.application[each.value].arn
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  volume { name = "certificates" }
  volume { name = "temporary" }
  container_definitions = jsonencode([local.certificate_container, {
    name             = each.value, image = each.value == "api" ? var.api_image : var.worker_image,
    essential        = true, user = "10001:10001", readonlyRootFilesystem = true,
    linuxParameters  = { capabilities = { add = [], drop = ["ALL"] } },
    environment      = [for name, value in local.environment[each.value] : { name = name, value = value }],
    secrets          = local.runtime_secrets[each.value],
    dependsOn        = [{ containerName = "certificates", condition = "SUCCESS" }],
    mountPoints      = [{ sourceVolume = "certificates", containerPath = "/certs", readOnly = true }, { sourceVolume = "temporary", containerPath = "/tmp", readOnly = false }],
    portMappings     = each.value == "api" ? [{ containerPort = 8080, hostPort = 8080, protocol = "tcp" }, { containerPort = 9091, hostPort = 9091, protocol = "tcp" }] : [{ containerPort = 8090, hostPort = 8090, protocol = "tcp" }],
    healthCheck      = { command = each.value == "api" ? ["CMD", "java", "-cp", "/app/probe", "HealthProbe"] : ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/health',timeout=3).read()"], interval = 15, timeout = 5, retries = 4, startPeriod = 60 },
    stopTimeout      = 90,
    logConfiguration = local.logs
  }])
}
resource "aws_ecs_service" "application" {
  for_each                           = toset(["api", "worker"])
  name                               = each.value
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.application[each.value].arn
  desired_count                      = var.enable_services ? 1 : 0
  launch_type                        = "FARGATE"
  health_check_grace_period_seconds  = each.value == "api" ? 180 : null
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.tasks.id]
    assign_public_ip = true
  }
  service_registries { registry_arn = aws_service_discovery_service.application[each.value].arn }
  dynamic "load_balancer" {
    for_each = each.value == "api" ? [1] : []
    content {
      target_group_arn = aws_lb_target_group.api.arn
      container_name   = "api"
      container_port   = 8080
    }
  }
  depends_on = [aws_lb_listener.https, aws_lb_listener_rule.api, aws_iam_role_policy.execution_secrets]
}
resource "aws_ecs_task_definition" "bootstrap" {
  skip_destroy             = true
  family                   = "${var.name}-bootstrap"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.bootstrap.arn
  volume { name = "temporary" }
  container_definitions = jsonencode([{
    name             = "bootstrap", image = var.worker_image, essential = true,
    entryPoint       = ["python", "-c"], command = [file("${path.module}/bootstrap.py")],
    user             = "0:0", readonlyRootFilesystem = true,
    linuxParameters  = { capabilities = { add = [], drop = ["ALL"] } },
    mountPoints      = [{ sourceVolume = "temporary", containerPath = "/tmp", readOnly = false }],
    environment      = [{ name = "AWS_REGION", value = var.region }, { name = "BOOTSTRAP_CONFIG", value = jsonencode({ region = var.region, ca = base64encode(local.ca_pem), database = aws_db_instance.main.address, master = aws_db_instance.main.master_user_secret[0].secret_arn, secrets = { for key, value in aws_secretsmanager_secret.runtime : key => value.arn }, app = local.app_origin }) }],
    logConfiguration = local.logs
  }])
}
