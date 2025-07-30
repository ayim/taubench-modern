package common

import (
	"maps"
	"os"
	"path/filepath"
	"slices"
)

// === GET REGISTRY SERVERS ===

// MergeDockerCatalogs merges the catalog.yaml files from the given paths into a embedded catalog.yaml file
func MergeDockerCatalogs(catalogPath *string) (*DockerCatalog, error) {
	if catalogPath == nil {
		return DockerParseEmbeddedCatalogYAML()
	}
	newCatalog, err := DockerParseCatalogYAML(*catalogPath)
	if err != nil {
		return DockerParseEmbeddedCatalogYAML()
	}
	catalog, err := DockerParseEmbeddedCatalogYAML()
	if err != nil {
		return nil, err
	}
	mergedCatalog := &DockerCatalog{
		Version:                      catalog.Version,
		Name:                         catalog.Name,
		DisplayName:                  catalog.DisplayName,
		Registry:                     catalog.Registry,
		Sema4DockerCompatibleVersion: catalog.Sema4DockerCompatibleVersion,
		Sema4DockerCompatibleBuild:   catalog.Sema4DockerCompatibleBuild,
	}
	if newCatalog.Registry != nil {
		for serverName, server := range newCatalog.Registry {
			mergedCatalog.Registry[serverName] = server
		}
	}
	return mergedCatalog, nil
}

// DockerGetRegistryServers reads the registry.yaml file using ParseRegistryYAML and returns a slice of server names (keys in the registry).
func DockerGetRegistryServers() ([]string, error) {
	regFile, err := DockerParseRegistryYAML()
	if err != nil {
		return nil, err
	}
	if regFile == nil || regFile.Registry == nil {
		return nil, nil
	}

	servers := make([]string, 0, len(regFile.Registry))
	for k := range regFile.Registry {
		servers = append(servers, k)
	}
	return servers, nil
}

// GetCatalogDataForServers reads the catalog.yaml file using ParseEmbeddedCatalogYAML and returns a map of server name to its catalog data,
// but only for the servers present in the provided serverNames slice.
func DockerGetCatalogDataForServers(serverNames []string, catalogPath *string) (DockerCatalogRegistryEntries, error) {
	mergedCatalog, err := MergeDockerCatalogs(catalogPath)
	if err != nil {
		return nil, err
	}

	result := make(DockerCatalogRegistryEntries)
	for _, name := range serverNames {
		if entry, ok := mergedCatalog.Registry[name]; ok {
			result[name] = entry
		}
	}

	return result, nil
}

// DockerGetRegistryCatalogData is a convenience function that reads the registry and catalog files,
// and returns a map of server name to its catalog data for all servers in the registry.
func DockerGetRegistryCatalogData(catalogPath *string) (DockerCatalogRegistryEntries, error) {
	servers, err := DockerGetRegistryServers()
	if err != nil {
		return nil, err
	}
	return DockerGetCatalogDataForServers(servers, catalogPath)
}

// === CHECKERS ===

// Extracts the MCP_DOCKER entry from a list of AgentPackageMcpServer
// IsDockerMcpGateway returns true if the given SpecMcpServer represents a docker MCP gateway entry.
func IsDockerMcpGateway(mcp *AgentPackageMcpServer) bool {
	// The "docker" entry is identified by Command == "docker" and Arguments is empty or nil.
	return mcp != nil && mcp.Command == "docker" && (len(mcp.Arguments) >= 2) && mcp.Arguments[0] == "mcp" && mcp.Arguments[1] == "gateway" && mcp.Arguments[2] == "run"
}

// === MAPPERS ===

