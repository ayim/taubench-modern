package tests

import (
	"os"
	"testing"

	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/cmd"
	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/common"
	"github.com/stretchr/testify/assert"

	"path/filepath"

	AgentServer "github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/agent-server-client"
)

func TestReadSpecV3Empty(t *testing.T) {
	common.Verbose = true
	spec, err := cmd.ReadSpec("./fixtures/agent-specs/agent-spec-v3-empty")
	if err != nil {
		t.Errorf("error: %+v", err)
	}
	assert.Equal(t, "v3", spec.AgentPackage.SpecVersion, "agent metadata should have correct Version")
}

func TestReadSpecV3(t *testing.T) {
	common.Verbose = true
	spec, err := cmd.ReadSpec("./fixtures/agent-specs/agent-spec-v3")
	if err != nil {
		t.Errorf("error: %+v", err)
	}

	assert.Equal(t, "v3", spec.AgentPackage.SpecVersion, "agent metadata should have correct Version")
	assert.Equal(t, common.Ptr("application/json"), spec.AgentPackage.Agents[0].McpServers[0].Env["CONTENT_TYPE"].Value, "agent metadata should have correct Value")
	assert.Equal(t, common.SpecMcpTypeSecret, spec.AgentPackage.Agents[0].McpServers[0].Env["MCP_API_KEY"].Type, "agent metadata should have correct Type")
	assert.Equal(t, common.SpecMcpTypeOAuth2Secret, spec.AgentPackage.Agents[0].McpServers[0].Env["MY_OAUTH2_API_KEY"].Type, "agent metadata should have correct Type")
	assert.Equal(t, 2, len(spec.AgentPackage.Agents[0].McpServers[0].Env["MY_OAUTH2_API_KEY"].Scopes), "agent metadata should have correct Scopes")
	assert.Equal(t, "Microsoft", spec.AgentPackage.Agents[0].McpServers[0].Env["MY_OAUTH2_API_KEY"].Provider, "agent metadata should have correct Provider")
	assert.Equal(t, common.SpecMcpTypeString, spec.AgentPackage.Agents[0].McpServers[0].Env["FILE_SYSTEM_ROOT"].Type, "agent metadata should have correct Provider")
	assert.Equal(t, "/data", spec.AgentPackage.Agents[0].McpServers[0].Env["FILE_SYSTEM_ROOT"].Default, "agent metadata should have correct Provider")
}

func TestWriteSpecV3(t *testing.T) {
	common.Verbose = true
	spec, err := cmd.ReadSpec("./fixtures/agent-specs/agent-spec-v3")
	if err != nil {
		t.Errorf("error: %+v", err)
	}

	assert.Equal(t, "v3", spec.AgentPackage.SpecVersion, "agent metadata should have correct Version")
	assert.Equal(t, common.Ptr("application/json"), spec.AgentPackage.Agents[0].McpServers[0].Env["CONTENT_TYPE"].Value, "agent metadata should have correct Value")
	assert.Equal(t, common.SpecMcpTypeSecret, spec.AgentPackage.Agents[0].McpServers[0].Env["MCP_API_KEY"].Type, "agent metadata should have correct Type")
	assert.Equal(t, common.SpecMcpTypeOAuth2Secret, spec.AgentPackage.Agents[0].McpServers[0].Env["MY_OAUTH2_API_KEY"].Type, "agent metadata should have correct Type")
	assert.Equal(t, 2, len(spec.AgentPackage.Agents[0].McpServers[0].Env["MY_OAUTH2_API_KEY"].Scopes), "agent metadata should have correct Scopes")
	assert.Equal(t, "Microsoft", spec.AgentPackage.Agents[0].McpServers[0].Env["MY_OAUTH2_API_KEY"].Provider, "agent metadata should have correct Provider")
	assert.Equal(t, common.SpecMcpTypeString, spec.AgentPackage.Agents[0].McpServers[0].Env["FILE_SYSTEM_ROOT"].Type, "agent metadata should have correct Provider")
	assert.Equal(t, "/data", spec.AgentPackage.Agents[0].McpServers[0].Env["FILE_SYSTEM_ROOT"].Default, "agent metadata should have correct Provider")
}

