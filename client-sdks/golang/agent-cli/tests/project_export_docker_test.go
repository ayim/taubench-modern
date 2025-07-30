package tests

import (
	"testing"

	AgentServer "github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/agent-server-client"
	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/cmd"
	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/common"
	"github.com/stretchr/testify/assert"
)

// Helper function to create a SpecState with assistantDockerMcpGateway for testing
func createSpecStateWithAssistantGateway(agentID string, gateway *common.SpecDockerMcpGateway) *cmd.SpecState {
	state := &cmd.SpecState{
		AssistantDockerMcpGateway: map[string]*common.SpecDockerMcpGateway{
			agentID: gateway,
		},
	}
	return state
}

// Helper function to create a basic AgentServer.Agent for testing
func createTestAgent(id, name string) AgentServer.Agent {
	return AgentServer.Agent{
		ID:   id,
		Name: name,
	}
}

// Helper function to create a SpecDockerMcpGateway with servers
func createGatewayWithServers(catalog string, servers map[string]common.SpecDockerMcpServer) *common.SpecDockerMcpGateway {
	return &common.SpecDockerMcpGateway{
		Catalog: &catalog,
		Servers: servers,
	}
}

// Helper function to create a test server
func createTestServer(tools []string) common.SpecDockerMcpServer {
	return common.SpecDockerMcpServer{
		Tools: tools,
	}
}

// Helper function to create an AgentSpec with agents
func createAgentSpecWithAgents(agents []common.SpecAgent) *common.AgentSpec {
	return &common.AgentSpec{
		AgentPackage: common.SpecAgentPackage{
			Agents: agents,
		},
	}
}

// Helper function to create a SpecAgent
func createSpecAgent(name string, dockerGateway *common.SpecDockerMcpGateway) common.SpecAgent {
	return common.SpecAgent{
		Name:             name,
		DockerMcpGateway: dockerGateway,
	}
}

func TestMergeDockerMcpGateway_NilOriginalSpec(t *testing.T) {
	// Setup
	agentID := "test-agent-id"
	assistantGateway := createGatewayWithServers("test-catalog", map[string]common.SpecDockerMcpServer{
		"server1": createTestServer([]string{"tool1", "tool2"}),
	})

	state := createSpecStateWithAssistantGateway(agentID, assistantGateway)
	agent := createTestAgent(agentID, "test-agent")

	// Execute
	result := state.MergeDockerMcpGateway(nil, agent)

	// Assert
	assert.Equal(t, assistantGateway, result, "Should return assistant gateway when original spec is nil")
}

func TestMergeDockerMcpGateway_NoMatchingAgentInOriginalSpec(t *testing.T) {
	// Setup
	agentID := "test-agent-id"
	assistantGateway := createGatewayWithServers("assistant-catalog", map[string]common.SpecDockerMcpServer{
		"assistant-server": createTestServer([]string{"assistant-tool"}),
	})

	state := createSpecStateWithAssistantGateway(agentID, assistantGateway)
	agent := createTestAgent(agentID, "test-agent")

	// Create original spec with different agent name
	originalSpec := createAgentSpecWithAgents([]common.SpecAgent{
		createSpecAgent("different-agent", createGatewayWithServers("original-catalog", nil)),
	})

	// Execute
	result := state.MergeDockerMcpGateway(originalSpec, agent)

	// Assert
	assert.Equal(t, assistantGateway, result, "Should return assistant gateway when no matching agent found in original spec")
}

func TestMergeDockerMcpGateway_MatchingAgentButNoOriginalDockerGateway(t *testing.T) {
	// Setup
	agentID := "test-agent-id"
	assistantGateway := createGatewayWithServers("assistant-catalog", map[string]common.SpecDockerMcpServer{
		"assistant-server": createTestServer([]string{"assistant-tool"}),
	})

	state := createSpecStateWithAssistantGateway(agentID, assistantGateway)
	agent := createTestAgent(agentID, "test-agent")

	// Create original spec with matching agent name but no DockerMcpGateway
	originalSpec := createAgentSpecWithAgents([]common.SpecAgent{
		createSpecAgent("test-agent", nil),
	})

	// Execute
	result := state.MergeDockerMcpGateway(originalSpec, agent)

	// Assert
	assert.Equal(t, assistantGateway, result, "Should return assistant gateway when original agent has no DockerMcpGateway")
}

