package common

import (
	"fmt"
	"os"

	"gopkg.in/yaml.v3"
)

// DockerRegistryEntry represents a single entry in the registry with a ref field.
type DockerRegistryEntry struct {
	Ref string `yaml:"ref"`
}

// DockerRegistryFile represents the structure of the registry.yaml file.
type DockerRegistryFile struct {
	Registry map[string]DockerRegistryEntry `yaml:"registry"`
}

// DockerParseRegistryYAML parses the registry.yaml file from the default location and returns a RegistryFile struct.
// The Docker Registry is a local file that is created by the Docker CLI tool when the MCP Gateway is activated.
// This will contain a cleaner list of servers that should be available in the Docker Catalog file.
func DockerParseRegistryYAML() (*DockerRegistryFile, error) {
	data, err := os.ReadFile(ExpandPath(defaultDockerRegistryLocation))
	if err != nil {
		return nil, fmt.Errorf("failed to read %s: %w", ExpandPath(defaultDockerRegistryLocation), err)
	}
	var regFile DockerRegistryFile
	if err := yaml.Unmarshal(data, &regFile); err != nil {
		return nil, fmt.Errorf("failed to unmarshal %s: %w", ExpandPath(defaultDockerRegistryLocation), err)
	}
	return &regFile, nil
}
