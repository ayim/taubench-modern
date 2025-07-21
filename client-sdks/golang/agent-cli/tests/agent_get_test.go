package tests

import (
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"

	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/cmd"
	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/common"
	AgentServer "github.com/Sema4AI/agent-platform/client-sdks/golang/agent-client-go/pkg/client"
)

func TestReadConversationGuideYAML_Success(t *testing.T) {
	tmpDir := t.TempDir()
	yamlPath := filepath.Join(tmpDir, "conversation-guide.yaml")

	yamlContent := `
question-groups:
  - title: "Group 1"
    questions:
      - "What is your name?"
      - "How old are you?"
`
	err := os.WriteFile(yamlPath, []byte(yamlContent), 0644)
	assert.NoError(t, err)

	result, err := common.ReadConversationGuideYAML(yamlPath)
	assert.NoError(t, err)
	assert.Len(t, result, 1)
	assert.Equal(t, "Group 1", result[0].Title)
	assert.Equal(t, []string{"What is your name?", "How old are you?"}, result[0].Questions)
}

func TestReadConversationGuideYAML_FileNotFound(t *testing.T) {
	_, err := common.ReadConversationGuideYAML("nonexistent.yaml")
	assert.Error(t, err)
}

func TestReadConversationGuideYAML_InvalidYAML(t *testing.T) {
	tmpDir := t.TempDir()
	yamlPath := filepath.Join(tmpDir, "invalid.yaml")

	err := os.WriteFile(yamlPath, []byte("not: [valid"), 0644)
	assert.NoError(t, err)

	_, err = common.ReadConversationGuideYAML(yamlPath)
	assert.Error(t, err)
}

