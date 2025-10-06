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

  default_action = "Deny"
  bypass         = ["AzureServices"]
}
#endregion

#region Private Access
resource "azurerm_private_dns_zone" "app" {
  name                = "privatelink.blob.core.windows.net"
  resource_group_name = var.resource_group_name
}

resource "azurerm_private_dns_zone_virtual_network_link" "app" {
  name                  = "${var.infra_id}-blob-vnet-link"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.app.name
  virtual_network_id    = var.vnet_id
}

# Using the private DNS zone and privatelink name, we explicitly override
# the privatelink domain for Azure blob storage so that our container apps
# will implicitly start to route privately to the private endpoint below.
# This is a documented Azure method, and they provide the target DNS zones
# here:
#   https://learn.microsoft.com/en-us/azure/private-link/private-endpoint-dns#storage

resource "azurerm_private_endpoint" "storage" {
  name                = "${var.infra_id}-storage-private-endpoint"
  location            = var.resource_group_location
  resource_group_name = var.resource_group_name
  subnet_id           = var.container_apps_subnet_id

  private_service_connection {
    name                           = "${var.infra_id}-storage-connection"
    private_connection_resource_id = azurerm_storage_account.agent_files.id
    subresource_names              = ["blob"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "${var.infra_id}-blob-dns-zone-group"
    private_dns_zone_ids = [azurerm_private_dns_zone.app.id]
  }
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
