provider "azurerm" {
  features {
    # Use Azure CLI authentication
  }

  subscription_id = var.subscription_id
}
