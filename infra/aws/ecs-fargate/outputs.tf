output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

output "route53_dns_servers" {
  description = "Route53 DNS servers for the hosted zone"
  value       = aws_route53_zone.main.name_servers
}

output "ecs_task_execution_role_arn" {
  value = module.ecs-cluster.ecs_task_execution_role_arn
}

output "ecs_task_role_arn" {
  value = module.ecs-cluster.ecs_task_role_arn
}

output "ecs_task_cluster_name" {
  value = module.ecs-cluster.ecs_cluster_name
}

output "private_subnet_ids" {
  value = module.vpc.private_subnet_ids
}

output "default_security_group" {
  value = module.vpc.default_security_group
}

output "alb_targets_security_group_id" {
  value = module.alb.alb_targets_security_group_id
}

output "rds_cluster_credentials_secret_arn" {
  value = module.postgres.cluster_credentials_secret_arn
}

output "alb_target_group_arn" {
  value = module.alb.alb_target_group_arn
}