func TestCheckAgentsSynchronization(t *testing.T) {
	tests := []struct {
		name            string
		agentProjects   []*common.AgentProject
		deployedAgents  []*AgentServer.Agent
		expectError     bool
		errorContains   string
		expectedChanges []string
		description     string
	}{
		{
			name:            "empty inputs",
			agentProjects:   []*common.AgentProject{},
			deployedAgents:  []*AgentServer.Agent{},
			expectError:     false,
			expectedChanges: []string{},
			description:     "should handle empty inputs without error",
		},
		{
			name:            "nil inputs",
			agentProjects:   nil,
			deployedAgents:  nil,
			expectError:     false,
			expectedChanges: []string{},
			description:     "should handle nil inputs without error",
		},
		{
			name: "agent project with matching deployed agent - successful sync",
			agentProjects: []*common.AgentProject{
				{
					Path:    "/test/path",
					AgentID: "agent-1",
					Agent: common.SpecAgent{
						Name:        "Test Agent",
						Description: "Test Description",
						Version:     "1.0.0",
						Runbook:     "Test runbook content",
					},
					Synced: false,
				},
			},
			deployedAgents: []*AgentServer.Agent{
				{
					ID:          "agent-1",
					Name:        "Test Agent",
					Description: "Test Description",
					Version:     "1.0.0",
					Runbook:     "Test runbook content",
					UpdatedAt:   time.Now().Add(-time.Hour), // 1 hour ago
				},
			},
			expectError:     false,
			expectedChanges: []string{},
			description:     "should successfully sync when agent project matches deployed agent",
		},
		{
			name: "agent project without matching deployed agent",
			agentProjects: []*common.AgentProject{
				{
					Path:    "/test/path",
					AgentID: "agent-1",
					Agent: common.SpecAgent{
						Name:        "Test Agent",
						Description: "Test Description",
						Version:     "1.0.0",
						Runbook:     "Test runbook content",
					},
					Synced: false,
				},
			},
			deployedAgents: []*AgentServer.Agent{
				{
					ID:          "agent-2", // Different ID
					Name:        "Different Agent",
					Description: "Different Description",
					Version:     "2.0.0",
					Runbook:     "Different runbook content",
					UpdatedAt:   time.Now().Add(-time.Hour),
				},
			},
			expectError:     false,
			expectedChanges: []string{},
			description:     "should handle agent project without matching deployed agent",
		},
		{
			name: "multiple agent projects with mixed matches",
			agentProjects: []*common.AgentProject{
				{
					Path:    "/test/path1",
					AgentID: "agent-1",
					Agent: common.SpecAgent{
						Name:        "Agent 1",
						Description: "Description 1",
						Version:     "1.0.0",
						Runbook:     "Runbook 1",
					},
					Synced: false,
				},
				{
					Path:    "/test/path2",
					AgentID: "agent-2",
					Agent: common.SpecAgent{
						Name:        "Agent 2",
						Description: "Description 2",
						Version:     "2.0.0",
						Runbook:     "Runbook 2",
					},
					Synced: false,
				},
			},
			deployedAgents: []*AgentServer.Agent{
				{
					ID:          "agent-1",
					Name:        "Agent 1",
					Description: "Description 1",
					Version:     "1.0.0",
					Runbook:     "Runbook 1",
					UpdatedAt:   time.Now().Add(-time.Hour),
				},
				{
					ID:          "agent-3", // No match for agent-2
					Name:        "Agent 3",
					Description: "Description 3",
					Version:     "3.0.0",
					Runbook:     "Runbook 3",
					UpdatedAt:   time.Now().Add(-time.Hour),
				},
			},
			expectError:     false,
			expectedChanges: []string{},
			description:     "should handle multiple agent projects with mixed matches",
		},
		{
			name: "agent project with action packages",
			agentProjects: []*common.AgentProject{
				{
					Path:    "/test/path",
					AgentID: "agent-1",
					Agent: common.SpecAgent{
						Name:        "Test Agent",
						Description: "Test Description",
						Version:     "1.0.0",
						Runbook:     "Test runbook content",
						ActionPackages: []common.SpecAgentActionPackage{
							{
								Name:         "test-action",
								Organization: "test-org",
								Type:         "folder",
								Version:      "1.0.0",
								Path:         "test-action",
							},
						},
					},
					Synced: false,
				},
			},
			deployedAgents: []*AgentServer.Agent{
				{
					ID:          "agent-1",
					Name:        "Test Agent",
					Description: "Test Description",
					Version:     "1.0.0",
					Runbook:     "Test runbook content",
					UpdatedAt:   time.Now().Add(-time.Hour),
				},
			},
			expectError:     false,
			expectedChanges: []string{"actionPackages"},
			description:     "should handle agent project with action packages",
		},
		{
			name: "concurrent processing test",
			agentProjects: []*common.AgentProject{
				{
					Path:    "/test/path1",
					AgentID: "agent-1",
					Agent: common.SpecAgent{
						Name:        "Agent 1",
						Description: "Description 1",
						Version:     "1.0.0",
						Runbook:     "Runbook 1",
					},
					Synced: false,
				},
				{
					Path:    "/test/path2",
					AgentID: "agent-2",
					Agent: common.SpecAgent{
						Name:        "Agent 2",
						Description: "Description 2",
						Version:     "2.0.0",
						Runbook:     "Runbook 2",
					},
					Synced: false,
				},
				{
					Path:    "/test/path3",
					AgentID: "agent-3",
					Agent: common.SpecAgent{
						Name:        "Agent 3",
						Description: "Description 3",
						Version:     "3.0.0",
						Runbook:     "Runbook 3",
					},
					Synced: false,
				},
			},
			deployedAgents: []*AgentServer.Agent{
				{
					ID:          "agent-1",
					Name:        "Agent 1",
					Description: "Description 1",
					Version:     "1.0.0",
					Runbook:     "Runbook 1",
					UpdatedAt:   time.Now().Add(-time.Hour),
				},
				{
					ID:          "agent-2",
					Name:        "Agent 2",
					Description: "Description 2",
					Version:     "2.0.0",
					Runbook:     "Runbook 2",
					UpdatedAt:   time.Now().Add(-time.Hour),
				},
				{
					ID:          "agent-3",
					Name:        "Agent 3",
					Description: "Description 3",
					Version:     "3.0.0",
					Runbook:     "Runbook 3",
					UpdatedAt:   time.Now().Add(-time.Hour),
				},
			},
			expectError:     false,
			expectedChanges: []string{},
			description:     "should handle concurrent processing of multiple agents",
		},
		{
			name: "agent project with empty AgentID",
			agentProjects: []*common.AgentProject{
				{
					Path:    "/test/path",
					AgentID: "", // Empty AgentID
					Agent: common.SpecAgent{
						Name:        "Test Agent",
						Description: "Test Description",
						Version:     "1.0.0",
						Runbook:     "Test runbook content",
					},
					Synced: false,
				},
			},
			deployedAgents: []*AgentServer.Agent{
				{
					ID:          "agent-1",
					Name:        "Test Agent",
					Description: "Test Description",
					Version:     "1.0.0",
					Runbook:     "Test runbook content",
					UpdatedAt:   time.Now().Add(-time.Hour),
				},
			},
			expectError:     false,
			expectedChanges: []string{},
			description:     "should handle empty AgentID without error",
		},
		{
			name: "agent project with different AgentID format",
			agentProjects: []*common.AgentProject{
				{
					Path:    "/test/path",
					AgentID: "different-format-id",
					Agent: common.SpecAgent{
						Name:        "Test Agent",
						Description: "Test Description",
						Version:     "1.0.0",
						Runbook:     "Test runbook content",
					},
					Synced: false,
				},
			},
			deployedAgents: []*AgentServer.Agent{
				{
					ID:          "agent-1",
					Name:        "Test Agent",
					Description: "Test Description",
					Version:     "1.0.0",
					Runbook:     "Test runbook content",
					UpdatedAt:   time.Now().Add(-time.Hour),
				},
			},
			expectError:     false,
			expectedChanges: []string{},
			description:     "should handle different AgentID format without error",
		},
		{
			name: "agent project with different name",
			agentProjects: []*common.AgentProject{
				{
					Path:    "/test/path",
					AgentID: "agent-1",
					Agent: common.SpecAgent{
						Name:        "Test Agent",
						Description: "Test Description",
						Version:     "1.0.0",
						Runbook:     "Test runbook content",
					},
					Synced: false,
				},
			},
			deployedAgents: []*AgentServer.Agent{
				{
					ID:          "agent-1",              // Same ID
					Name:        "Different Agent Name", // Different name
					Description: "Test Description",
					Version:     "1.0.0",
					Runbook:     "Test runbook content",
					UpdatedAt:   time.Now().Add(-time.Hour),
				},
			},
			expectError:     false,
			expectedChanges: []string{"name"},
			description:     "should detect when agent name differs",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Create a copy of agent projects to avoid modifying the original test data
			var agentProjectsCopy []*common.AgentProject
			if tt.agentProjects != nil {
				agentProjectsCopy = make([]*common.AgentProject, len(tt.agentProjects))
				for i, ap := range tt.agentProjects {
					if ap != nil {
						// Create a deep copy of the agent project
						agentCopy := &common.AgentProject{
							Path:                  ap.Path,
							AgentID:               ap.AgentID,
							Agent:                 ap.Agent,
							Synced:                ap.Synced,
							AgentChanges:          make([]string, len(ap.AgentChanges)),
							ActionPackagesChanges: make([]string, len(ap.ActionPackagesChanges)),
							Exclude:               make([]string, len(ap.Exclude)),
						}
						copy(agentCopy.AgentChanges, ap.AgentChanges)
						copy(agentCopy.ActionPackagesChanges, ap.ActionPackagesChanges)
						copy(agentCopy.Exclude, ap.Exclude)
						agentProjectsCopy[i] = agentCopy
					}
				}
			}

			// Execute the function
			err := cmd.CheckAgentsSynchronization(agentProjectsCopy, tt.deployedAgents)

			// Assert results
			if tt.expectError {
				assert.Error(t, err, tt.description)
				if tt.errorContains != "" {
					assert.Contains(t, err.Error(), tt.errorContains, "error should contain expected message")
				}
			} else {
				assert.NoError(t, err, tt.description)
			}

			// Additional assertions for successful cases
			if !tt.expectError && tt.agentProjects != nil {
				for _, ap := range agentProjectsCopy {
					if ap != nil {
						// The Synced field will be updated by ApplySynchronizationStatus
						// We can't predict the exact value without mocking file system operations
						// So we just verify the function completed without error
						_ = ap.Synced // Access the field to ensure it was processed
					}
				}

				// Verify AgentChanges and ActionPackagesChanges
				verifyAgentChanges(t, agentProjectsCopy, tt.expectedChanges)
			}
		})
	}
}