func TestWriteSpecStringMatchV3(t *testing.T) {
	common.Verbose = true

	spec, err := cmd.ReadSpec("./fixtures/agent-specs/agent-spec-v3")
	if err != nil {
		t.Fatalf("failed to read spec: %+v", err)
	}

	tempDir, err := os.MkdirTemp("", "writespec-test")
	if err != nil {
		t.Fatalf("failed to create temp dir: %+v", err)
	}
	defer os.RemoveAll(tempDir)

	err = cmd.WriteSpec(spec, tempDir)
	if err != nil {
		t.Fatalf("failed to write spec: %+v", err)
	}

	originalYamlBytes, err := os.ReadFile("./fixtures/agent-specs/agent-spec-v3/expected-agent-spec.yaml")
	if err != nil {
		t.Fatalf("failed to read written YAML: %+v", err)
	}
	originalYaml := string(originalYamlBytes)

	writtenYamlBytes, err := os.ReadFile(tempDir + "/agent-spec.yaml")
	if err != nil {
		t.Fatalf("failed to read written YAML: %+v", err)
	}
	writtenYaml := string(writtenYamlBytes)

	assert.Equal(t, originalYaml, writtenYaml, "YAML written by WriteSpec should match the marshaled YAML string")
}

func TestCreateConversationGuideFile(t *testing.T) {
	// Prepare a mock agent with QuestionGroups
	agent := AgentServer.Agent{
		ID:   "test-agent-id",
		Name: "Test Agent",
		Metadata: AgentServer.AgentMetadata{
			QuestionGroups: AgentServer.QuestionGroups{
				{
					Title:     "Getting Started",
					Questions: []string{"What can you do?", "How do I use this agent?"},
				},
				{
					Title:     "Advanced Usage",
					Questions: []string{"How do I connect to a database?", "Can you automate file management?"},
				},
				{
					Title:     "Test Title",
					Questions: []string{"Testing me?"},
				},
			},
		},
	}

	tmpDir, err := common.CreateTempDir("test-conv-guide-test")
	if err != nil {
		t.Fatalf("failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	state := &cmd.SpecState{
		AssistantConversationGuides: map[string]string{},
	}
	err = state.CreateConversationGuideFile([]AgentServer.Agent{agent}, tmpDir)
	if err != nil {
		t.Fatalf("createConversationGuideFile failed: %v", err)
	}

	// Read the generated YAML file
	convGuidePath := filepath.Join(tmpDir, "conversation-guide.yaml")
	data, err := os.ReadFile(convGuidePath)
	if err != nil {
		t.Fatalf("failed to read conversation-guide.yaml: %v", err)
	}

	expectedYAML := `question-groups:
- title: Getting Started
  questions:
  - What can you do?
  - How do I use this agent?
- title: Advanced Usage
  questions:
  - How do I connect to a database?
  - Can you automate file management?
- title: Test Title
  questions:
  - Testing me?
`
	assert.YAMLEq(t, expectedYAML, string(data), "conversation-guide.yaml content should match expected YAML")
}

func TestFilterMcpServerSecretValuesFromSpec(t *testing.T) {
	secretValue := "secret-should-be-removed"
	stringValue := "string-should-stay"
	oauth2Value := "oauth2-should-be-removed"
	rawValue := "raw-should-stay"
	dataServerInfoValue := "dataserverinfo-should-stay"

	spec := &common.AgentSpec{
		AgentPackage: common.SpecAgentPackage{
			SpecVersion: "v3",
			Agents: []common.SpecAgent{
				{
					Name: "agent1",
					McpServers: []common.SpecMcpServer{
						{
							Name: "mcp1",
							Headers: common.SpecMcpServerVariables{
								"X-SECRET": common.SpecMcpServerVariable{
									Type:  common.SpecMcpTypeSecret,
									Value: &secretValue,
								},
								"X-STRING": common.SpecMcpServerVariable{
									Type:  common.SpecMcpTypeString,
									Value: &stringValue,
								},
								"X-OAUTH2": common.SpecMcpServerVariable{
									Type:  common.SpecMcpTypeOAuth2Secret,
									Value: &oauth2Value,
								},
								"X-RAW": common.SpecMcpServerVariable{
									Value: &rawValue,
								},
								"X-DATAINFO": common.SpecMcpServerVariable{
									Type:  common.SpecMcpTypeDataServerInfo,
									Value: &dataServerInfoValue,
								},
							},
							Env: common.SpecMcpServerVariables{
								"ENV-SECRET": common.SpecMcpServerVariable{
									Type:  common.SpecMcpTypeSecret,
									Value: &secretValue,
								},
								"ENV-STRING": common.SpecMcpServerVariable{
									Type:  common.SpecMcpTypeString,
									Value: &stringValue,
								},
								"ENV-OAUTH2": common.SpecMcpServerVariable{
									Type:  common.SpecMcpTypeOAuth2Secret,
									Value: &oauth2Value,
								},
								"ENV-RAW": common.SpecMcpServerVariable{
									Value: &rawValue,
								},
								"ENV-DATAINFO": common.SpecMcpServerVariable{
									Type:  common.SpecMcpTypeDataServerInfo,
									Value: &dataServerInfoValue,
								},
							},
						},
					},
				},
			},
		},
	}

	filtered := cmd.FilterMcpServerSecretValuesFromSpec(spec)
	assert.NotNil(t, filtered)
	assert.Equal(t, "v3", filtered.AgentPackage.SpecVersion)
	assert.Equal(t, 1, len(filtered.AgentPackage.Agents))
	agent := filtered.AgentPackage.Agents[0]
	assert.Equal(t, 1, len(agent.McpServers))
	mcp := agent.McpServers[0]

	assert.Contains(t, mcp.Headers, "X-SECRET")
	assert.Contains(t, mcp.Headers, "X-STRING")
	assert.Contains(t, mcp.Headers, "X-OAUTH2")
	assert.Contains(t, mcp.Headers, "X-RAW")
	assert.Contains(t, mcp.Headers, "X-DATAINFO")
	assert.Nil(t, mcp.Headers["X-SECRET"].Value)
	if assert.Nil(t, mcp.Headers["X-STRING"].Value) {
		assert.Equal(t, stringValue, mcp.Headers["X-STRING"].Default)
	}
	assert.Nil(t, mcp.Headers["X-OAUTH2"].Value)
	if assert.NotNil(t, mcp.Headers["X-RAW"].Value) {
		assert.Equal(t, rawValue, *mcp.Headers["X-RAW"].Value)
	}
	assert.Contains(t, mcp.Headers, "X-DATAINFO")
	if assert.NotNil(t, mcp.Headers["X-DATAINFO"].Value) {
		assert.Equal(t, dataServerInfoValue, *mcp.Headers["X-DATAINFO"].Value)
	}

	assert.Contains(t, mcp.Env, "ENV-SECRET")
	assert.Contains(t, mcp.Env, "ENV-STRING")
	assert.Contains(t, mcp.Env, "ENV-OAUTH2")
	assert.Contains(t, mcp.Env, "ENV-RAW")
	assert.Nil(t, mcp.Env["ENV-SECRET"].Value)
	if assert.Nil(t, mcp.Env["ENV-STRING"].Value) {
		assert.Equal(t, stringValue, mcp.Env["ENV-STRING"].Default)
	}
	assert.Nil(t, mcp.Env["ENV-OAUTH2"].Value)
	if assert.NotNil(t, mcp.Env["ENV-RAW"].Value) {
		assert.Equal(t, rawValue, *mcp.Env["ENV-RAW"].Value)
	}
	assert.Contains(t, mcp.Env, "ENV-DATAINFO")
	if assert.NotNil(t, mcp.Env["ENV-DATAINFO"].Value) {
		assert.Equal(t, dataServerInfoValue, *mcp.Env["ENV-DATAINFO"].Value)
	}
}

func TestFilterMcpServerSecretValuesFromSpec_EmptyCases(t *testing.T) {
	spec := &common.AgentSpec{
		AgentPackage: common.SpecAgentPackage{
			SpecVersion: "v3",
			Agents:      []common.SpecAgent{},
		},
	}
	filtered := cmd.FilterMcpServerSecretValuesFromSpec(spec)
	assert.NotNil(t, filtered)
	assert.Equal(t, 0, len(filtered.AgentPackage.Agents))

	spec2 := &common.AgentSpec{
		AgentPackage: common.SpecAgentPackage{
			SpecVersion: "v3",
			Agents: []common.SpecAgent{{
				Name:       "agent1",
				McpServers: nil,
			}},
		},
	}
	filtered2 := cmd.FilterMcpServerSecretValuesFromSpec(spec2)
	assert.Equal(t, 1, len(filtered2.AgentPackage.Agents))
	assert.Equal(t, 0, len(filtered2.AgentPackage.Agents[0].McpServers))

	spec3 := &common.AgentSpec{
		AgentPackage: common.SpecAgentPackage{
			SpecVersion: "v3",
			Agents: []common.SpecAgent{{
				Name:       "agent1",
				McpServers: []common.SpecMcpServer{{}},
			}},
		},
	}
	filtered3 := cmd.FilterMcpServerSecretValuesFromSpec(spec3)
	assert.Equal(t, 1, len(filtered3.AgentPackage.Agents))
	assert.Equal(t, 1, len(filtered3.AgentPackage.Agents[0].McpServers))
}

func TestSpecAgentIsEqual(t *testing.T) {
	baseSpec := common.SpecAgent{
		Name:         "agent1",
		Description:  "desc",
		Model:        common.SpecAgentModel{Provider: "OpenAI", Name: "gpt-4"},
		Version:      "1.0.0",
		Runbook:      "runbook.md",
		Architecture: "agent",
		Reasoning:    "disabled",
		Metadata:     AgentServer.AgentMetadata{Mode: AgentServer.ConversationalMode},
		ActionPackages: []common.SpecAgentActionPackage{{
			Name:         "ap1",
			Organization: "MyActions",
			Type:         "folder",
			Version:      "0.1.0",
			Whitelist:    "",
		}},
		McpServers: []common.SpecMcpServer{{
			Name:      "mcp1",
			Transport: AgentServer.MCPTransportAuto,
			URL:       "http://",
		}},
	}
	baseDeployed := AgentServer.Agent{
		Name:        baseSpec.Name,
		Description: baseSpec.Description,
		Model:       AgentServer.AgentModel{Provider: "OpenAI", Name: "gpt-4"},
		Version:     baseSpec.Version,
		Runbook:     baseSpec.Runbook,
		AdvancedConfig: AgentServer.AgentAdvancedConfig{
			Architecture: "agent",
			Reasoning:    "disabled",
		},
		Metadata: AgentServer.AgentMetadata{Mode: AgentServer.ConversationalMode},
		ActionPackages: []AgentServer.AgentActionPackage{{
			Name:         "ap1",
			Organization: "MyActions",
			Version:      "0.1.0",
			Whitelist:    "",
		}},
		McpServers: []AgentServer.McpServer{{
			Name:      "mcp1",
			Transport: AgentServer.MCPTransportAuto,
			URL:       common.Ptr("http://"),
		}},
	}

	tests := []struct {
		name     string
		spec     common.SpecAgent
		deployed AgentServer.Agent
		expectEq bool
		expectCh []string
	}{
		{
			name:     "all fields equal",
			spec:     baseSpec,
			deployed: baseDeployed,
			expectEq: true,
			expectCh: nil,
		},
		{
			name:     "name differs",
			spec:     func() common.SpecAgent { s := baseSpec; s.Name = "other"; return s }(),
			deployed: baseDeployed,
			expectEq: false,
			expectCh: []string{"name"},
		},
		{
			name:     "description differs",
			spec:     func() common.SpecAgent { s := baseSpec; s.Description = "other"; return s }(),
			deployed: baseDeployed,
			expectEq: false,
			expectCh: []string{"description"},
		},
		{
			name:     "model provider differs",
			spec:     func() common.SpecAgent { s := baseSpec; s.Model.Provider = "Azure"; return s }(),
			deployed: baseDeployed,
			expectEq: false,
			expectCh: []string{"modelProvider"},
		},
		{
			name:     "version differs",
			spec:     func() common.SpecAgent { s := baseSpec; s.Version = "2.0.0"; return s }(),
			deployed: baseDeployed,
			expectEq: false,
			expectCh: []string{"version"},
		},
		{
			name:     "architecture differs",
			spec:     func() common.SpecAgent { s := baseSpec; s.Architecture = "plan_execute"; return s }(),
			deployed: baseDeployed,
			expectEq: false,
			expectCh: []string{"architecture"},
		},
		{
			name:     "reasoning differs",
			spec:     func() common.SpecAgent { s := baseSpec; s.Reasoning = "enabled"; return s }(),
			deployed: baseDeployed,
			expectEq: false,
			expectCh: []string{"reasoning"},
		},
		{
			name:     "runbook differs",
			spec:     func() common.SpecAgent { s := baseSpec; s.Runbook = "other"; return s }(),
			deployed: baseDeployed,
			expectEq: false,
			expectCh: []string{"runbook"},
		},
		{
			name:     "metadata differs",
			spec:     func() common.SpecAgent { s := baseSpec; s.Metadata.Mode = "worker"; return s }(),
			deployed: baseDeployed,
			expectEq: false,
			expectCh: []string{"metadata"},
		},
		{
			name:     "actionPackages differs",
			spec:     func() common.SpecAgent { s := baseSpec; s.ActionPackages = nil; return s }(),
			deployed: baseDeployed,
			expectEq: false,
			expectCh: []string{"actionPackages"},
		},
		{
			name:     "mcpServers differs",
			spec:     func() common.SpecAgent { s := baseSpec; s.McpServers = nil; return s }(),
			deployed: baseDeployed,
			expectEq: false,
			expectCh: []string{"mcpServers"},
		},
		{
			name: "mcpServer header type differs",
			spec: func() common.SpecAgent {
				s := baseSpec
				s.McpServers = []common.SpecMcpServer{{
					Name:      "mcp1",
					Transport: AgentServer.MCPTransportAuto,
					URL:       "http://",
					Headers: common.SpecMcpServerVariables{
						"X-API-KEY": {
							Type:  common.SpecMcpTypeSecret,
							Value: common.Ptr("secret-value"),
						},
					},
				}}
				return s
			}(),
			deployed: func() AgentServer.Agent {
				d := baseDeployed
				d.McpServers = []AgentServer.McpServer{{
					Name:      "mcp1",
					Transport: AgentServer.MCPTransportAuto,
					URL:       common.Ptr("http://"),
					Headers: AgentServer.McpServerVariables{
						"X-API-KEY": {
							Type:  "string",
							Value: common.Ptr("secret-value"),
						},
					},
				}}
				return d
			}(),
			expectEq: false,
			expectCh: []string{"mcpServers"},
		},
		{
			name: "mcpServer header type same",
			spec: func() common.SpecAgent {
				s := baseSpec
				s.McpServers = []common.SpecMcpServer{{
					Name:      "mcp1",
					Transport: AgentServer.MCPTransportAuto,
					URL:       "http://",
					Headers: common.SpecMcpServerVariables{
						"X-API-KEY": {
							Type:  common.SpecMcpTypeSecret,
							Value: common.Ptr("secret-value"),
						},
					},
				}}
				return s
			}(),
			deployed: func() AgentServer.Agent {
				d := baseDeployed
				d.McpServers = []AgentServer.McpServer{{
					Name:      "mcp1",
					Transport: AgentServer.MCPTransportAuto,
					URL:       common.Ptr("http://"),
					Headers: AgentServer.McpServerVariables{
						"X-API-KEY": {
							Type:  "secret",
							Value: common.Ptr("secret-value"),
						},
					},
				}}
				return d
			}(),
			expectEq: true,
			expectCh: nil,
		},
		{
			name: "mcpServer header raw string same",
			spec: func() common.SpecAgent {
				s := baseSpec
				s.McpServers = []common.SpecMcpServer{{
					Name:      "mcp1",
					Transport: AgentServer.MCPTransportAuto,
					URL:       "http://",
					Headers: common.SpecMcpServerVariables{
						"X-API-KEY": {
							Value: common.Ptr("secret-value"),
						},
					},
				}}
				return s
			}(),
			deployed: func() AgentServer.Agent {
				d := baseDeployed
				d.McpServers = []AgentServer.McpServer{{
					Name:      "mcp1",
					Transport: AgentServer.MCPTransportAuto,
					URL:       common.Ptr("http://"),
					Headers: AgentServer.McpServerVariables{
						"X-API-KEY": {
							Value: common.Ptr("secret-value"),
						},
					},
				}}
				return d
			}(),
			expectEq: true,
			expectCh: nil,
		},
		{
			name: "mcpServer header raw string different value",
			spec: func() common.SpecAgent {
				s := baseSpec
				s.McpServers = []common.SpecMcpServer{{
					Name:      "mcp1",
					Transport: AgentServer.MCPTransportAuto,
					URL:       "http://",
					Headers: common.SpecMcpServerVariables{
						"X-API-KEY": {
							Value: common.Ptr("secret-value"),
						},
					},
				}}
				return s
			}(),
			deployed: func() AgentServer.Agent {
				d := baseDeployed
				d.McpServers = []AgentServer.McpServer{{
					Name:      "mcp1",
					Transport: AgentServer.MCPTransportAuto,
					URL:       common.Ptr("http://"),
					Headers: AgentServer.McpServerVariables{
						"X-API-KEY": {
							Value: common.Ptr("secret-value-change"),
						},
					},
				}}
				return d
			}(),
			expectEq: false,
			expectCh: []string{"mcpServers"},
		},
		{
			name: "mcpServer header raw string different types _ same value",
			spec: func() common.SpecAgent {
				s := baseSpec
				s.McpServers = []common.SpecMcpServer{{
					Name:      "mcp1",
					Transport: AgentServer.MCPTransportAuto,
					URL:       "http://",
					Headers: common.SpecMcpServerVariables{
						"X-API-KEY": {
							Value: common.Ptr("secret-value"),
						},
					},
				}}
				return s
			}(),
			deployed: func() AgentServer.Agent {
				d := baseDeployed
				d.McpServers = []AgentServer.McpServer{{
					Name:      "mcp1",
					Transport: AgentServer.MCPTransportAuto,
					URL:       common.Ptr("http://"),
					Headers: AgentServer.McpServerVariables{
						"X-API-KEY": {
							Type:  "secret",
							Value: common.Ptr("secret-value"),
						},
					},
				}}
				return d
			}(),
			expectEq: false,
			expectCh: []string{"mcpServers"},
		},
		{
			name: "mcpServer header raw string different types _ entirely",
			spec: func() common.SpecAgent {
				s := baseSpec
				s.McpServers = []common.SpecMcpServer{{
					Name:      "mcp1",
					Transport: AgentServer.MCPTransportAuto,
					URL:       "http://",
					Headers: common.SpecMcpServerVariables{
						"X-API-KEY": {
							Value: common.Ptr("secret-value"),
						},
					},
				}}
				return s
			}(),
			deployed: func() AgentServer.Agent {
				d := baseDeployed
				d.McpServers = []AgentServer.McpServer{{
					Name:      "mcp1",
					Transport: AgentServer.MCPTransportAuto,
					URL:       common.Ptr("http://"),
					Headers: AgentServer.McpServerVariables{
						"X-API-KEY": {
							Type:     "oauth2-secret",
							Provider: "Google",
						},
					},
				}}
				return d
			}(),
			expectEq: false,
			expectCh: []string{"mcpServers"},
		},
		{
			name: "question groups differs",
			spec: func() common.SpecAgent {
				s := baseSpec
				s.Metadata.QuestionGroups = []AgentServer.QuestionGroup{{Title: "Getting Started", Questions: []string{"What can you do?"}}}
				return s
			}(),
			deployed: func() AgentServer.Agent {
				d := baseDeployed
				d.Metadata.QuestionGroups = []AgentServer.QuestionGroup{{Title: "Getting Started", Questions: []string{"How do I use this agent?"}}}
				return d
			}(),
			expectEq: false,
			expectCh: []string{"metadata"},
		},
		{
			name: "question groups same",
			spec: func() common.SpecAgent {
				s := baseSpec
				s.Metadata.QuestionGroups = []AgentServer.QuestionGroup{{Title: "Getting Started", Questions: []string{"What can you do?"}}}
				return s
			}(),
			deployed: func() AgentServer.Agent {
				d := baseDeployed
				d.Metadata.QuestionGroups = []AgentServer.QuestionGroup{{Title: "Getting Started", Questions: []string{"What can you do?"}}}
				return d
			}(),
			expectEq: true,
			expectCh: nil,
		},
		{
			name:     "welcome message differs",
			spec:     func() common.SpecAgent { s := baseSpec; s.Metadata.WelcomeMessage = "Hello!"; return s }(),
			deployed: func() AgentServer.Agent { d := baseDeployed; d.Metadata.WelcomeMessage = "Hi!"; return d }(),
			expectEq: false,
			expectCh: []string{"metadata"},
		},
		{
			name:     "welcome message same",
			spec:     func() common.SpecAgent { s := baseSpec; s.Metadata.WelcomeMessage = "Hello!"; return s }(),
			deployed: func() AgentServer.Agent { d := baseDeployed; d.Metadata.WelcomeMessage = "Hello!"; return d }(),
			expectEq: true,
			expectCh: nil,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			eq, changes := tt.spec.IsEqual(&common.AgentProject{}, &tt.deployed)
			assert.Equal(t, tt.expectEq, eq)
			if tt.expectCh != nil {
				assert.ElementsMatch(t, tt.expectCh, changes)
			} else {
				assert.Empty(t, changes)
			}
		})
	}
}