func TestMergeDockerMcpGateway_OriginalGatewayButNoAssistantGateway(t *testing.T) {
	// Setup
	agentID := "test-agent-id"
	originalGateway := createGatewayWithServers("original-catalog", map[string]common.SpecDockerMcpServer{
		"original-server": createTestServer([]string{"original-tool"}),
	})

	state := createSpecStateWithAssistantGateway(agentID, nil)
	agent := createTestAgent(agentID, "test-agent")

	// Create original spec with DockerMcpGateway
	originalSpec := createAgentSpecWithAgents([]common.SpecAgent{
		createSpecAgent("test-agent", originalGateway),
	})

	// Execute
	result := state.MergeDockerMcpGateway(originalSpec, agent)

	// Assert
	assert.Nil(t, result, "Should return nil when assistant has no gateway")
}

func TestMergeDockerMcpGateway_BothGatewaysPresent_NoServerConflicts(t *testing.T) {
	// Setup
	agentID := "test-agent-id"

	originalGateway := createGatewayWithServers("original-catalog", map[string]common.SpecDockerMcpServer{
		"original-server": createTestServer([]string{"original-tool"}),
	})

	assistantGateway := createGatewayWithServers("assistant-catalog", map[string]common.SpecDockerMcpServer{
		"assistant-server": createTestServer([]string{"assistant-tool"}),
	})

	state := createSpecStateWithAssistantGateway(agentID, assistantGateway)
	agent := createTestAgent(agentID, "test-agent")

	originalSpec := createAgentSpecWithAgents([]common.SpecAgent{
		createSpecAgent("test-agent", originalGateway),
	})

	// Execute
	result := state.MergeDockerMcpGateway(originalSpec, agent)

	// Assert
	assert.NotNil(t, result, "Result should not be nil")
	assert.Equal(t, "original-catalog", *result.Catalog, "Should preserve original catalog")
	assert.Len(t, result.Servers, 2, "Should have both servers")
	assert.Contains(t, result.Servers, "original-server", "Should contain original server")
	assert.Contains(t, result.Servers, "assistant-server", "Should contain assistant server")
	assert.Equal(t, []string{"original-tool"}, result.Servers["original-server"].Tools, "Original server tools should be preserved")
	assert.Equal(t, []string{"assistant-tool"}, result.Servers["assistant-server"].Tools, "Assistant server tools should be added")
}

func TestMergeDockerMcpGateway_BothGatewaysPresent_ServerConflicts(t *testing.T) {
	// Setup
	agentID := "test-agent-id"

	originalGateway := createGatewayWithServers("original-catalog", map[string]common.SpecDockerMcpServer{
		"shared-server": createTestServer([]string{"original-tool"}),
		"original-only": createTestServer([]string{"original-only-tool"}),
	})

	assistantGateway := createGatewayWithServers("assistant-catalog", map[string]common.SpecDockerMcpServer{
		"shared-server":  createTestServer([]string{"assistant-tool"}),
		"assistant-only": createTestServer([]string{"assistant-only-tool"}),
	})

	state := createSpecStateWithAssistantGateway(agentID, assistantGateway)
	agent := createTestAgent(agentID, "test-agent")

	originalSpec := createAgentSpecWithAgents([]common.SpecAgent{
		createSpecAgent("test-agent", originalGateway),
	})

	// Execute
	result := state.MergeDockerMcpGateway(originalSpec, agent)

	// Assert
	assert.NotNil(t, result, "Result should not be nil")
	assert.Equal(t, "original-catalog", *result.Catalog, "Should preserve original catalog")
	assert.Len(t, result.Servers, 3, "Should have all unique servers")
	assert.Contains(t, result.Servers, "shared-server", "Should contain shared server")
	assert.Contains(t, result.Servers, "original-only", "Should contain original-only server")
	assert.Contains(t, result.Servers, "assistant-only", "Should contain assistant-only server")

	// The shared server should keep the original configuration (no overwrite)
	assert.Equal(t, []string{"original-tool"}, result.Servers["shared-server"].Tools, "Conflicting server should preserve original configuration")
	assert.NotEqual(t, []string{"assistant-tool"}, result.Servers["shared-server"].Tools, "Conflicting server should not overwrite original configuration")
	assert.Equal(t, []string{"original-only-tool"}, result.Servers["original-only"].Tools, "Original-only server should be preserved")
	assert.Equal(t, []string{"assistant-only-tool"}, result.Servers["assistant-only"].Tools, "Assistant-only server should be added")
}

