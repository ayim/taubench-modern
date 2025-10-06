output "blob_endpoint" {
  value = azurerm_storage_account.agent_files.primary_blob_endpoint
}

output "storage_account_id" {
  value = azurerm_storage_account.agent_files.id
}
