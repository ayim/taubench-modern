package tests

import (
	"os"
	"testing"

	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/cmd"
	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/common"
	"github.com/stretchr/testify/assert"

	"path/filepath"

	AgentServer "github.com/Sema4AI/agent-platform/packages/golang-agent-cli/agent-server-client"
)

func TestReadSpecV2_1Empty(t *testing.T) {
	common.Verbose = true
	spec, err := cmd.ReadSpec("./fixtures/agent-specs/agent-spec-v2.1-empty")
	if err != nil {
		t.Errorf("error: %+v", err)
	}
	assert.Equal(t, "v2", spec.AgentPackage.SpecVersion, "agent metadata should have correct Version")
}

func TestReadSpecV2_1(t *testing.T) {
	common.Verbose = true
	spec, err := cmd.ReadSpec("./fixtures/agent-specs/agent-spec-v2.1")
	if err != nil {
		t.Errorf("error: %+v", err)
	}

	assert.Equal(t, "v2", spec.AgentPackage.SpecVersion, "agent metadata should have correct Version")
	assert.Equal(t, common.Ptr("application/json"), spec.AgentPackage.Agents[0].McpServers[0].Env["CONTENT_TYPE"].Value, "agent metadata should have correct Value")
	assert.Equal(t, common.SpecMcpTypeSecret, spec.AgentPackage.Agents[0].McpServers[0].Env["MCP_API_KEY"].Type, "agent metadata should have correct Type")
	assert.Equal(t, common.SpecMcpTypeOAuth2Secret, spec.AgentPackage.Agents[0].McpServers[0].Env["MY_OAUTH2_API_KEY"].Type, "agent metadata should have correct Type")
	assert.Equal(t, 2, len(spec.AgentPackage.Agents[0].McpServers[0].Env["MY_OAUTH2_API_KEY"].Scopes), "agent metadata should have correct Scopes")
	assert.Equal(t, "Microsoft", spec.AgentPackage.Agents[0].McpServers[0].Env["MY_OAUTH2_API_KEY"].Provider, "agent metadata should have correct Provider")
	assert.Equal(t, common.SpecMcpTypeString, spec.AgentPackage.Agents[0].McpServers[0].Env["FILE_SYSTEM_ROOT"].Type, "agent metadata should have correct Provider")
	assert.Equal(t, "/data", *spec.AgentPackage.Agents[0].McpServers[0].Env["FILE_SYSTEM_ROOT"].Value, "agent metadata should have correct Provider")
}

func TestWriteSpecV2_1(t *testing.T) {
	common.Verbose = true
	spec, err := cmd.ReadSpec("./fixtures/agent-specs/agent-spec-v2.1")
	if err != nil {
		t.Errorf("error: %+v", err)
	}

	assert.Equal(t, "v2", spec.AgentPackage.SpecVersion, "agent metadata should have correct Version")
	assert.Equal(t, common.Ptr("application/json"), spec.AgentPackage.Agents[0].McpServers[0].Env["CONTENT_TYPE"].Value, "agent metadata should have correct Value")
	assert.Equal(t, common.SpecMcpTypeSecret, spec.AgentPackage.Agents[0].McpServers[0].Env["MCP_API_KEY"].Type, "agent metadata should have correct Type")
	assert.Equal(t, common.SpecMcpTypeOAuth2Secret, spec.AgentPackage.Agents[0].McpServers[0].Env["MY_OAUTH2_API_KEY"].Type, "agent metadata should have correct Type")
	assert.Equal(t, 2, len(spec.AgentPackage.Agents[0].McpServers[0].Env["MY_OAUTH2_API_KEY"].Scopes), "agent metadata should have correct Scopes")
	assert.Equal(t, "Microsoft", spec.AgentPackage.Agents[0].McpServers[0].Env["MY_OAUTH2_API_KEY"].Provider, "agent metadata should have correct Provider")
	assert.Equal(t, common.SpecMcpTypeString, spec.AgentPackage.Agents[0].McpServers[0].Env["FILE_SYSTEM_ROOT"].Type, "agent metadata should have correct Provider")
	assert.Equal(t, "/data", *spec.AgentPackage.Agents[0].McpServers[0].Env["FILE_SYSTEM_ROOT"].Value, "agent metadata should have correct Provider")
}