func TestMergeDockerMcpGateway_OriginalGatewayWithNilServers(t *testing.T) {
	// Setup
	agentID := "test-agent-id"

	originalGateway := &common.SpecDockerMcpGateway{
		Catalog: common.Ptr("original-catalog"),
		Servers: nil, // nil servers map
	}

	assistantGateway := createGatewayWithServers("assistant-catalog", map[string]common.SpecDockerMcpServer{
		"assistant-server": createTestServer([]string{"assistant-tool"}),
	})

	state := createSpecStateWithAssistantGateway(agentID, assistantGateway)
	agent := createTestAgent(agentID, "test-agent")

	originalSpec := createAgentSpecWithAgents([]common.SpecAgent{
		createSpecAgent("test-agent", originalGateway),
	})

	// Execute
	result := state.MergeDockerMcpGateway(originalSpec, agent)

	// Assert
	assert.NotNil(t, result, "Result should not be nil")
	assert.Equal(t, "original-catalog", *result.Catalog, "Should preserve original catalog")
	assert.NotNil(t, result.Servers, "Servers map should be initialized")
	assert.Len(t, result.Servers, 1, "Should have assistant server")
	assert.Contains(t, result.Servers, "assistant-server", "Should contain assistant server")
	assert.Equal(t, []string{"assistant-tool"}, result.Servers["assistant-server"].Tools, "Assistant server tools should be added")
}

func TestMergeDockerMcpGateway_AssistantGatewayWithNilServers(t *testing.T) {
	// Setup
	agentID := "test-agent-id"

	originalGateway := createGatewayWithServers("original-catalog", map[string]common.SpecDockerMcpServer{
		"original-server": createTestServer([]string{"original-tool"}),
	})

	assistantGateway := &common.SpecDockerMcpGateway{
		Catalog: common.Ptr("assistant-catalog"),
		Servers: nil, // nil servers map
	}

	state := createSpecStateWithAssistantGateway(agentID, assistantGateway)
	agent := createTestAgent(agentID, "test-agent")

	originalSpec := createAgentSpecWithAgents([]common.SpecAgent{
		createSpecAgent("test-agent", originalGateway),
	})

	// Execute
	result := state.MergeDockerMcpGateway(originalSpec, agent)

	// Assert
	assert.NotNil(t, result, "Result should not be nil")
	assert.Equal(t, "original-catalog", *result.Catalog, "Should preserve original catalog")
	assert.NotNil(t, result.Servers, "Servers map should be preserved")
	assert.Len(t, result.Servers, 1, "Should have original server only")
	assert.Contains(t, result.Servers, "original-server", "Should contain original server")
	assert.Equal(t, []string{"original-tool"}, result.Servers["original-server"].Tools, "Original server tools should be preserved")
}

func TestMergeDockerMcpGateway_BothGatewaysWithNilServers(t *testing.T) {
	// Setup
	agentID := "test-agent-id"

	originalGateway := &common.SpecDockerMcpGateway{
		Catalog: common.Ptr("original-catalog"),
		Servers: nil,
	}

	assistantGateway := &common.SpecDockerMcpGateway{
		Catalog: common.Ptr("assistant-catalog"),
		Servers: nil,
	}

	state := createSpecStateWithAssistantGateway(agentID, assistantGateway)
	agent := createTestAgent(agentID, "test-agent")

	originalSpec := createAgentSpecWithAgents([]common.SpecAgent{
		createSpecAgent("test-agent", originalGateway),
	})

	// Execute
	result := state.MergeDockerMcpGateway(originalSpec, agent)

	// Assert
	assert.NotNil(t, result, "Result should not be nil")
	assert.Equal(t, "original-catalog", *result.Catalog, "Should preserve original catalog")
	assert.Nil(t, result.Servers, "Servers map should remain nil when both are nil")
}

func TestMergeDockerMcpGateway_EmptyAssistantGatewayMap(t *testing.T) {
	// Setup
	agentID := "test-agent-id"

	originalGateway := createGatewayWithServers("original-catalog", map[string]common.SpecDockerMcpServer{
		"original-server": createTestServer([]string{"original-tool"}),
	})

	state := &cmd.SpecState{
		AssistantDockerMcpGateway: make(map[string]*common.SpecDockerMcpGateway), // empty map
	}
	agent := createTestAgent(agentID, "test-agent")

	originalSpec := createAgentSpecWithAgents([]common.SpecAgent{
		createSpecAgent("test-agent", originalGateway),
	})

	// Execute
	result := state.MergeDockerMcpGateway(originalSpec, agent)

	// Assert
	assert.Nil(t, result, "Should return nil when assistant gateway map is empty")
}
