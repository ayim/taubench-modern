locals {
  db_username = "s4admin"
  db_password = random_password.administrator_password.result
}

data "azurerm_client_config" "current" {}

# Database Server
resource "azurerm_postgresql_flexible_server" "postgres" {
  name                = "postgres-${var.infra_id}"
  version             = "16"
  resource_group_name = var.resource_group_name
  location            = var.resource_group_location
  zone                = "1"

  # The provided subnet should not have any other resource deployed in it and
  # this subnet will be delegated to the PostgreSQL Flexible Server, if not
  # already delegated
  delegated_subnet_id = var.db_subnet_id
  private_dns_zone_id = azurerm_private_dns_zone.dns_zone.id

  public_network_access_enabled = false
  administrator_login           = local.db_username
  administrator_password        = local.db_password

  storage_mb   = 32768
  storage_tier = "P4"
  sku_name     = "B_Standard_B1ms"
}

resource "azurerm_postgresql_flexible_server_configuration" "extensions" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.postgres.id
  value     = "UUID-OSSP" # Team Edition requires the Postgres UUID extension
}

# Networking
resource "azurerm_private_dns_zone" "dns_zone" {
  name                = "${var.infra_id}.postgres.database.azure.com"
  resource_group_name = var.resource_group_name
}

resource "azurerm_private_dns_zone_virtual_network_link" "dns_zone" {
  name                  = "${var.infra_id}-vnet-link"
  resource_group_name   = var.resource_group_name
  virtual_network_id    = var.vnet_id
  private_dns_zone_name = azurerm_private_dns_zone.dns_zone.name
}

# Secrets
resource "random_password" "administrator_password" {
  length  = 32
  special = false
}

resource "azurerm_key_vault_secret" "db_host" {
  name  = "db-host"
  value = azurerm_postgresql_flexible_server.postgres.fqdn

  key_vault_id = var.key_vault_id
}

resource "azurerm_key_vault_secret" "db_port" {
  name  = "db-port"
  value = "5432"

  key_vault_id = var.key_vault_id
}

resource "azurerm_key_vault_secret" "db_username" {
  name  = "db-username"
  value = local.db_username

  key_vault_id = var.key_vault_id
}

resource "azurerm_key_vault_secret" "db_password" {
  name  = "db-password"
  value = local.db_password

  key_vault_id = var.key_vault_id
}
