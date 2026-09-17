locals {
  monitoring_images = { for name in ["otel-collector", "prometheus", "tempo", "grafana"] : name => yamldecode(file("${path.module}/../../../compose.observability.yaml")).services[name].image }
  monitoring_files = merge({
    "collector.yaml"  = file("${path.module}/../../observability/collector.yaml")
    "prometheus.yaml" = replace(replace(replace(file("${path.module}/../../observability/prometheus.yaml"), "api:9091", "api.${var.name}.internal:9091"), "worker:8090", "worker.${var.name}.internal:8090"), "local-release", "aws-rehearsal")
    "alerts.yaml"     = file("${path.module}/../../observability/alerts.yaml")
    "tempo.yaml"      = file("${path.module}/../../observability/tempo.yaml")
  }, { for relative_file in fileset("${path.module}/../../observability/grafana", "**") : "grafana/${relative_file}" => file("${path.module}/../../observability/grafana/${relative_file}") })
}
resource "aws_ebs_volume" "auxiliary" {
  availability_zone = var.availability_zones[0]
  size              = 30
  type              = "gp3"
  encrypted         = true
  lifecycle { prevent_destroy = true }
}
resource "aws_instance" "auxiliary" {
  ami                         = var.ami_id
  instance_type               = "t3.large"
  subnet_id                   = aws_subnet.public[0].id
  private_ip                  = "10.42.1.10"
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.auxiliary.id]
  iam_instance_profile        = aws_iam_instance_profile.auxiliary.name
  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
  root_block_device {
    volume_size = 8
    volume_type = "gp3"
    encrypted   = true
  }
  user_data_base64 = base64gzip(templatefile("${path.module}/auxiliary.sh.tftpl", {
    region            = var.region, volume_serial = replace(aws_ebs_volume.auxiliary.id, "-", ""),
    ca_base64         = base64encode(local.ca_pem), database = aws_db_instance.main.address,
    auth_origin       = local.auth_origin, private_ip = "10.42.1.10",
    kafka_image       = local.kafka_image, keycloak_image = local.keycloak_image,
    secrets           = { for key in ["keycloak-db", "keycloak-admin", "keycloak-realm"] : key => aws_secretsmanager_secret.runtime[key].arn },
    monitoring_images = local.monitoring_images,
    monitoring_files  = { for name, content in local.monitoring_files : name => base64encode(content) }
  }))
  user_data_replace_on_change = true
  depends_on                  = [aws_iam_role_policy.auxiliary_secrets, aws_route_table_association.public]
}
resource "aws_volume_attachment" "auxiliary" {
  device_name = "/dev/sdf"
  volume_id   = aws_ebs_volume.auxiliary.id
  instance_id = aws_instance.auxiliary.id
}
