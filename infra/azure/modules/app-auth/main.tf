resource "random_password" "session_secret" {
  length  = 32
  special = false
}

resource "azurerm_key_vault_secret" "session_secret" {
  name         = "session-secret"
  value        = random_password.session_secret.result
  key_vault_id = var.key_vault_id
}

resource "azurerm_key_vault_secret" "oidc_client_id" {
  name         = "oidc-client-id"
  value        = "REPLACE_ME_WITH_OIDC_CLIENT_ID"
  key_vault_id = var.key_vault_id
  lifecycle {
    ignore_changes = [value]
  }
}

resource "azurerm_key_vault_secret" "oidc_client_secret" {
  name         = "oidc-client-secret"
  value        = "REPLACE_ME_WITH_OIDC_CLIENT_SECRET"
  key_vault_id = var.key_vault_id
  lifecycle {
    ignore_changes = [value]
  }
}

resource "azurerm_key_vault_secret" "oidc_server" {
  name         = "oidc-server"
  value        = "REPLACE_ME_WITH_OIDC_SERVER_URL"
  key_vault_id = var.key_vault_id
  lifecycle {
    ignore_changes = [value]
  }
}
