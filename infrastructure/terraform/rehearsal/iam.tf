locals {
  ecs_trust = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role" "execution" {
  name               = "${var.name}-execution"
  assume_role_policy = local.ecs_trust
}
resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}
resource "aws_iam_role_policy" "execution_secrets" {
  role   = aws_iam_role.execution.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = [for key in ["api", "worker", "migrator"] : aws_secretsmanager_secret.runtime[key].arn] }] })
}
resource "aws_iam_role" "application" {
  for_each           = toset(["api", "worker"])
  name               = "${var.name}-${each.key}"
  assume_role_policy = local.ecs_trust
}
resource "aws_iam_role_policy" "objects" {
  for_each = aws_iam_role.application
  role     = each.value.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["s3:GetObject", "s3:GetObjectVersion", "s3:PutObject"], Resource = "${aws_s3_bucket.objects.arn}/tenants/*" }
  ] })
}
resource "aws_iam_role" "bootstrap" {
  name               = "${var.name}-bootstrap"
  assume_role_policy = local.ecs_trust
}
// Manual cleanup is constrained to document objects; selected-object protection
// still comes from the cleanup command's locked database checks and If-Match.
resource "aws_iam_role_policy" "worker_cleanup" {
  role = aws_iam_role.application["worker"].id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["s3:ListBucket"], Resource = aws_s3_bucket.objects.arn,
    Condition = { StringLike = { "s3:prefix" = ["tenants/*/documents/*"] } } },
    { Effect = "Allow", Action = ["s3:DeleteObject"], Resource = "${aws_s3_bucket.objects.arn}/tenants/*/documents/*" }
  ] })
}
resource "aws_iam_role_policy" "bootstrap" {
  role = aws_iam_role.bootstrap.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = concat([aws_db_instance.main.master_user_secret[0].secret_arn], [for secret in aws_secretsmanager_secret.runtime : secret.arn]) },
    { Effect = "Allow", Action = ["secretsmanager:PutSecretValue"], Resource = [for secret in aws_secretsmanager_secret.runtime : secret.arn] }
  ] })
}
resource "aws_iam_role" "auxiliary" {
  name               = "${var.name}-auxiliary"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.auxiliary.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
resource "aws_iam_role_policy" "auxiliary_secrets" {
  role   = aws_iam_role.auxiliary.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = [for key in ["keycloak-db", "keycloak-admin", "keycloak-realm"] : aws_secretsmanager_secret.runtime[key].arn] }] })
}
resource "aws_iam_instance_profile" "auxiliary" {
  name = var.name
  role = aws_iam_role.auxiliary.name
}