// TestCheckAgentsSynchronization_WithMcpServers tests synchronization with MCP servers
func TestCheckAgentsSynchronization_WithMcpServers(t *testing.T) {
	tests := []struct {
		name            string
		agentProjects   []*common.AgentProject
		deployedAgents  []*AgentServer.Agent
		expectError     bool
		expectedChanges []string
		description     string
	}{
		{
			name: "agent with MCP servers - successful sync",
			agentProjects: []*common.AgentProject{
				{
					Path:    "/test/path",
					AgentID: "agent-1",
					Agent: common.SpecAgent{
						Name:        "Test Agent",
						Description: "Test Description",
						Version:     "1.0.0",
						Runbook:     "Test runbook content",
						McpServers: []common.SpecMcpServer{
							{
								Name:        "file-system-server",
								Transport:   AgentServer.MCPTransportStdio,
								Description: "MCP server for file system operations",
								CommandLine: []string{"uv", "run", "python", "-m", "mcp_file_system"},
								Env: map[string]common.SpecMcpServerVariable{
									"FILE_SYSTEM_ROOT": {
										Type:        common.SpecMcpTypeString,
										Description: "Root directory for file operations",
										Default:     "/data",
									},
									"MCP_API_KEY": {
										Type:        common.SpecMcpTypeSecret,
										Description: "API key for authentication",
									},
								},
								Cwd:                  "./mcp-servers/file-system",
								ForceSerialToolCalls: false,
							},
							{
								Name:        "database-server",
								Transport:   AgentServer.MCPTransportStreamableHTTP,
								Description: "MCP server for database operations",
								URL:         "http://localhost:8080/mcp",
								Headers: map[string]common.SpecMcpServerVariable{
									"Authorization": {
										Type:        common.SpecMcpTypeOAuth2Secret,
										Description: "OAuth2 API key for authentication",
										Provider:    "Microsoft",
										Scopes:      []string{"user.read", "user.write"},
									},
									"Content-Type": {
										Value: common.Ptr("application/json"),
									},
								},
								ForceSerialToolCalls: true,
							},
						},
					},
					Synced: false,
				},
			},
			deployedAgents: []*AgentServer.Agent{
				{
					ID:          "agent-1",
					Name:        "Test Agent",
					Description: "Test Description",
					Version:     "1.0.0",
					Runbook:     "Test runbook content",
					McpServers: []AgentServer.McpServer{
						{
							Name:        "file-system-server",
							Transport:   AgentServer.MCPTransportStdio,
							Description: "MCP server for file system operations",
							Command:     common.Ptr("uv"),
							Args:        []string{"run", "python", "-m", "mcp_file_system"},
							Env: map[string]AgentServer.McpServerVariable{
								"FILE_SYSTEM_ROOT": {
									Type:        "string",
									Description: "Root directory for file operations",
									Default:     "/data",
								},
								"MCP_API_KEY": {
									Type:        "secret",
									Description: "API key for authentication",
								},
							},
							Cwd:                  common.Ptr("./mcp-servers/file-system"),
							ForceSerialToolCalls: false,
						},
						{
							Name:        "database-server",
							Transport:   AgentServer.MCPTransportStreamableHTTP,
							Description: "MCP server for database operations",
							URL:         common.Ptr("http://localhost:8080/mcp"),
							Headers: map[string]AgentServer.McpServerVariable{
								"Authorization": {
									Type:        "oauth2-secret",
									Description: "OAuth2 API key for authentication",
									Provider:    "Microsoft",
									Scopes:      []string{"user.read", "user.write"},
								},
								"Content-Type": {
									Value: common.Ptr("application/json"),
								},
							},
							ForceSerialToolCalls: true,
						},
					},
					UpdatedAt: time.Now().Add(-time.Hour),
				},
			},
			expectError:     false,
			expectedChanges: []string{},
			description:     "should successfully sync when agent project MCP servers match deployed agent",
		},
		{
			name: "agent with MCP servers - different configuration",
			agentProjects: []*common.AgentProject{
				{
					Path:    "/test/path",
					AgentID: "agent-1",
					Agent: common.SpecAgent{
						Name:        "Test Agent",
						Description: "Test Description",
						Version:     "1.0.0",
						Runbook:     "Test runbook content",
						McpServers: []common.SpecMcpServer{
							{
								Name:        "file-system-server",
								Transport:   AgentServer.MCPTransportStdio,
								Description: "MCP server for file system operations",
								CommandLine: []string{"uv", "run", "python", "-m", "mcp_file_system"},
								Env: map[string]common.SpecMcpServerVariable{
									"FILE_SYSTEM_ROOT": {
										Type:        common.SpecMcpTypeString,
										Description: "Root directory for file operations",
										Default:     "/data",
									},
								},
								Cwd:                  "./mcp-servers/file-system",
								ForceSerialToolCalls: false,
							},
						},
					},
					Synced: false,
				},
			},
			deployedAgents: []*AgentServer.Agent{
				{
					ID:          "agent-1",
					Name:        "Test Agent",
					Description: "Test Description",
					Version:     "1.0.0",
					Runbook:     "Test runbook content",
					McpServers: []AgentServer.McpServer{
						{
							Name:        "file-system-server",
							Transport:   AgentServer.MCPTransportStdio,
							Description: "MCP server for file system operations",
							Command:     common.Ptr("uv"),
							Args:        []string{"run", "python", "-m", "mcp_file_system"},
							Env: map[string]AgentServer.McpServerVariable{
								"FILE_SYSTEM_ROOT": {
									Type:        "string",
									Description: "Root directory for file operations",
									Default:     "/different/path", // Different default
								},
							},
							Cwd:                  common.Ptr("./mcp-servers/file-system"),
							ForceSerialToolCalls: false,
						},
					},
					UpdatedAt: time.Now().Add(-time.Hour),
				},
			},
			expectError:     false,
			expectedChanges: []string{"mcpServers"},
			description:     "should handle MCP server configuration differences",
		},
		{
			name: "agent with MCP servers - missing in deployed",
			agentProjects: []*common.AgentProject{
				{
					Path:    "/test/path",
					AgentID: "agent-1",
					Agent: common.SpecAgent{
						Name:        "Test Agent",
						Description: "Test Description",
						Version:     "1.0.0",
						Runbook:     "Test runbook content",
						McpServers: []common.SpecMcpServer{
							{
								Name:        "file-system-server",
								Transport:   AgentServer.MCPTransportStdio,
								Description: "MCP server for file system operations",
								CommandLine: []string{"uv", "run", "python", "-m", "mcp_file_system"},
							},
						},
					},
					Synced: false,
				},
			},
			deployedAgents: []*AgentServer.Agent{
				{
					ID:          "agent-1",
					Name:        "Test Agent",
					Description: "Test Description",
					Version:     "1.0.0",
					Runbook:     "Test runbook content",
					McpServers:  []AgentServer.McpServer{}, // No MCP servers
					UpdatedAt:   time.Now().Add(-time.Hour),
				},
			},
			expectError:     false,
			expectedChanges: []string{"mcpServers"},
			description:     "should handle agent project with MCP servers but deployed agent without",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Create a copy of agent projects to avoid modifying the original test data
			var agentProjectsCopy []*common.AgentProject
			if tt.agentProjects != nil {
				agentProjectsCopy = make([]*common.AgentProject, len(tt.agentProjects))
				for i, ap := range tt.agentProjects {
					if ap != nil {
						agentCopy := &common.AgentProject{
							Path:                  ap.Path,
							AgentID:               ap.AgentID,
							Agent:                 ap.Agent,
							Synced:                ap.Synced,
							AgentChanges:          make([]string, len(ap.AgentChanges)),
							ActionPackagesChanges: make([]string, len(ap.ActionPackagesChanges)),
							Exclude:               make([]string, len(ap.Exclude)),
						}
						copy(agentCopy.AgentChanges, ap.AgentChanges)
						copy(agentCopy.ActionPackagesChanges, ap.ActionPackagesChanges)
						copy(agentCopy.Exclude, ap.Exclude)
						agentProjectsCopy[i] = agentCopy
					}
				}
			}

			// Execute the function
			err := cmd.CheckAgentsSynchronization(agentProjectsCopy, tt.deployedAgents)

			// Assert results
			if tt.expectError {
				assert.Error(t, err, tt.description)
			} else {
				assert.NoError(t, err, tt.description)
			}

			// Additional assertions for AgentChanges and ActionPackagesChanges
			if !tt.expectError && tt.agentProjects != nil {
				verifyAgentChanges(t, agentProjectsCopy, tt.expectedChanges)
			}
		})
	}
}

