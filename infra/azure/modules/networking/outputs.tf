output "vnet_id" {
  value = azurerm_virtual_network.network.id
}

output "vnet_name" {
  value = azurerm_virtual_network.network.name
}

output "db_subnet_id" {
  value = azurerm_subnet.db_subnet.id
}

output "container_apps_subnet_id" {
  value = azurerm_subnet.container_apps_subnet.id
}
