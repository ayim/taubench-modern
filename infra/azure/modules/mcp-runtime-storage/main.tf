data "azurerm_storage_account" "storage_account" {
  name                = var.storage_account_name
  resource_group_name = var.resource_group_name
}

resource "azurerm_storage_share" "mcp_runtime_data" {
  name               = "mcp-runtime-data"
  storage_account_id = data.azurerm_storage_account.storage_account.id
  quota              = 50 # GB
}

resource "azurerm_container_app_environment_storage" "mcp_runtime" {
  name                         = "mcp-runtime-storage"
  container_app_environment_id = var.container_app_environment_id
  account_name                 = var.storage_account_name
  share_name                   = azurerm_storage_share.mcp_runtime_data.name
  access_key                   = data.azurerm_storage_account.storage_account.primary_access_key
  access_mode                  = "ReadWrite"
}