func TestWriteSpecStringMatchV2_1(t *testing.T) {
	common.Verbose = true

	spec, err := cmd.ReadSpec("./fixtures/agent-specs/agent-spec-v2.1")
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

	originalYamlBytes, err := os.ReadFile("./fixtures/agent-specs/agent-spec-v2.1/expected-agent-spec.yaml")
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
			SpecVersion: "v2",
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
	assert.Equal(t, "v2", filtered.AgentPackage.SpecVersion)
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
	if assert.NotNil(t, mcp.Headers["X-STRING"].Value) {
		assert.Equal(t, stringValue, *mcp.Headers["X-STRING"].Value)
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
	if assert.NotNil(t, mcp.Env["ENV-STRING"].Value) {
		assert.Equal(t, stringValue, *mcp.Env["ENV-STRING"].Value)
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
			SpecVersion: "v2",
			Agents:      []common.SpecAgent{},
		},
	}
	filtered := cmd.FilterMcpServerSecretValuesFromSpec(spec)
	assert.NotNil(t, filtered)
	assert.Equal(t, 0, len(filtered.AgentPackage.Agents))

	spec2 := &common.AgentSpec{
		AgentPackage: common.SpecAgentPackage{
			SpecVersion: "v2",
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
			SpecVersion: "v2",
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
			SpecVersion: "v2",
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

func TestReadSpecV2_1WithAgentSettings(t *testing.T) {
	common.Verbose = true
	spec, err := cmd.ReadSpec("./fixtures/agent-specs/agent-spec-v2.1-with-settings")
	if err != nil {
		t.Errorf("error: %+v", err)
	}

	assert.Equal(t, "v2", spec.AgentPackage.SpecVersion, "agent metadata should have correct Version")
	assert.Equal(t, "agent-with-settings", spec.AgentPackage.Agents[0].Name, "agent should have correct name")

	// Test agent settings
	agentSettings := spec.AgentPackage.Agents[0].AgentSettings
	assert.NotNil(t, agentSettings, "agent settings should not be nil")

	// Test various data types in agent settings
	assert.Equal(t, 30, agentSettings["api_timeout"], "api_timeout should be 30")
	assert.Equal(t, 3, agentSettings["max_retries"], "max_retries should be 3")
	assert.Equal(t, true, agentSettings["debug_mode"], "debug_mode should be true")
	assert.Equal(t, "You are a helpful assistant", agentSettings["custom_prompt"], "custom_prompt should match")
	assert.Equal(t, 0.7, agentSettings["temperature"], "temperature should be 0.7")

	// Test nested config (YAML parser uses map[interface{}]interface{})
	nestedConfigRaw, ok := agentSettings["nested_config"].(map[interface{}]interface{})
	assert.True(t, ok, "nested_config should be a map")

	// Convert string keys for easier access
	nestedConfig := make(map[string]interface{})
	for k, v := range nestedConfigRaw {
		nestedConfig[k.(string)] = v
	}

	databaseRaw, ok := nestedConfig["database"].(map[interface{}]interface{})
	assert.True(t, ok, "database should be a map")

	// Convert database map keys
	database := make(map[string]interface{})
	for k, v := range databaseRaw {
		database[k.(string)] = v
	}

	assert.Equal(t, "localhost", database["host"], "database host should be localhost")
	assert.Equal(t, 5432, database["port"], "database port should be 5432")
	assert.Equal(t, false, database["ssl_enabled"], "ssl_enabled should be false")

	features, ok := nestedConfig["features"].([]interface{})
	assert.True(t, ok, "features should be a slice")
	assert.Equal(t, 2, len(features), "features should have 2 items")
	assert.Equal(t, "feature1", features[0], "first feature should be feature1")
	assert.Equal(t, "feature2", features[1], "second feature should be feature2")
}

func TestWriteSpecV2_1WithAgentSettings(t *testing.T) {
	common.Verbose = true
	spec, err := cmd.ReadSpec("./fixtures/agent-specs/agent-spec-v2.1-with-settings")
	if err != nil {
		t.Errorf("error: %+v", err)
	}

	tempDir, err := os.MkdirTemp("", "writespec-agent-settings-test")
	if err != nil {
		t.Fatalf("failed to create temp dir: %+v", err)
	}
	defer os.RemoveAll(tempDir)

	err = cmd.WriteSpec(spec, tempDir)
	if err != nil {
		t.Fatalf("failed to write spec: %+v", err)
	}

	// Read back and verify agent settings are preserved
	writtenSpec, err := cmd.ReadSpec(tempDir)
	if err != nil {
		t.Fatalf("failed to read written spec: %+v", err)
	}

	writtenSettings := writtenSpec.AgentPackage.Agents[0].AgentSettings
	originalSettings := spec.AgentPackage.Agents[0].AgentSettings

	assert.Equal(t, originalSettings["api_timeout"], writtenSettings["api_timeout"], "api_timeout should be preserved")
	assert.Equal(t, originalSettings["max_retries"], writtenSettings["max_retries"], "max_retries should be preserved")
	assert.Equal(t, originalSettings["debug_mode"], writtenSettings["debug_mode"], "debug_mode should be preserved")
	assert.Equal(t, originalSettings["custom_prompt"], writtenSettings["custom_prompt"], "custom_prompt should be preserved")
	assert.Equal(t, originalSettings["temperature"], writtenSettings["temperature"], "temperature should be preserved")

	// Verify nested structure is preserved (handling YAML interface{} maps)
	originalNestedRaw := originalSettings["nested_config"].(map[interface{}]interface{})
	writtenNestedRaw := writtenSettings["nested_config"].(map[interface{}]interface{})

	// Convert to string-keyed maps for comparison
	originalNested := make(map[string]interface{})
	for k, v := range originalNestedRaw {
		originalNested[k.(string)] = v
	}

	writtenNested := make(map[string]interface{})
	for k, v := range writtenNestedRaw {
		writtenNested[k.(string)] = v
	}

	originalDbRaw := originalNested["database"].(map[interface{}]interface{})
	writtenDbRaw := writtenNested["database"].(map[interface{}]interface{})

	originalDb := make(map[string]interface{})
	for k, v := range originalDbRaw {
		originalDb[k.(string)] = v
	}

	writtenDb := make(map[string]interface{})
	for k, v := range writtenDbRaw {
		writtenDb[k.(string)] = v
	}

	assert.Equal(t, originalDb["host"], writtenDb["host"], "nested database host should be preserved")
	assert.Equal(t, originalDb["port"], writtenDb["port"], "nested database port should be preserved")
	assert.Equal(t, originalDb["ssl_enabled"], writtenDb["ssl_enabled"], "nested database ssl_enabled should be preserved")
}

func TestWriteSpecStringMatchV2_1WithAgentSettings(t *testing.T) {
	common.Verbose = true

	spec, err := cmd.ReadSpec("./fixtures/agent-specs/agent-spec-v2.1-with-settings")
	if err != nil {
		t.Fatalf("failed to read spec: %+v", err)
	}

	tempDir, err := os.MkdirTemp("", "writespec-stringmatch-agent-settings-test")
	if err != nil {
		t.Fatalf("failed to create temp dir: %+v", err)
	}
	defer os.RemoveAll(tempDir)

	err = cmd.WriteSpec(spec, tempDir)
	if err != nil {
		t.Fatalf("failed to write spec: %+v", err)
	}

	originalYamlBytes, err := os.ReadFile("./fixtures/agent-specs/agent-spec-v2.1-with-settings/expected-agent-spec.yaml")
	if err != nil {
		t.Fatalf("failed to read expected YAML: %+v", err)
	}
	originalYaml := string(originalYamlBytes)

	writtenYamlBytes, err := os.ReadFile(tempDir + "/agent-spec.yaml")
	if err != nil {
		t.Fatalf("failed to read written YAML: %+v", err)
	}
	writtenYaml := string(writtenYamlBytes)

	assert.YAMLEq(t, originalYaml, writtenYaml, "YAML written by WriteSpec should match the expected YAML string")
}

func TestSpecAgentIsEqualWithAgentSettings(t *testing.T) {
	baseSpec := common.SpecAgent{
		Name:         "agent1",
		Description:  "desc",
		Model:        common.SpecAgentModel{Provider: "OpenAI", Name: "gpt-4"},
		Version:      "1.0.0",
		Runbook:      "runbook.md",
		Architecture: "agent",
		Reasoning:    "disabled",
		Metadata:     AgentServer.AgentMetadata{Mode: AgentServer.ConversationalMode},
		AgentSettings: map[string]any{
			"timeout": 30,
			"debug":   true,
			"config": map[string]interface{}{
				"key": "value",
			},
		},
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
		Extra: AgentServer.AgentExtra{
			AgentSettings: map[string]any{
				"timeout": 30,
				"debug":   true,
				"config": map[string]interface{}{
					"key": "value",
				},
			},
		},

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
			name:     "agent settings same",
			spec:     baseSpec,
			deployed: baseDeployed,
			expectEq: true,
			expectCh: nil,
		},
		{
			name: "agent settings differ - simple value",
			spec: func() common.SpecAgent {
				s := baseSpec
				s.AgentSettings = map[string]any{
					"timeout": 60, // different value
					"debug":   true,
					"config": map[string]interface{}{
						"key": "value",
					},
				}
				return s
			}(),
			deployed: baseDeployed,
			expectEq: false,
			expectCh: []string{"agentSettings"},
		},
		{
			name: "agent settings differ - nested value",
			spec: func() common.SpecAgent {
				s := baseSpec
				s.AgentSettings = map[string]any{
					"timeout": 30,
					"debug":   true,
					"config": map[string]interface{}{
						"key": "different_value", // different nested value
					},
				}
				return s
			}(),
			deployed: baseDeployed,
			expectEq: false,
			expectCh: []string{"agentSettings"},
		},
		{
			name: "agent settings differ - missing key",
			spec: func() common.SpecAgent {
				s := baseSpec
				s.AgentSettings = map[string]any{
					"timeout": 30,
					"debug":   true,
					// missing "config" key
				}
				return s
			}(),
			deployed: baseDeployed,
			expectEq: false,
			expectCh: []string{"agentSettings"},
		},
		{
			name: "agent settings nil vs empty",
			spec: func() common.SpecAgent {
				s := baseSpec
				s.AgentSettings = nil
				return s
			}(),
			deployed: func() AgentServer.Agent {
				d := baseDeployed
				d.Extra.AgentSettings = map[string]any{}
				return d
			}(),
			expectEq: true, // nil and empty map should be considered equal
			expectCh: nil,
		},
		{
			name: "agent settings empty vs nil",
			spec: func() common.SpecAgent {
				s := baseSpec
				s.AgentSettings = map[string]any{}
				return s
			}(),
			deployed: func() AgentServer.Agent {
				d := baseDeployed
				d.Extra.AgentSettings = nil
				return d
			}(),
			expectEq: true, // empty map and nil should be considered equal
			expectCh: nil,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			eq, changes := tt.spec.IsEqual(&common.AgentProject{}, &tt.deployed)
			if !tt.expectEq && eq {
				t.Logf("Expected not equal but got equal for test: %s", tt.name)
			}
			if tt.expectEq && !eq {
				t.Logf("Expected equal but got not equal for test: %s", tt.name)
				t.Logf("Changes: %v", changes)
				t.Logf("Spec AgentSettings: %+v", tt.spec.AgentSettings)
				t.Logf("Deployed AgentSettings: %+v", tt.deployed.AgentSettings)
			}
			assert.Equal(t, tt.expectEq, eq)
			if tt.expectCh != nil {
				assert.ElementsMatch(t, tt.expectCh, changes)
			} else {
				assert.Empty(t, changes)
			}
		})
	}
}

func TestFilterAgentSettingsFromSpec(t *testing.T) {
	spec := &common.AgentSpec{
		AgentPackage: common.SpecAgentPackage{
			SpecVersion: "v2",
			Agents: []common.SpecAgent{
				{
					Name:         "agent1",
					Description:  "desc",
					Model:        common.SpecAgentModel{Provider: "OpenAI", Name: "gpt-4"},
					Version:      "1.0.0",
					Runbook:      "runbook.md",
					Architecture: "agent",
					Reasoning:    "disabled",
					Metadata:     AgentServer.AgentMetadata{Mode: AgentServer.ConversationalMode},
					AgentSettings: map[string]any{
						"api_key":    "secret-key-should-be-preserved",
						"timeout":    30,
						"debug_mode": true,
						"config_url": "http://example.com",
						"nested_config": map[string]interface{}{
							"database": map[string]interface{}{
								"password": "secret-password",
								"host":     "localhost",
								"port":     5432,
							},
							"features": []interface{}{"feature1", "feature2"},
						},
					},
					ActionPackages: []common.SpecAgentActionPackage{{
						Name:         "ap1",
						Organization: "MyActions",
						Type:         "folder",
						Version:      "0.1.0",
						Whitelist:    "",
					}},
					McpServers: []common.SpecMcpServer{},
				},
			},
		},
	}

	// Currently, agent settings are not filtered - they are preserved as-is
	// This test verifies that agent settings are NOT filtered (unlike MCP server secrets)
	filtered := cmd.FilterMcpServerSecretValuesFromSpec(spec)
	assert.NotNil(t, filtered)
	assert.Equal(t, "v2", filtered.AgentPackage.SpecVersion)
	assert.Equal(t, 1, len(filtered.AgentPackage.Agents))

	agent := filtered.AgentPackage.Agents[0]
	assert.NotNil(t, agent.AgentSettings)

	// All agent settings should be preserved (not filtered like MCP secrets)
	assert.Equal(t, "secret-key-should-be-preserved", agent.AgentSettings["api_key"])
	assert.Equal(t, 30, agent.AgentSettings["timeout"])
	assert.Equal(t, true, agent.AgentSettings["debug_mode"])
	assert.Equal(t, "http://example.com", agent.AgentSettings["config_url"])

	// Nested structures should also be preserved
	// This test creates data programmatically, so it uses string-keyed maps
	nestedConfig, ok := agent.AgentSettings["nested_config"].(map[string]interface{})
	assert.True(t, ok, "nested_config should be preserved")

	database, ok := nestedConfig["database"].(map[string]interface{})
	assert.True(t, ok, "database config should be preserved")
	assert.Equal(t, "secret-password", database["password"])
	assert.Equal(t, "localhost", database["host"])
	assert.Equal(t, 5432, database["port"])

	features, ok := nestedConfig["features"].([]interface{})
	assert.True(t, ok, "features should be preserved")
	assert.Equal(t, 2, len(features))
	assert.Equal(t, "feature1", features[0])
	assert.Equal(t, "feature2", features[1])
}
