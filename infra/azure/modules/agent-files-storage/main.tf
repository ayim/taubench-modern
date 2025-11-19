#region Storage
resource "azurerm_storage_account" "agent_files" {
  name                     = substr("${var.infra_id}agentfiles", 0, 24)
  resource_group_name      = var.resource_group_name
  location                 = var.resource_group_location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  allow_nested_items_to_be_public   = false
  infrastructure_encryption_enabled = true

  blob_properties {
    versioning_enabled = false
  }
}

resource "azurerm_storage_container" "agent_files" {
  name                  = "${var.infra_id}-agent-files"
  storage_account_id    = azurerm_storage_account.agent_files.id
  container_access_type = "private"
}

resource "azurerm_storage_account_network_rules" "agent_files" {
  storage_account_id = azurerm_storage_account.agent_files.id

  default_action             = "Deny"
  bypass                     = ["AzureServices"]
  virtual_network_subnet_ids = [var.container_apps_subnet_id]
}
#endregion

#region Secrets
resource "azurerm_key_vault_secret" "storage_account_name" {
  name  = "storage-account-name"
  value = azurerm_storage_account.agent_files.name

  key_vault_id = var.key_vault_id
}

resource "azurerm_key_vault_secret" "storage_container_name" {
  name  = "storage-container-name"
  value = azurerm_storage_container.agent_files.name

  key_vault_id = var.key_vault_id
}
#endregion
