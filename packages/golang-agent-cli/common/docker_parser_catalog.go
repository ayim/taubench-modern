package common

import (
	"fmt"
	"os"

	"gopkg.in/yaml.v2"
)

// DockerParseCatalogYAML parses the catalog.yaml file and returns a Catalog struct
func DockerParseCatalogYAML(path string) (*DockerCatalog, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read catalog.yaml: %w", err)
	}
	var catalog DockerCatalog
	if err := yaml.Unmarshal(data, &catalog); err != nil {
		return nil, fmt.Errorf("failed to unmarshal catalog.yaml: %w", err)
	}
	return &catalog, nil
}

// DockerParseEmbeddedCatalogYAML parses the embedded catalog.yaml and returns a Catalog struct
// The Docker Catalog is embedded in the agent-cli binary as it was downloaded from the Docker: https://desktop.docker.com/mcp/catalog/v2/catalog.yaml
func DockerParseEmbeddedCatalogYAML() (*DockerCatalog, error) {
	var catalog DockerCatalog
	if err := yaml.Unmarshal(CatalogYAML, &catalog); err != nil {
		return nil, fmt.Errorf("failed to unmarshal embedded catalog.yaml: %w", err)
	}
	return &catalog, nil
}
