# Application VNet
resource "azurerm_virtual_network" "network" {
  name                = "${var.infra_id}-vnet"
  resource_group_name = var.resource_group_name
  location            = var.resource_group_location
  address_space       = ["10.0.0.0/16"]
}

# VNet Subnet for the Postgres Database Server
resource "azurerm_subnet" "db_subnet" {
  name                 = "${var.infra_id}-db-sn"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.network.name
  address_prefixes     = ["10.0.2.0/24"]
  service_endpoints    = ["Microsoft.Storage"]

  delegation {
    name = "fs"
    service_delegation {
      name = "Microsoft.DBforPostgreSQL/flexibleServers"
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/join/action",
      ]
    }
  }
}

# VNet Subnet for Application Containers
resource "azurerm_subnet" "container_apps_subnet" {
  name                 = "${var.infra_id}-containerapp-sn"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.network.name
  address_prefixes     = ["10.0.8.0/21"] # The Subnet must have a /21 or larger address space.
  service_endpoints    = ["Microsoft.Storage"]

  delegation {
    name = "container_app_environment"
    service_delegation {
      name = "Microsoft.App/environments"
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/join/action",
      ]
    }
  }
}
