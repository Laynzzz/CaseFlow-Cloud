resource "aws_vpc" "main" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
}
resource "aws_internet_gateway" "main" { vpc_id = aws_vpc.main.id }
resource "aws_subnet" "public" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.42.${count.index + 1}.0/24"
  availability_zone = var.availability_zones[count.index]
}
resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.42.${count.index + 11}.0/24"
  availability_zone = var.availability_zones[count.index]
}
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
}
resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}
resource "aws_security_group" "edge" {
  name   = "${var.name}-edge"
  vpc_id = aws_vpc.main.id
}
resource "aws_security_group" "tasks" {
  name   = "${var.name}-tasks"
  vpc_id = aws_vpc.main.id
}
resource "aws_security_group" "auxiliary" {
  name   = "${var.name}-auxiliary"
  vpc_id = aws_vpc.main.id
}
resource "aws_security_group" "database" {
  name   = "${var.name}-database"
  vpc_id = aws_vpc.main.id
}
resource "aws_vpc_security_group_ingress_rule" "https" {
  security_group_id = aws_security_group.edge.id
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"
}
resource "aws_vpc_security_group_ingress_rule" "api" {
  security_group_id            = aws_security_group.tasks.id
  referenced_security_group_id = aws_security_group.edge.id
  from_port                    = 8080
  to_port                      = 8080
  ip_protocol                  = "tcp"
}
resource "aws_vpc_security_group_ingress_rule" "identity" {
  security_group_id            = aws_security_group.auxiliary.id
  referenced_security_group_id = aws_security_group.edge.id
  from_port                    = 8080
  to_port                      = 8080
  ip_protocol                  = "tcp"
}
resource "aws_vpc_security_group_ingress_rule" "internal_auxiliary" {
  for_each                     = toset(["29092", "4318"])
  security_group_id            = aws_security_group.auxiliary.id
  referenced_security_group_id = aws_security_group.tasks.id
  from_port                    = tonumber(each.value)
  to_port                      = tonumber(each.value)
  ip_protocol                  = "tcp"
}
resource "aws_vpc_security_group_ingress_rule" "metrics" {
  for_each                     = toset(["9091", "8090"])
  security_group_id            = aws_security_group.tasks.id
  referenced_security_group_id = aws_security_group.auxiliary.id
  from_port                    = tonumber(each.value)
  to_port                      = tonumber(each.value)
  ip_protocol                  = "tcp"
}
resource "aws_vpc_security_group_ingress_rule" "database" {
  for_each                     = { tasks = aws_security_group.tasks.id, auxiliary = aws_security_group.auxiliary.id }
  security_group_id            = aws_security_group.database.id
  referenced_security_group_id = each.value
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}
resource "aws_vpc_security_group_egress_rule" "outbound" {
  for_each          = { edge = aws_security_group.edge.id, tasks = aws_security_group.tasks.id, auxiliary = aws_security_group.auxiliary.id }
  security_group_id = each.value
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}