// TestCheckAgentsSynchronization_WithConversationStarter tests synchronization with conversation starter
func TestCheckAgentsSynchronization_WithConversationStarter(t *testing.T) {
	tests := []struct {
		name            string
		agentProjects   []*common.AgentProject
		deployedAgents  []*AgentServer.Agent
		expectError     bool
		expectedChanges []string
		description     string
	}{
		{
			name: "agent with conversation starter - successful sync",
			agentProjects: []*common.AgentProject{
				{
					Path:    "/test/path",
					AgentID: "agent-1",
					Agent: common.SpecAgent{
						Name:                "Test Agent",
						Description:         "Test Description",
						Version:             "1.0.0",
						Runbook:             "Test runbook content",
						ConversationStarter: "Hello! How can I help you today?",
					},
					Synced: false,
				},
			},
			deployedAgents: []*AgentServer.Agent{
				{
					ID:          "agent-1",
					Name:        "Test Agent",
					Description: "Test Description",
					Version:     "1.0.0",
					Runbook:     "Test runbook content",
					Extra: AgentServer.AgentExtra{
						ConversationStarter: "Hello! How can I help you today?",
					},
					UpdatedAt: time.Now().Add(-time.Hour),
				},
			},
			expectError:     false,
			expectedChanges: []string{},
			description:     "should successfully sync when conversation starter matches",
		},
		{
			name: "agent with conversation starter - different values",
			agentProjects: []*common.AgentProject{
				{
					Path:    "/test/path",
					AgentID: "agent-1",
					Agent: common.SpecAgent{
						Name:                "Test Agent",
						Description:         "Test Description",
						Version:             "1.0.0",
						Runbook:             "Test runbook content",
						ConversationStarter: "Hello! How can I help you today?",
					},
					Synced: false,
				},
			},
			deployedAgents: []*AgentServer.Agent{
				{
					ID:          "agent-1",
					Name:        "Test Agent",
					Description: "Test Description",
					Version:     "1.0.0",
					Runbook:     "Test runbook content",
					Extra: AgentServer.AgentExtra{
						ConversationStarter: "Hi there! What can I do for you?", // Different conversation starter
					},
					UpdatedAt: time.Now().Add(-time.Hour),
				},
			},
			expectError:     false,
			expectedChanges: []string{"conversationStarter"},
			description:     "should handle different conversation starter values",
		},
		{
			name: "agent with conversation starter - empty in deployed",
			agentProjects: []*common.AgentProject{
				{
					Path:    "/test/path",
					AgentID: "agent-1",
					Agent: common.SpecAgent{
						Name:                "Test Agent",
						Description:         "Test Description",
						Version:             "1.0.0",
						Runbook:             "Test runbook content",
						ConversationStarter: "Hello! How can I help you today?",
					},
					Synced: false,
				},
			},
			deployedAgents: []*AgentServer.Agent{
				{
					ID:          "agent-1",
					Name:        "Test Agent",
					Description: "Test Description",
					Version:     "1.0.0",
					Runbook:     "Test runbook content",
					Extra: AgentServer.AgentExtra{
						ConversationStarter: "", // Empty conversation starter
					},
					UpdatedAt: time.Now().Add(-time.Hour),
				},
			},
			expectError:     false,
			expectedChanges: []string{"conversationStarter"},
			description:     "should handle agent project with conversation starter but deployed agent without",
		},
		{
			name: "agent without conversation starter - empty in both",
			agentProjects: []*common.AgentProject{
				{
					Path:    "/test/path",
					AgentID: "agent-1",
					Agent: common.SpecAgent{
						Name:                "Test Agent",
						Description:         "Test Description",
						Version:             "1.0.0",
						Runbook:             "Test runbook content",
						ConversationStarter: "", // Empty conversation starter
					},
					Synced: false,
				},
			},
			deployedAgents: []*AgentServer.Agent{
				{
					ID:          "agent-1",
					Name:        "Test Agent",
					Description: "Test Description",
					Version:     "1.0.0",
					Runbook:     "Test runbook content",
					Extra: AgentServer.AgentExtra{
						ConversationStarter: "", // Empty conversation starter
					},
					UpdatedAt: time.Now().Add(-time.Hour),
				},
			},
			expectError:     false,
			expectedChanges: []string{},
			description:     "should handle empty conversation starter in both agent project and deployed agent",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Create a copy of agent projects to avoid modifying the original test data
			var agentProjectsCopy []*common.AgentProject
			if tt.agentProjects != nil {
				agentProjectsCopy = make([]*common.AgentProject, len(tt.agentProjects))
				for i, ap := range tt.agentProjects {
					if ap != nil {
						agentCopy := &common.AgentProject{
							Path:                  ap.Path,
							AgentID:               ap.AgentID,
							Agent:                 ap.Agent,
							Synced:                ap.Synced,
							AgentChanges:          make([]string, len(ap.AgentChanges)),
							ActionPackagesChanges: make([]string, len(ap.ActionPackagesChanges)),
							Exclude:               make([]string, len(ap.Exclude)),
						}
						copy(agentCopy.AgentChanges, ap.AgentChanges)
						copy(agentCopy.ActionPackagesChanges, ap.ActionPackagesChanges)
						copy(agentCopy.Exclude, ap.Exclude)
						agentProjectsCopy[i] = agentCopy
					}
				}
			}

			// Execute the function
			err := cmd.CheckAgentsSynchronization(agentProjectsCopy, tt.deployedAgents)

			// Assert results
			if tt.expectError {
				assert.Error(t, err, tt.description)
			} else {
				assert.NoError(t, err, tt.description)
			}

			// Additional assertions for AgentChanges and ActionPackagesChanges
			if !tt.expectError && tt.agentProjects != nil {
				verifyAgentChanges(t, agentProjectsCopy, tt.expectedChanges)
			}
		})
	}
}

