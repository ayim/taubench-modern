resource "aws_secretsmanager_secret" "auth-configuration" {
  name        = "auth-configuration-${var.infra_id}"
  description = "Auth configuration and secrets for ${var.infra_id}"
  kms_key_id  = var.encryption_key_arn
}

resource "tls_private_key" "jwt_private_key" {
  algorithm   = "ECDSA"
  ecdsa_curve = "P256"
}

resource "random_password" "session_secret" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret_version" "auth-configuration" {
  secret_id = aws_secretsmanager_secret.auth-configuration.id
  secret_string = jsonencode({
    _informative_oidc_client_url = "REPLACE_ME with a link to OIDC client configuration (e.g. https://console.cloud.google.com/auth/clients/xxx, *informative*)"

    oidc_client_id      = "REPLACE_ME_WITH_OIDC_CLIENT_ID"
    oidc_client_secret  = "REPLACE_ME_WITH_OIDC_CLIENT_SECRET"
    oidc_server         = "REPLACE_ME_WITH_OIDC_SERVER_URL"
    session_secret      = random_password.session_secret.result
    jwt_private_key_b64 = base64encode(tls_private_key.jwt_private_key.private_key_pem)
    jwt_public_key_b64  = base64encode(tls_private_key.jwt_private_key.public_key_pem)
  })
  lifecycle {
    ignore_changes = [secret_string]
  }
}
