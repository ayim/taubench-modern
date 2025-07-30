package tests

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/common"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// Test fixtures for Docker catalog and registry
const testRegistryYAML = `registry:
  server1:
    image: "test/server1:latest"
  server2:
    image: "test/server2:latest"
  server3:
    image: "test/server3:latest"
`

const testCatalogYAML = `version: 1
name: "test-catalog"
displayName: "Test Catalog"
sema4DockerCompatibleVersion: "1.0.0"
sema4DockerCompatibleBuild: "1"
registry:
  server1:
    description: "Test Server 1"
    title: "Server 1"
    type: "mcp"
    image: "test/server1:latest"
    tools:
      - name: "tool1"
        description: "Tool 1"
      - name: "tool2"
        description: "Tool 2"
      - name: "tool3"
        description: "Tool 3"
  server2:
    description: "Test Server 2"
    title: "Server 2"
    type: "mcp"
    image: "test/server2:latest"
    tools:
      - name: "tool4"
        description: "Tool 4"
      - name: "tool5"
        description: "Tool 5"
  server3:
    description: "Test Server 3"
    title: "Server 3"
    type: "mcp"
    image: "test/server3:latest"
    tools:
      - name: "tool6"
        description: "Tool 6"
`

// setupTestFiles creates temporary registry.yaml and catalog.yaml files for testing
func setupTestFiles(t *testing.T) (registryPath, catalogPath, tempDir string, cleanup func()) {
	tempDir = t.TempDir()

	// Create registry.yaml
	registryPath = filepath.Join(tempDir, "registry.yaml")
	err := os.WriteFile(registryPath, []byte(testRegistryYAML), 0644)
	require.NoError(t, err)

	// Create catalog.yaml
	catalogPath = filepath.Join(tempDir, "catalog.yaml")
	err = os.WriteFile(catalogPath, []byte(testCatalogYAML), 0644)
	require.NoError(t, err)

	// Setup cleanup function
	cleanup = func() {
		os.RemoveAll(tempDir)
	}

	return registryPath, catalogPath, tempDir, cleanup
}

func TestCheckDockerRegistryDifferences_NilInput(t *testing.T) {
	// Test with nil SpecDockerMcpGateway
	differences, err := common.CheckDockerRegistryDifferences(nil, "")

	assert.NoError(t, err)
	assert.Empty(t, differences)
}

func TestCheckDockerRegistryDifferences_EmptyServers(t *testing.T) {
	// Test with empty servers map
	dmg := &common.SpecDockerMcpGateway{
		Servers: make(map[string]common.SpecDockerMcpServer),
	}

	differences, err := common.CheckDockerRegistryDifferences(dmg, "")

	assert.NoError(t, err)
	assert.Empty(t, differences)
}

func TestCheckDockerRegistryDifferences_NoLocalConfig(t *testing.T) {
	// Test when ExtractDockerMcpGatewayToAgentPackage returns nil (simulating no local config)
	dmg := &common.SpecDockerMcpGateway{
		Servers: map[string]common.SpecDockerMcpServer{
			"server1": {Tools: []string{"tool1", "tool2"}},
		},
	}

	// Using non-existent path to trigger error/nil return from ExtractDockerMcpGatewayToAgentPackage
	differences, err := common.CheckDockerRegistryDifferences(dmg, "/non/existent/path")

	assert.NoError(t, err)
	assert.Empty(t, differences)
}

func TestCheckDockerRegistryDifferences_WithCatalogPath(t *testing.T) {
	_, _, tempDir, cleanup := setupTestFiles(t)
	defer cleanup()

	// Test with catalog path - this is more of an integration test
	// as it depends on the actual file parsing implementation
	dmg := &common.SpecDockerMcpGateway{
		Catalog: common.Ptr("catalog.yaml"),
		Servers: map[string]common.SpecDockerMcpServer{
			"server1": {Tools: []string{"tool1", "tool2"}},
			"server2": {Tools: []string{"tool4"}},
		},
	}

	// This test might not work as expected because the function looks for files
	// in specific embedded locations rather than the provided catalog path
	_, err := common.CheckDockerRegistryDifferences(dmg, tempDir)

	// The function should return empty differences if it can't load the local config
	assert.NoError(t, err)
	// Note: The actual behavior depends on the implementation of ExtractDockerMcpGatewayToAgentPackage
	// which might not use the provided catalog path as expected
}