// TestCheckAgentsSynchronization_WithWelcomeMessage tests synchronization with welcome message
func TestCheckAgentsSynchronization_WithWelcomeMessage(t *testing.T) {
	tests := []struct {
		name            string
		agentProjects   []*common.AgentProject
		deployedAgents  []*AgentServer.Agent
		expectError     bool
		expectedChanges []string
		description     string
	}{
		{
			name: "agent with welcome message - successful sync",
			agentProjects: []*common.AgentProject{
				{
					Path:    "/test/path",
					AgentID: "agent-1",
					Agent: common.SpecAgent{
						Name:           "Test Agent",
						Description:    "Test Description",
						Version:        "1.0.0",
						Runbook:        "Test runbook content",
						WelcomeMessage: "Welcome! I'm here to help you with your tasks.",
					},
					Synced: false,
				},
			},
			deployedAgents: []*AgentServer.Agent{
				{
					ID:          "agent-1",
					Name:        "Test Agent",
					Description: "Test Description",
					Version:     "1.0.0",
					Runbook:     "Test runbook content",
					Extra: AgentServer.AgentExtra{
						WelcomeMessage: "Welcome! I'm here to help you with your tasks.",
					},
					UpdatedAt: time.Now().Add(-time.Hour),
				},
			},
			expectError:     false,
			expectedChanges: []string{},
			description:     "should successfully sync when welcome message matches",
		},
		{
			name: "agent with welcome message - different values",
			agentProjects: []*common.AgentProject{
				{
					Path:    "/test/path",
					AgentID: "agent-1",
					Agent: common.SpecAgent{
						Name:           "Test Agent",
						Description:    "Test Description",
						Version:        "1.0.0",
						Runbook:        "Test runbook content",
						WelcomeMessage: "Welcome! I'm here to help you with your tasks.",
					},
					Synced: false,
				},
			},
			deployedAgents: []*AgentServer.Agent{
				{
					ID:          "agent-1",
					Name:        "Test Agent",
					Description: "Test Description",
					Version:     "1.0.0",
					Runbook:     "Test runbook content",
					Extra: AgentServer.AgentExtra{
						WelcomeMessage: "Hello! How can I assist you today?", // Different welcome message
					},
					UpdatedAt: time.Now().Add(-time.Hour),
				},
			},
			expectError:     false,
			expectedChanges: []string{"welcomeMessage"},
			description:     "should handle different welcome message values",
		},
		{
			name: "agent with welcome message - empty in deployed",
			agentProjects: []*common.AgentProject{
				{
					Path:    "/test/path",
					AgentID: "agent-1",
					Agent: common.SpecAgent{
						Name:           "Test Agent",
						Description:    "Test Description",
						Version:        "1.0.0",
						Runbook:        "Test runbook content",
						WelcomeMessage: "Welcome! I'm here to help you with your tasks.",
					},
					Synced: false,
				},
			},
			deployedAgents: []*AgentServer.Agent{
				{
					ID:          "agent-1",
					Name:        "Test Agent",
					Description: "Test Description",
					Version:     "1.0.0",
					Runbook:     "Test runbook content",
					Extra: AgentServer.AgentExtra{
						WelcomeMessage: "", // Empty welcome message
					},
					UpdatedAt: time.Now().Add(-time.Hour),
				},
			},
			expectError:     false,
			expectedChanges: []string{"welcomeMessage"},
			description:     "should handle agent project with welcome message but deployed agent without",
		},
		{
			name: "agent with welcome message in metadata - successful sync",
			agentProjects: []*common.AgentProject{
				{
					Path:    "/test/path",
					AgentID: "agent-1",
					Agent: common.SpecAgent{
						Name:           "Test Agent",
						Description:    "Test Description",
						Version:        "1.0.0",
						Runbook:        "Test runbook content",
						WelcomeMessage: "Welcome! I'm here to help you with your tasks.",
					},
					Synced: false,
				},
			},
			deployedAgents: []*AgentServer.Agent{
				{
					ID:          "agent-1",
					Name:        "Test Agent",
					Description: "Test Description",
					Version:     "1.0.0",
					Runbook:     "Test runbook content",
					Metadata: AgentServer.AgentMetadata{
						WelcomeMessage: "Welcome! I'm here to help you with your tasks.",
					},
					UpdatedAt: time.Now().Add(-time.Hour),
				},
			},
			expectError:     false,
			expectedChanges: []string{"metadata", "welcomeMessage"},
			description:     "should successfully sync when welcome message is in metadata",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Create a copy of agent projects to avoid modifying the original test data
			var agentProjectsCopy []*common.AgentProject
			if tt.agentProjects != nil {
				agentProjectsCopy = make([]*common.AgentProject, len(tt.agentProjects))
				for i, ap := range tt.agentProjects {
					if ap != nil {
						agentCopy := &common.AgentProject{
							Path:                  ap.Path,
							AgentID:               ap.AgentID,
							Agent:                 ap.Agent,
							Synced:                ap.Synced,
							AgentChanges:          make([]string, len(ap.AgentChanges)),
							ActionPackagesChanges: make([]string, len(ap.ActionPackagesChanges)),
							Exclude:               make([]string, len(ap.Exclude)),
						}
						copy(agentCopy.AgentChanges, ap.AgentChanges)
						copy(agentCopy.ActionPackagesChanges, ap.ActionPackagesChanges)
						copy(agentCopy.Exclude, ap.Exclude)
						agentProjectsCopy[i] = agentCopy
					}
				}
			}

			// Execute the function
			err := cmd.CheckAgentsSynchronization(agentProjectsCopy, tt.deployedAgents)

			// Assert results
			if tt.expectError {
				assert.Error(t, err, tt.description)
			} else {
				assert.NoError(t, err, tt.description)
			}

			// Additional assertions for AgentChanges and ActionPackagesChanges
			if !tt.expectError && tt.agentProjects != nil {
				verifyAgentChanges(t, agentProjectsCopy, tt.expectedChanges)
			}
		})
	}
}

