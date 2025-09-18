output "auth_configuration_secret_arn" {
  value = aws_secretsmanager_secret.auth-configuration.arn
}