// CheckDockerRegistryDifferences compares the Docker MCP Gateway configuration in the Agent Project
// with the configuration in the deployed agent (from the Docker registry) and returns a list of differences.
func CheckDockerRegistryDifferences(dmg *SpecDockerMcpGateway, agentPackagePath string) (DockerMcpGatewayChanges, error) {
	var differences DockerMcpGatewayChanges

	// If the Docker MCP Gateway is not defined in the Agent Project, we shouldn't check for differences
	if dmg == nil {
		return differences, nil
	}

	// Check if the agent package path exists - if not, there's no local config to compare against
	if _, err := os.Stat(agentPackagePath); os.IsNotExist(err) {
		return differences, nil
	}

	// Use ExtractDockerMcpGatewayFromRegistry to get the deployed Docker MCP Gateway config
	var catalogPath *string
	if dmg.Catalog != nil {
		catalogPath = Ptr(filepath.Join(agentPackagePath, *dmg.Catalog))
	}
	localDockerMcpGateway, err := ExtractDockerMcpGatewayToAgentPackage(catalogPath)
	if err != nil || localDockerMcpGateway == nil {
		return differences, nil
	}

	// Compare Servers (by name and tools)
	specServers := dmg.Servers

	// Check for missing or extra servers
	for name := range specServers {
		if _, ok := localDockerMcpGateway.Servers[name]; !ok {
			differences = append(differences, "server."+name)
		}
	}

	// Compare server details for servers present in both
	for name := range specServers {
		specDockerServer, specOk := specServers[name]
		localDockerServer, localOk := localDockerMcpGateway.Servers[name]
		if specOk && localOk && specDockerServer.Tools != nil && localDockerServer.Tools != nil {
			// Compare tools (as sets)
			localDockerTools := make([]string, len(localDockerServer.Tools))
			for i, t := range localDockerServer.Tools {
				localDockerTools[i] = t.Name
			}
			// Check for missing or extra tools
			for _, t := range specDockerServer.Tools {
				if !slices.Contains(localDockerTools, t) {
					differences = append(differences, "server."+name+".tools."+t)
				}
			}
		}
	}

	return differences, nil
}

// ToAgentPackageDockerMcpGateway converts a SpecDockerMcpGateway to an AgentPackageDockerMcpGateway.
func ToAgentPackageDockerMcpGateway(dockerMcpGatewaySpec *SpecDockerMcpGateway) (*AgentPackageDockerMcpGateway, error) {
	if dockerMcpGatewaySpec == nil {
		return nil, nil
	}

	// Attempt to load catalog data for all servers in the spec
	serverNames := slices.Collect(maps.Keys(dockerMcpGatewaySpec.Servers))
	catalogEntries, err := DockerGetCatalogDataForServers(serverNames, dockerMcpGatewaySpec.Catalog)
	if err != nil {
		return nil, err
	}

	servers := make(map[string]DockerCatalogRegistry, len(dockerMcpGatewaySpec.Servers))
	for name, specServer := range dockerMcpGatewaySpec.Servers {
		regServerEntry, ok := catalogEntries[name]
		if !ok {
			continue
		}

		// Considering all tools as default
		tools := []DockerCatalogTool{}
		// Selecting only the specified tools
		if len(specServer.Tools) > 0 {
			for _, t := range regServerEntry.Tools {
				if ok := slices.Contains(specServer.Tools, t.Name); ok {
					tools = append(tools, t)
				}
			}
		} else {
			tools = regServerEntry.Tools
		}
		// Replace the tools in the registry entry with the selected ones (only those should be available)
		regServerEntry.Tools = tools

		// Assign the new entry
		servers[name] = regServerEntry
	}

	return &AgentPackageDockerMcpGateway{
		Catalog: dockerMcpGatewaySpec.Catalog,
		Servers: servers,
	}, nil
}

// ExtractDockerMcpGatewayToAgentPackage extracts the Docker MCP Gateway from the registry.yaml + catalog.yaml files
// and returns an AgentPackageDockerMcpGateway
func ExtractDockerMcpGatewayToAgentPackage(catalogPath *string) (*AgentPackageDockerMcpGateway, error) {
	// Get the registry from the registry.yaml file
	registry, err := DockerGetRegistryCatalogData(catalogPath)
	if err != nil {
		return nil, err
	}

	return &AgentPackageDockerMcpGateway{
		Catalog: catalogPath,
		Servers: registry,
	}, nil
}

// ExtractDockerMcpGatewayToSpec extracts the Docker MCP Gateway from the registry.yaml + catalog.yaml files
// and returns a SpecDockerMcpGateway
func ExtractDockerMcpGatewayToSpec(catalogPath *string) (*SpecDockerMcpGateway, error) {
	// Get the registry from the registry.yaml file
	registry, err := DockerGetRegistryCatalogData(catalogPath)
	if err != nil {
		return nil, err
	}
	// Get the catalog data for all servers in the registry
	servers := make(map[string]SpecDockerMcpServer, len(registry))
	for name := range registry {
		// Use the entry as is, since it already contains the tools and other metadata
		servers[name] = SpecDockerMcpServer{}
	}
	return &SpecDockerMcpGateway{
		Catalog: catalogPath,
		Servers: servers,
	}, nil
}
