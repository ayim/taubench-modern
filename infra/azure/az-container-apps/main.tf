locals {
  resource_group_name     = azurerm_resource_group.team_edition.name
  resource_group_location = azurerm_resource_group.team_edition.location
}

data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "team_edition" {
  name     = "team-edition-${var.infra_id}"
  location = var.infra_location
}

resource "azurerm_log_analytics_workspace" "team_edition" {
  name                = "logs-${var.infra_id}"
  location            = local.resource_group_location
  resource_group_name = local.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = 30 # days, this is the minimum retention allowed
}

resource "azurerm_container_app_environment" "team_edition" {
  name                       = "app-${var.infra_id}"
  location                   = azurerm_resource_group.team_edition.location
  resource_group_name        = local.resource_group_name
  logs_destination           = "log-analytics"
  log_analytics_workspace_id = azurerm_log_analytics_workspace.team_edition.id
  infrastructure_subnet_id   = module.networking.container_apps_subnet_id

  workload_profile {
    name                  = "main"
    workload_profile_type = "D8"

    minimum_count = 1
    maximum_count = 3
  }

  identity {
    type = "SystemAssigned"
  }
}

# User Assigned Identity for Application
resource "azurerm_user_assigned_identity" "app_identity" {
  name                = "container-app-identity"
  resource_group_name = local.resource_group_name
  location            = local.resource_group_location
}

# Key Vault for Application
resource "azurerm_key_vault" "team_edition" {
  name                = "kv-${var.infra_id}"
  location            = local.resource_group_location
  resource_group_name = local.resource_group_name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  access_policy {
    tenant_id = data.azurerm_client_config.current.tenant_id
    object_id = var.key_vault_administrators_object_id

    secret_permissions = ["Get", "List", "Set", "Delete", "Purge"]
  }

  access_policy {
    # Allow app UAI to read secrets
    tenant_id = data.azurerm_client_config.current.tenant_id
    object_id = azurerm_user_assigned_identity.app_identity.principal_id

    secret_permissions = ["Get", "List"]
  }
}

resource "azurerm_key_vault_secret" "uai_client_id" {
  name  = "uai-client-id"
  value = azurerm_user_assigned_identity.app_identity.client_id

  key_vault_id = azurerm_key_vault.team_edition.id
}

# Grant ACR registry pull access for app UAI
resource "azurerm_role_assignment" "acr_pull" {
  scope                = module.container-registry.acr_registry_id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.app_identity.principal_id
}

module "networking" {
  source = "../modules/networking"

  infra_id                = var.infra_id
  resource_group_name     = local.resource_group_name
  resource_group_location = local.resource_group_location
}

module "az-flexible-pg" {
  source = "../modules/az-flexible-pg"

  infra_id                = var.infra_id
  resource_group_name     = local.resource_group_name
  resource_group_location = local.resource_group_location

  db_subnet_id = module.networking.db_subnet_id
  vnet_id      = module.networking.vnet_id
  key_vault_id = azurerm_key_vault.team_edition.id
}

module "container-registry" {
  source = "../modules/container-registry"

  infra_id                = var.infra_id
  resource_group_name     = local.resource_group_name
  resource_group_location = local.resource_group_location

  app_environment_principal_id = azurerm_container_app_environment.team_edition.identity[0].principal_id
}

module "app-auth" {
  source = "../modules/app-auth"

  key_vault_id = azurerm_key_vault.team_edition.id
}

module "agent-files-storage" {
  source = "../modules/agent-files-storage"

  container_apps_subnet_id = module.networking.container_apps_subnet_id
  infra_id                 = var.infra_id
  key_vault_id             = azurerm_key_vault.team_edition.id
  resource_group_name      = local.resource_group_name
  resource_group_location  = local.resource_group_location
  vnet_id                  = module.networking.vnet_id
}

resource "azurerm_role_assignment" "agent_files_contributor" {
  scope                = module.agent-files-storage.storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.app_identity.principal_id
}

resource "azurerm_role_assignment" "agent_files_smb_contributor" {
  scope                = module.agent-files-storage.storage_account_id
  role_definition_name = "Storage File Data SMB Share Contributor"
  principal_id         = azurerm_user_assigned_identity.app_identity.principal_id
}
