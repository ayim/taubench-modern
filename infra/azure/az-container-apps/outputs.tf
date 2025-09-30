output "vnet_name" {
  value = module.networking.vnet_name
}

output "key_vault_uri" {
  value = azurerm_key_vault.team_edition.vault_uri
}

output "acr_login_server" {
  value = module.container-registry.acr_login_server
}

output "app_environment_id" {
  value = azurerm_container_app_environment.team_edition.id
}

output "resource_group_name" {
  value = local.resource_group_name
}

output "app_uai" {
  value = azurerm_user_assigned_identity.app_identity.id
}