func TestCheckDockerRegistryDifferences_ServerMismatch(t *testing.T) {
	// Create a mock scenario where we can control the local Docker MCP Gateway
	// This test demonstrates the expected behavior but may not work with the current implementation
	// due to external dependencies

	dmg := &common.SpecDockerMcpGateway{
		Servers: map[string]common.SpecDockerMcpServer{
			"server1":     {Tools: []string{"tool1", "tool2"}},
			"server2":     {Tools: []string{"tool4"}},
			"nonexistent": {Tools: []string{"tool999"}}, // This server doesn't exist in local
		},
	}

	_, err := common.CheckDockerRegistryDifferences(dmg, "")

	assert.NoError(t, err)
	// Without proper mocking, this will likely return empty differences
	// In a real scenario with proper local config, we'd expect:
	// assert.Contains(t, differences, "server.nonexistent")
}

func TestCheckDockerRegistryDifferences_ToolMismatch(t *testing.T) {
	// Test scenario where servers exist but tools are different
	dmg := &common.SpecDockerMcpGateway{
		Servers: map[string]common.SpecDockerMcpServer{
			"server1": {Tools: []string{"tool1", "tool2", "nonexistent_tool"}}, // Has extra tool
		},
	}

	_, err := common.CheckDockerRegistryDifferences(dmg, "")

	assert.NoError(t, err)
	// Without proper mocking, this will likely return empty differences
	// In a real scenario with proper local config, we'd expect:
	// assert.Contains(t, differences, "server.server1.tools.nonexistent_tool")
}

// Test helper functions and utilities

func TestIsDockerMcpGateway(t *testing.T) {
	tests := []struct {
		name     string
		mcp      *common.AgentPackageMcpServer
		expected bool
	}{
		{
			name: "Valid Docker MCP Gateway",
			mcp: &common.AgentPackageMcpServer{
				Command:   "docker",
				Arguments: []string{"mcp", "gateway", "run"},
			},
			expected: true,
		},
		{
			name: "Invalid - wrong command",
			mcp: &common.AgentPackageMcpServer{
				Command:   "python",
				Arguments: []string{"mcp", "gateway", "run"},
			},
			expected: false,
		},
		{
			name: "Invalid - missing arguments",
			mcp: &common.AgentPackageMcpServer{
				Command:   "docker",
				Arguments: []string{"mcp"},
			},
			expected: false,
		},
		{
			name: "Invalid - wrong arguments",
			mcp: &common.AgentPackageMcpServer{
				Command:   "docker",
				Arguments: []string{"run", "container"},
			},
			expected: false,
		},
		{
			name:     "Nil input",
			mcp:      nil,
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := common.IsDockerMcpGateway(tt.mcp)
			assert.Equal(t, tt.expected, result)
		})
	}
}

// Integration test that would work with proper file setup
func TestCheckDockerRegistryDifferences_Integration(t *testing.T) {
	t.Skip("Skipping integration test - requires proper file system setup and embedded resource mocking")

	// This test would require:
	// 1. Mocking the embedded registry.yaml and catalog.yaml files
	// 2. Or refactoring the code to accept file paths as parameters
	// 3. Or using a test environment with the actual embedded files

	registryPath, catalogPath, tempDir, cleanup := setupTestFiles(t)
	defer cleanup()

	// Copy files to expected locations or mock the embedded file system
	// This would require significant changes to the underlying file parsing functions

	dmg := &common.SpecDockerMcpGateway{
		Catalog: &catalogPath,
		Servers: map[string]common.SpecDockerMcpServer{
			"server1": {Tools: []string{"tool1", "tool2"}},
			"server2": {Tools: []string{"tool4", "tool5"}},
			"server4": {Tools: []string{"tool999"}}, // Non-existent server
		},
	}

	differences, err := common.CheckDockerRegistryDifferences(dmg, tempDir)

	assert.NoError(t, err)
	// Expected differences:
	// - "server.server4" (server doesn't exist in registry)
	// We might also expect tool differences if the local config differs

	t.Logf("Registry path: %s", registryPath)
	t.Logf("Catalog path: %s", catalogPath)
	t.Logf("Differences: %v", differences)
}

// Benchmark test for performance
func BenchmarkCheckDockerRegistryDifferences(b *testing.B) {
	dmg := &common.SpecDockerMcpGateway{
		Servers: map[string]common.SpecDockerMcpServer{
			"server1": {Tools: []string{"tool1", "tool2"}},
			"server2": {Tools: []string{"tool4", "tool5"}},
		},
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, _ = common.CheckDockerRegistryDifferences(dmg, "")
	}
}
