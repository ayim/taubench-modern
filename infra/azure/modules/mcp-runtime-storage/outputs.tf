output "mcp_runtime_storage_name" {
  description = "Name of the MCP Runtime storage mount for Container Apps"
  value       = azurerm_container_app_environment_storage.mcp_runtime.name
}