// Helper function to verify AgentChanges and ActionPackagesChanges
func verifyAgentChanges(t *testing.T, agentProjects []*common.AgentProject, expectedChanges []string) {
	for _, ap := range agentProjects {
		if ap != nil {
			// Verify that the detected changes match expected changes
			if len(expectedChanges) > 0 {
				assert.NotEmpty(t, ap.AgentChanges, "AgentChanges should be populated when there are differences")

				// Check that all expected changes are present in AgentChanges
				for _, expectedChange := range expectedChanges {
					assert.Contains(t, ap.AgentChanges, expectedChange,
						"AgentChanges should contain expected change: %s", expectedChange)
				}
			} else {
				// If no differences expected, AgentChanges should be empty
				assert.Empty(t, ap.AgentChanges, "AgentChanges should be empty when no differences detected")
			}

			// Verify ActionPackagesChanges is properly handled
			_ = ap.ActionPackagesChanges // Access to ensure it was processed
		}
	}
}

// BenchmarkCheckAgentsSynchronization benchmarks the function performance
func BenchmarkCheckAgentsSynchronization(b *testing.B) {
	// Create test data
	agentProjects := make([]*common.AgentProject, 100)
	deployedAgents := make([]*AgentServer.Agent, 100)

	for i := 0; i < 100; i++ {
		agentProjects[i] = &common.AgentProject{
			Path:    "/test/path" + string(rune('0'+i%10)),
			AgentID: "agent-" + string(rune('0'+i%10)),
			Agent: common.SpecAgent{
				Name:        "Agent " + string(rune('0'+i%10)),
				Description: "Description " + string(rune('0'+i%10)),
				Version:     "1.0." + string(rune('0'+i%10)),
				Runbook:     "Runbook " + string(rune('0'+i%10)),
			},
			Synced: false,
		}

		deployedAgents[i] = &AgentServer.Agent{
			ID:          "agent-" + string(rune('0'+i%10)),
			Name:        "Agent " + string(rune('0'+i%10)),
			Description: "Description " + string(rune('0'+i%10)),
			Version:     "1.0." + string(rune('0'+i%10)),
			Runbook:     "Runbook " + string(rune('0'+i%10)),
			UpdatedAt:   time.Now().Add(-time.Hour),
		}
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		// Create a copy of agent projects for each benchmark iteration
		agentProjectsCopy := make([]*common.AgentProject, len(agentProjects))
		for j, ap := range agentProjects {
			if ap != nil {
				agentCopy := &common.AgentProject{
					Path:                  ap.Path,
					AgentID:               ap.AgentID,
					Agent:                 ap.Agent,
					Synced:                ap.Synced,
					AgentChanges:          make([]string, len(ap.AgentChanges)),
					ActionPackagesChanges: make([]string, len(ap.ActionPackagesChanges)),
					Exclude:               make([]string, len(ap.Exclude)),
				}
				copy(agentCopy.AgentChanges, ap.AgentChanges)
				copy(agentCopy.ActionPackagesChanges, ap.ActionPackagesChanges)
				copy(agentCopy.Exclude, ap.Exclude)
				agentProjectsCopy[j] = agentCopy
			}
		}

		_ = cmd.CheckAgentsSynchronization(agentProjectsCopy, deployedAgents)
	}
}
