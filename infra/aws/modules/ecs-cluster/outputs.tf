output "ecs_task_execution_role_arn" {
  value = aws_iam_role.ecs_execution_role.arn
}

output "ecs_task_role_arn" {
  value = aws_iam_role.ecs_task_role.arn
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.ecs_cluster.name
}
