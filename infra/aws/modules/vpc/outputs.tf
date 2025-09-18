output "private_subnet_ids" {
  value = [for subnet in aws_subnet.private_subnets : subnet.id]
}

output "public_subnet_ids" {
  value = [for subnet in aws_subnet.public_subnets : subnet.id]
}

output "default_security_group" {
  value = aws_default_security_group.default.id
}

output "vpc_id" {
  value = aws_vpc.vpc.id
}
