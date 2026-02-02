output "postgres_version" {
  value = aws_rds_cluster.cluster.engine_version
}

output "cluster_credentials_secret_arn" {
  value = aws_secretsmanager_secret.moonraker-db-credentials[0].arn
}

output "cluster_credentials" {
  value = {
    cluster_name = aws_rds_cluster.cluster.id
    username     = local.cluster_username
    password     = local.cluster_password
    host         = aws_rds_cluster.cluster.endpoint
    port         = aws_rds_cluster.cluster.port
    ro_host      = aws_rds_cluster.cluster.reader_endpoint
  }
}

output "configuration_report" {
  value = {
    minCapacity   = aws_rds_cluster.cluster.serverlessv2_scaling_configuration[0].min_capacity
    maxCapacity   = aws_rds_cluster.cluster.serverlessv2_scaling_configuration[0].max_capacity
    instanceCount = length(aws_rds_cluster_instance.serverless)
  }
}
