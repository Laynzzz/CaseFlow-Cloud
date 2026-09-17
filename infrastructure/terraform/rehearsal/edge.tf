resource "aws_acm_certificate" "main" {
  domain_name               = var.app_hostname
  subject_alternative_names = [var.auth_hostname]
  validation_method         = "DNS"
  lifecycle { create_before_destroy = true }
}
resource "aws_route53_record" "certificate" {
  for_each = toset([var.app_hostname, var.auth_hostname])
  zone_id  = var.hosted_zone_id
  name     = one([for option in aws_acm_certificate.main.domain_validation_options : option.resource_record_name if option.domain_name == each.value])
  type     = one([for option in aws_acm_certificate.main.domain_validation_options : option.resource_record_type if option.domain_name == each.value])
  records  = [one([for option in aws_acm_certificate.main.domain_validation_options : option.resource_record_value if option.domain_name == each.value])]
  ttl      = 60
}
resource "aws_acm_certificate_validation" "main" {
  certificate_arn         = aws_acm_certificate.main.arn
  validation_record_fqdns = [for record in aws_route53_record.certificate : record.fqdn]
}
resource "aws_lb" "main" {
  name                       = var.name
  internal                   = false
  load_balancer_type         = "application"
  security_groups            = [aws_security_group.edge.id]
  subnets                    = aws_subnet.public[*].id
  drop_invalid_header_fields = true
  enable_deletion_protection = var.deletion_protection
}
resource "aws_lb_target_group" "api" {
  name        = "${var.name}-api"
  port        = 8080
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id
  health_check {
    path                = "/api/v1/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 15
  }
}
resource "aws_lb_target_group" "identity" {
  name     = "${var.name}-oidc"
  port     = 8080
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id
  health_check { path = "/realms/caseflow/.well-known/openid-configuration" }
}
resource "aws_lb_target_group_attachment" "identity" {
  target_group_arn = aws_lb_target_group.identity.arn
  target_id        = aws_instance.auxiliary.id
  port             = 8080
}
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate_validation.main.certificate_arn
  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      status_code  = "404"
      message_body = "Not found"
    }
  }
}
resource "aws_lb_listener_rule" "api" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 20
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
  condition {
    host_header {
      values = [var.app_hostname]
    }
  }
}
resource "aws_lb_listener_rule" "identity" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 10
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.identity.arn
  }
  condition {
    host_header {
      values = [var.auth_hostname]
    }
  }
  condition {
    path_pattern {
      values = ["/realms/caseflow/*", "/resources/*"]
    }
  }
}
resource "aws_route53_record" "hosts" {
  for_each = toset([var.app_hostname, var.auth_hostname])
  zone_id  = var.hosted_zone_id
  name     = each.value
  type     = "A"
  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}