func TestSpecWriteFiltersQuestionGroupsFromMetadata(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "spec-question-groups-test")
	if err != nil {
		t.Fatalf("failed to create temp dir: %+v", err)
	}
	defer os.RemoveAll(tmpDir)

	spec := &common.AgentSpec{
		AgentPackage: common.SpecAgentPackage{
			SpecVersion: "v3",
			Agents: []common.SpecAgent{
				{
					Name:         "agent-with-qg",
					Description:  "desc",
					Model:        common.SpecAgentModel{Provider: "OpenAI", Name: "gpt-4"},
					Version:      "1.0.0",
					Runbook:      "runbook.md",
					Architecture: "agent",
					Reasoning:    "disabled",
					Metadata: AgentServer.AgentMetadata{
						Mode: AgentServer.ConversationalMode,
						QuestionGroups: AgentServer.QuestionGroups{
							{Title: "Getting Started", Questions: []string{"What can you do?"}},
						},
					},
				},
			},
		},
	}

	err = cmd.WriteSpec(spec, tmpDir)
	if err != nil {
		t.Fatalf("failed to write spec: %+v", err)
	}

	writtenYamlBytes, err := os.ReadFile(tmpDir + "/agent-spec.yaml")
	if err != nil {
		t.Fatalf("failed to read written YAML: %+v", err)
	}
	writtenYaml := string(writtenYamlBytes)

	// The metadata section should NOT contain question_groups or question-groups
	assert.Contains(t, writtenYaml, "mode: conversational", "Spec YAML should contain mode in metadata")
	assert.NotContains(t, writtenYaml, "question-groups", "Spec YAML should not contain question-groups in metadata")
}
