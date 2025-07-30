package tests

import (
	"testing"

	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/cmd"
	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/common"
	"github.com/stretchr/testify/assert"

	AgentServer "github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/agent-server-client"
)

// ==== GENERIC TESTS ====

func TestGenerateMcpServersMetadata_AutoTransport(t *testing.T) {
	// 1. URL contains '/sse' (should be accepted as a URL transport)
	mcp1 := common.SpecMcpServer{
		Name:      "auto-sse",
		Transport: AgentServer.MCPTransportAuto,
		URL:       "http://localhost:8080/sse",
	}
	result, err := cmd.GenerateMcpServersMetadata(mcp1)
	assert.NoError(t, err)
	if assert.NotNil(t, result) {
		assert.Equal(t, AgentServer.MCPTransportAuto, result.Transport)
		assert.Equal(t, mcp1.URL, result.URL)
	}

	// 2. URL is set but does not contain '/sse' (should be accepted as a URL transport)
	mcp2 := common.SpecMcpServer{
		Name:      "auto-http",
		Transport: AgentServer.MCPTransportAuto,
		URL:       "http://localhost:8080/api",
	}
	result, err = cmd.GenerateMcpServersMetadata(mcp2)
	assert.NoError(t, err)
	if assert.NotNil(t, result) {
		assert.Equal(t, AgentServer.MCPTransportAuto, result.Transport)
		assert.Equal(t, mcp2.URL, result.URL)
	}

	// 3. Only command is set (should be accepted as a stdio transport)
	mcp3 := common.SpecMcpServer{
		Name:        "auto-stdio",
		Transport:   AgentServer.MCPTransportAuto,
		CommandLine: []string{"mycmd", "arg1", "arg2"},
	}
	result, err = cmd.GenerateMcpServersMetadata(mcp3)
	assert.NoError(t, err)
	if assert.NotNil(t, result) {
		assert.Equal(t, AgentServer.MCPTransportAuto, result.Transport)
		assert.Equal(t, "mycmd", result.Command)
		assert.Equal(t, []string{"arg1", "arg2"}, result.Arguments)
	}

	// 4. Neither URL nor command is set (should be accepted as a stdio transport with empty command)
	mcp4 := common.SpecMcpServer{
		Name:      "auto-stdio-default",
		Transport: AgentServer.MCPTransportAuto,
	}
	result, err = cmd.GenerateMcpServersMetadata(mcp4)
	assert.NoError(t, err)
	if assert.NotNil(t, result) {
		assert.Equal(t, AgentServer.MCPTransportAuto, result.Transport)
		assert.Equal(t, "", result.Command)
		assert.Equal(t, "", result.URL)
	}

	// 5. Invalid: Both URL and command are set (should error)
	mcp5 := common.SpecMcpServer{
		Name:        "auto-invalid",
		Transport:   AgentServer.MCPTransportAuto,
		URL:         "http://localhost:8080/api",
		CommandLine: []string{"mycmd"},
	}
	_, err = cmd.GenerateMcpServersMetadata(mcp5)
	assert.Error(t, err)
}

// ==== V2 TESTS ====

func assertV2Metadata(t *testing.T, metadata []*common.AgentPackageMetadata) {
	// Basic metadata fields
	assert.Equal(t, "0.0.1", metadata[0].Version, "agent metadata should have correct Version")
	assert.Equal(t, "a1", metadata[0].Name, "agent metadata should have correct Name")
	assert.Equal(t, "a1", metadata[0].Description, "agent metadata should have correct Description")
	assert.Equal(t, AgentServer.ReasoningDisabled, metadata[0].Reasoning, "agent metadata should have correct Reasoning")
	assert.Equal(t, AgentServer.ConversationalMode, metadata[0].Metadata.Mode, "agent metadata should have correct Metadata.Mode")

	// Model fields
	assert.Equal(t, AgentServer.OpenAI, metadata[0].Model.Provider, "agent metadata should have correct Model.Provider")
	assert.Equal(t, "gpt-4o", metadata[0].Model.Name, "agent metadata should have correct Model.Name")

	// Architecture field
	assert.Equal(t, AgentServer.AgentKind, metadata[0].Architecture, "agent metadata should have correct Architecture")

	// Action packages
	assert.Equal(t, 1, len(metadata[0].ActionPackages), "agent metadata should have correct number of ActionPackages")
	assert.Equal(t, "Wind of Change", metadata[0].ActionPackages[0].Name, "agent metadata should have correct ActionPackages[0].Name")
	assert.Equal(t, "0.0.1", metadata[0].ActionPackages[0].Version, "agent metadata should have correct ActionPackages[0].Version")
	assert.Equal(t, 5, len(metadata[0].ActionPackages[0].Actions), "agent metadata should have correct ActionPackages[0].Actions")

	// Knowledge (should be empty for v2)
	assert.Equal(t, 0, len(metadata[0].Knowledge), "agent metadata should have empty Knowledge for v2")

	// Datasources (should be empty for v2)
	assert.Equal(t, 0, len(metadata[0].Datasources), "agent metadata should have empty Datasources for v2")

	// MCP Servers (should be empty for v2)
	assert.Equal(t, 0, len(metadata[0].McpServers), "agent metadata should have empty McpServers for v2")

	// Question Groups (should be empty for v2)
	assert.Nil(t, metadata[0].QuestionGroups, "agent metadata should have nil QuestionGroups for v2")

	// Conversation Starter (should be empty for v2)
	assert.Equal(t, "", metadata[0].ConversationStarter, "agent metadata should have empty ConversationStarter for v2")

	// Welcome Message (should be empty for v2)
	assert.Equal(t, "", metadata[0].WelcomeMessage, "agent metadata should have empty WelcomeMessage for v2")

	// Metadata fields
	assert.Equal(t, AgentServer.ConversationalMode, metadata[0].Metadata.Mode, "agent metadata should have correct Metadata.Mode")
	assert.Nil(t, metadata[0].Metadata.WorkerConfig, "agent metadata should have nil Metadata.WorkerConfig for v2")
	assert.Nil(t, metadata[0].Metadata.QuestionGroups, "agent metadata should have nil Metadata.QuestionGroups for v2")
	assert.Equal(t, "", metadata[0].Metadata.WelcomeMessage, "agent metadata should have empty Metadata.WelcomeMessage for v2")

	// Optional fields that should be empty for v2
	assert.Equal(t, "", metadata[0].ReleaseNote, "agent metadata should have empty ReleaseNote for v2")
	assert.Equal(t, "", metadata[0].Icon, "agent metadata should have empty Icon for v2")
}

func TestGenerateAgentMetadataFromPackageV2_ActionPackageDetails(t *testing.T) {
	common.Verbose = true
	metadata, err := cmd.GenerateAgentMetadataFromPackage("./fixtures/agent-packages/a-1.v2.zip")
	if err != nil {
		t.Errorf("error: %+v", err)
	}

	agent := metadata[0]

	// Test action package structure
	assert.Len(t, agent.ActionPackages, 1, "should have exactly one action package")
	actionPackage := agent.ActionPackages[0]

	// Test action package metadata fields
	assert.Equal(t, "Wind of Change", actionPackage.Name, "action package should have correct name")
	assert.Equal(t, "0.0.1", actionPackage.Version, "action package should have correct version")
	assert.Equal(t, "Predicts how the wind has changed or tells how the wind is now", actionPackage.Description, "action package should have correct description")
	assert.Equal(t, "", actionPackage.Whitelist, "action package should have empty whitelist")
	assert.NotEmpty(t, actionPackage.Icon, "action package should have icon")
	assert.Equal(t, "MyActions/wind-of-change", actionPackage.Path, "action package should have correct path")

	// Test action package secrets
	assert.NotNil(t, actionPackage.Secrets, "action package should have secrets map")
	assert.IsType(t, map[string]interface{}{}, actionPackage.Secrets, "secrets should be map[string]interface{}")

	// Test actions
	assert.Len(t, actionPackage.Actions, 5, "action package should have 5 actions")

	// Test each action has required fields
	for i, action := range actionPackage.Actions {
		assert.NotEmpty(t, action.Name, "action %d should have non-empty name", i)
		assert.NotEmpty(t, action.Description, "action %d should have non-empty description", i)
		assert.NotEmpty(t, action.Summary, "action %d should have non-empty summary", i)
		assert.NotEmpty(t, action.OperationKind, "action %d should have non-empty operation kind", i)

		// Test action field types
		assert.IsType(t, "", action.Name, "action.Name should be string")
		assert.IsType(t, "", action.Description, "action.Description should be string")
		assert.IsType(t, "", action.Summary, "action.Summary should be string")
		assert.IsType(t, "", action.OperationKind, "action.OperationKind should be string")
	}

	// Test external endpoints (should be empty for v2)
	assert.Empty(t, actionPackage.ExternalEndpoints, "action package should have empty external endpoints for v2")
}

func TestGenerateAgentMetadataFromPackageV2(t *testing.T) {
	common.Verbose = true
	metadata, err := cmd.GenerateAgentMetadataFromPackage("./fixtures/agent-packages/a-1.v2.zip")
	if err != nil {
		t.Errorf("error: %+v", err)
	}

	assertV2Metadata(t, metadata)
}

func TestGenerateAgentMetadataFromPackageV2_ComprehensiveFieldCheck(t *testing.T) {
	common.Verbose = true
	metadata, err := cmd.GenerateAgentMetadataFromPackage("./fixtures/agent-packages/a-1.v2.zip")
	if err != nil {
		t.Errorf("error: %+v", err)
	}

	// Test that we have exactly one agent
	assert.Equal(t, 1, len(metadata), "should have exactly one agent")

	agent := metadata[0]

	// Test all string fields
	assert.IsType(t, "", agent.Version, "Version should be a string")
	assert.IsType(t, "", agent.Name, "Name should be a string")
	assert.IsType(t, "", agent.Description, "Description should be a string")
	assert.IsType(t, "", agent.ReleaseNote, "ReleaseNote should be a string")
	assert.IsType(t, "", agent.Icon, "Icon should be a string")
	assert.IsType(t, "", agent.ConversationStarter, "ConversationStarter should be a string")
	assert.IsType(t, "", agent.WelcomeMessage, "WelcomeMessage should be a string")

	// Test model fields
	assert.IsType(t, AgentServer.AgentModelProvider(""), agent.Model.Provider, "Model.Provider should be AgentModelProvider")
	assert.IsType(t, "", agent.Model.Name, "Model.Name should be a string")

	// Test architecture and reasoning
	assert.IsType(t, AgentServer.AgentArchitecture(""), agent.Architecture, "Architecture should be AgentArchitecture")
	assert.IsType(t, AgentServer.AgentReasoning(""), agent.Reasoning, "Reasoning should be AgentReasoning")

	// Test slice fields
	assert.IsType(t, []common.AgentPackageMetadataKnowledge{}, agent.Knowledge, "Knowledge should be a slice")
	assert.IsType(t, []common.AgentPackageDatasource{}, agent.Datasources, "Datasources should be a slice")
	assert.IsType(t, []common.AgentPackageActionPackageMetadata{}, agent.ActionPackages, "ActionPackages should be a slice")
	assert.IsType(t, []common.AgentPackageMcpServer{}, agent.McpServers, "McpServers should be a slice")

	// Test metadata fields
	assert.IsType(t, AgentServer.AgentMetadata{}, agent.Metadata, "Metadata should be AgentMetadata")
	assert.IsType(t, AgentServer.AgentMode(""), agent.Metadata.Mode, "Metadata.Mode should be AgentMode")

	// Test that optional fields are properly handled
	assert.Nil(t, agent.QuestionGroups, "QuestionGroups should be nil for v2")
	assert.Nil(t, agent.Metadata.QuestionGroups, "Metadata.QuestionGroups should be nil for v2")
	assert.Nil(t, agent.Metadata.WorkerConfig, "Metadata.WorkerConfig should be nil for v2")

	// Test action package details
	if assert.NotEmpty(t, agent.ActionPackages, "ActionPackages should not be empty") {
		actionPackage := agent.ActionPackages[0]
		assert.IsType(t, "", actionPackage.Name, "ActionPackage.Name should be a string")
		assert.IsType(t, "", actionPackage.Version, "ActionPackage.Version should be a string")
		assert.IsType(t, "", actionPackage.Description, "ActionPackage.Description should be a string")
		assert.IsType(t, "", actionPackage.Whitelist, "ActionPackage.Whitelist should be a string")
		assert.IsType(t, "", actionPackage.Icon, "ActionPackage.Icon should be a string")
		assert.IsType(t, "", actionPackage.Path, "ActionPackage.Path should be a string")
		assert.IsType(t, []common.ActionPackageMetadataAction{}, actionPackage.Actions, "ActionPackage.Actions should be a slice")

		// Test action details
		if assert.NotEmpty(t, actionPackage.Actions, "Actions should not be empty") {
			action := actionPackage.Actions[0]
			assert.IsType(t, "", action.Name, "Action.Name should be a string")
			assert.IsType(t, "", action.Description, "Action.Description should be a string")
			assert.IsType(t, "", action.Summary, "Action.Summary should be a string")
			assert.IsType(t, "", action.OperationKind, "Action.OperationKind should be a string")
		}
	}
}

func TestGenerateAgentMetadataFromPackageV2_FieldConsistency(t *testing.T) {
	common.Verbose = true
	metadata, err := cmd.GenerateAgentMetadataFromPackage("./fixtures/agent-packages/a-1.v2.zip")
	if err != nil {
		t.Errorf("error: %+v", err)
	}

	agent := metadata[0]

	// Test that v2 specific fields are consistent
	assert.Equal(t, AgentServer.ConversationalMode, agent.Metadata.Mode, "v2 should have conversational mode")
	assert.Equal(t, AgentServer.AgentKind, agent.Architecture, "v2 should have agent architecture")
	assert.Equal(t, AgentServer.ReasoningDisabled, agent.Reasoning, "v2 should have disabled reasoning")

	// Test that v3 fields are not present in v2
	assert.Empty(t, agent.McpServers, "v2 should not have MCP servers")
	assert.Empty(t, agent.Knowledge, "v2 should not have knowledge files")
	assert.Empty(t, agent.Datasources, "v2 should not have datasources")
	assert.Empty(t, agent.ConversationStarter, "v2 should not have conversation starter")
	assert.Empty(t, agent.WelcomeMessage, "v2 should not have welcome message")
	assert.Nil(t, agent.QuestionGroups, "v2 should not have question groups")

	// Test that action packages are properly structured for v2
	assert.Len(t, agent.ActionPackages, 1, "v2 should have exactly one action package")
	assert.Equal(t, "Wind of Change", agent.ActionPackages[0].Name, "v2 action package should have correct name")
	assert.Equal(t, "0.0.1", agent.ActionPackages[0].Version, "v2 action package should have correct version")
	assert.Len(t, agent.ActionPackages[0].Actions, 5, "v2 action package should have 5 actions")
}

func TestGenerateAgentMetadataFromPackageV2_V3Comparison(t *testing.T) {
	common.Verbose = true

	// Generate metadata for both v2 and v3
	v2Metadata, err := cmd.GenerateAgentMetadataFromPackage("./fixtures/agent-packages/a-1.v2.zip")
	if err != nil {
		t.Errorf("error generating v2 metadata: %+v", err)
	}

	v3Metadata, err := cmd.GenerateAgentMetadataFromPackage("./fixtures/agent-packages/a-1.v3.zip")
	if err != nil {
		t.Errorf("error generating v3 metadata: %+v", err)
	}

	v2Agent := v2Metadata[0]
	v3Agent := v3Metadata[0]

	// Test that basic fields are the same between v2 and v3
	assert.Equal(t, v2Agent.Name, v3Agent.Name, "Name should be the same between v2 and v3")
	assert.Equal(t, v2Agent.Description, v3Agent.Description, "Description should be the same between v2 and v3")
	assert.Equal(t, v2Agent.Version, v3Agent.Version, "Version should be the same between v2 and v3")
	assert.Equal(t, v2Agent.Model.Provider, v3Agent.Model.Provider, "Model.Provider should be the same between v2 and v3")
	assert.Equal(t, v2Agent.Model.Name, v3Agent.Model.Name, "Model.Name should be the same between v2 and v3")
	assert.Equal(t, v2Agent.Architecture, v3Agent.Architecture, "Architecture should be the same between v2 and v3")
	assert.Equal(t, v2Agent.Reasoning, v3Agent.Reasoning, "Reasoning should be the same between v2 and v3")

	// Test that action packages are the same
	assert.Equal(t, len(v2Agent.ActionPackages), len(v3Agent.ActionPackages), "ActionPackages count should be the same between v2 and v3")
	if len(v2Agent.ActionPackages) > 0 && len(v3Agent.ActionPackages) > 0 {
		assert.Equal(t, v2Agent.ActionPackages[0].Name, v3Agent.ActionPackages[0].Name, "ActionPackage.Name should be the same between v2 and v3")
		assert.Equal(t, v2Agent.ActionPackages[0].Version, v3Agent.ActionPackages[0].Version, "ActionPackage.Version should be the same between v2 and v3")
		assert.Equal(t, len(v2Agent.ActionPackages[0].Actions), len(v3Agent.ActionPackages[0].Actions), "ActionPackage.Actions count should be the same between v2 and v3")
	}

	// Test that v3 has additional fields that v2 doesn't have
	assert.Empty(t, v2Agent.McpServers, "v2 should not have MCP servers")
	assert.NotEmpty(t, v3Agent.McpServers, "v3 should have MCP servers")

	// Test that optional fields are empty in both versions when not specified
	assert.Empty(t, v2Agent.ConversationStarter, "v2 should have empty ConversationStarter")
	assert.Empty(t, v3Agent.ConversationStarter, "v3 should have empty ConversationStarter when not specified")
	assert.Empty(t, v2Agent.WelcomeMessage, "v2 should have empty WelcomeMessage")
	assert.Empty(t, v3Agent.WelcomeMessage, "v3 should have empty WelcomeMessage when not specified")
	assert.Nil(t, v2Agent.QuestionGroups, "v2 should have nil QuestionGroups")
	assert.Nil(t, v3Agent.QuestionGroups, "v3 should have nil QuestionGroups when not specified")
}

func TestGenerateAgentMetadataFromPackageV2_ConversationStarterAndWelcomeMessage(t *testing.T) {
	common.Verbose = true
	metadata, err := cmd.GenerateAgentMetadataFromPackage("./fixtures/agent-packages/a-1.v2.zip")
	if err != nil {
		t.Errorf("error: %+v", err)
	}

	// Test that conversation starter and welcome message are empty for v2 package-based metadata
	assert.Equal(t, "", metadata[0].ConversationStarter, "v2 package metadata should have empty ConversationStarter")
	assert.Equal(t, "", metadata[0].WelcomeMessage, "v2 package metadata should have empty WelcomeMessage")
}

// ==== V3 TESTS ====

func assertV3Metadata(t *testing.T, metadata []*common.AgentPackageMetadata) {
	assert.Equal(t, "0.0.1", metadata[0].Version, "agent metadata should have correct Version")
	assert.Equal(t, 4, len(metadata[0].McpServers), "agent metadata should have correct McpServers")
	mcpServerNames := []string{"file-system-server", "database-server", "database-server-no-heads", "file-system-server-no-env"}
	for _, mcpServer := range metadata[0].McpServers {
		assert.Contains(t, mcpServerNames, mcpServer.Name, "agent metadata should have correct Version")

		switch mcpServer.Name {
		case "file-system-server-no-env":
			assert.Equal(t, AgentServer.MCPTransportStdio, mcpServer.Transport, "agent metadata should have correct MCPServer.Transport")
			assert.Equal(t, "docker", mcpServer.Command, "agent metadata should have correct MCPServer.Command")
			assert.Equal(t, []string([]string{}), mcpServer.Arguments, "agent metadata should have correct MCPServer.Arguments")
			assert.Equal(t, common.AgentPackageMcpServerVariables(common.AgentPackageMcpServerVariables(nil)), mcpServer.Env, "agent metadata should have correct MCPServer.Env")
			assert.Equal(t, "/Users/username/this/is/where/docker/is/", mcpServer.Cwd, "agent metadata should have correct MCPServer.CWD")
		case "database-server-no-heads":
			assert.Equal(t, AgentServer.MCPTransportSSE, mcpServer.Transport, "agent metadata should have correct MCPServer.Transport")
			assert.Equal(t, "", mcpServer.Command, "agent metadata should have correct MCPServer.Command")
			assert.Equal(t, "http://localhost:8080/sse", mcpServer.URL, "agent metadata should have correct MCPServer.URL")
			assert.Equal(t, common.AgentPackageMcpServerVariables(common.AgentPackageMcpServerVariables(nil)), mcpServer.Headers, "agent metadata should have correct MCPServer.URL")
		case "file-system-server":
			assert.Equal(t, AgentServer.MCPTransportStdio, mcpServer.Transport, "agent metadata should have correct MCPServer.Transport")
			assert.Equal(t, "uv", mcpServer.Command, "agent metadata should have correct MCPServer.Command")
			assert.Equal(t, []string([]string{
				"run",
				"python",
				"-m",
				"mcp_file_system",
			}), mcpServer.Arguments, "agent metadata should have correct MCPServer.Arguments")

			assert.Equal(t, common.AgentPackageMcpServerVariables{
				"CONTENT_TYPE": {Value: common.Ptr("application/json")},
				"FILE_SYSTEM_ROOT": {
					Type:        "string",
					Description: "Your content type for authentication",
					Provider:    "",
					Scopes:      nil,
					Value:       common.Ptr("/data"),
				},
				"MCP_API_KEY": {
					Type:        "secret",
					Description: "Your API key for authentication",
					Provider:    "",
					Scopes:      nil,
					Value:       nil,
				},
				"MY_OAUTH2_API_KEY": {
					Type:        "oauth2-secret",
					Description: "Your OAuth2 API key for authentication",
					Provider:    "Microsoft",
					Scopes: []string{
						"user.read",
						"user.write",
					},
					Value: nil,
				},
			}, mcpServer.Env, "agent metadata should have correct MCPServer.Env")
			assert.Equal(t, "./mcp-servers/file-system", mcpServer.Cwd, "agent metadata should have correct MCPServer.CWD")
		case "database-server":
			assert.Equal(t, AgentServer.MCPTransportStreamableHTTP, mcpServer.Transport, "agent metadata should have correct MCPServer.Transport")
			assert.Equal(t, "", mcpServer.Command, "agent metadata should have correct MCPServer.Command")
			assert.Equal(t, "http://localhost:8080/mcp", mcpServer.URL, "agent metadata should have correct MCPServer.URL")
			assert.Equal(t, common.AgentPackageMcpServerVariables{
				"Content-Type": {
					Value: common.Ptr("application/json"),
				},
				"Authorization": {
					Type:        "oauth2-secret",
					Description: "Your OAuth2 API key for authentication",
					Provider:    "Microsoft",
					Scopes:      nil,
					Value:       nil,
				},
				"X-API-Version": {
					Type:        "string",
					Description: "API version header",
					Provider:    "",
					Scopes:      nil,
					Value:       common.Ptr("1.0.0"),
				},
				"X-email-API-Key": {
					Type:        "secret",
					Description: "API key to access e-mails",
					Provider:    "",
					Scopes:      nil,
					Value:       nil,
				},
			}, mcpServer.Headers, "agent metadata should have correct MCPServer.Env")
		}
	}
}

func TestGenerateAgentMetadataFromPackageV3(t *testing.T) {
	common.Verbose = true
	metadata, err := cmd.GenerateAgentMetadataFromPackage("./fixtures/agent-packages/a-1.v3.zip")
	if err != nil {
		t.Errorf("error: %+v", err)
	}

	assertV3Metadata(t, metadata)
}

func TestGenerateAgentMetadataFromProjectV3QG(t *testing.T) {
	common.Verbose = true
	metadata, err := cmd.GenerateAgentMetadataFromProject("./fixtures/agent-projects/a-1.v3.qg")
	if err != nil {
		t.Errorf("error: %+v", err)
	}

	assert.Equal(t, "0.0.1", metadata[0].Version, "agent metadata should have correct Version")
	assert.Equal(t, "a1", metadata[0].Name, "agent metadata should have correct Name")
	assert.Equal(t, "a1", metadata[0].Description, "agent metadata should have correct Description")
	assert.Equal(t, AgentServer.ReasoningDisabled, metadata[0].Reasoning, "agent metadata should have correct Reasoning")
	assert.Equal(t, AgentServer.ConversationalMode, metadata[0].Metadata.Mode, "agent metadata should have correct Metadata.Mode")

	if assert.NotNil(t, metadata[0].Metadata.QuestionGroups, "QuestionGroups should not be nil") {
		assert.Equal(t, 2, len(metadata[0].Metadata.QuestionGroups), "Should have 2 question groups")
		assert.Equal(t, "Getting Started", metadata[0].Metadata.QuestionGroups[0].Title, "First group title should match")
		assert.Equal(t, []string{"What can you do?", "How do I use this agent?"}, metadata[0].Metadata.QuestionGroups[0].Questions, "First group questions should match")
		assert.Equal(t, "Advanced Usage", metadata[0].Metadata.QuestionGroups[1].Title, "Second group title should match")
		assert.Equal(t, []string{"How do I connect to a database?", "Can you automate file management?"}, metadata[0].Metadata.QuestionGroups[1].Questions, "Second group questions should match")
	}
}

func TestGenerateAgentMetadataFromProjectV3CSW(t *testing.T) {
	common.Verbose = true
	metadata, err := cmd.GenerateAgentMetadataFromProject("./fixtures/agent-projects/a-1.v3.csw")
	if err != nil {
		t.Errorf("error: %+v", err)
	}

	// Test basic metadata
	assert.Equal(t, "0.0.1", metadata[0].Version, "agent metadata should have correct Version")
	assert.Equal(t, "a1", metadata[0].Name, "agent metadata should have correct Name")
	assert.Equal(t, "a1", metadata[0].Description, "agent metadata should have correct Description")
	assert.Equal(t, AgentServer.ReasoningDisabled, metadata[0].Reasoning, "agent metadata should have correct Reasoning")
	assert.Equal(t, AgentServer.ConversationalMode, metadata[0].Metadata.Mode, "agent metadata should have correct Metadata.Mode")

	// Test conversation starter (should be empty for package-based metadata)
	assert.Equal(t, "What can you do?", metadata[0].ConversationStarter, "package metadata should have empty ConversationStarter")

	// Test welcome message
	assert.Equal(t, "Welcome! I'm here to help you with various tasks. Feel free to ask me anything!", metadata[0].WelcomeMessage, "agent metadata should have correct WelcomeMessage")

	// Test question groups
	if assert.NotNil(t, metadata[0].QuestionGroups, "QuestionGroups should not be nil") {
		assert.Equal(t, 2, len(metadata[0].QuestionGroups), "Should have 2 question groups")
		assert.Equal(t, "Getting Started", metadata[0].QuestionGroups[0].Title, "First group title should match")
		assert.Equal(t, []string{"What can you do?", "How do I use this agent?"}, metadata[0].QuestionGroups[0].Questions, "First group questions should match")
		assert.Equal(t, "Advanced Usage", metadata[0].QuestionGroups[1].Title, "Second group title should match")
		assert.Equal(t, []string{"How do I connect to a database?", "Can you automate file management?"}, metadata[0].QuestionGroups[1].Questions, "Second group questions should match")
	}

	// Test that question groups are also present in metadata
	if assert.NotNil(t, metadata[0].Metadata.QuestionGroups, "Metadata.QuestionGroups should not be nil") {
		assert.Equal(t, 2, len(metadata[0].Metadata.QuestionGroups), "Should have 2 question groups in metadata")
		assert.Equal(t, "Getting Started", metadata[0].Metadata.QuestionGroups[0].Title, "First group title should match in metadata")
		assert.Equal(t, []string{"What can you do?", "How do I use this agent?"}, metadata[0].Metadata.QuestionGroups[0].Questions, "First group questions should match in metadata")
		assert.Equal(t, "Advanced Usage", metadata[0].Metadata.QuestionGroups[1].Title, "Second group title should match in metadata")
		assert.Equal(t, []string{"How do I connect to a database?", "Can you automate file management?"}, metadata[0].Metadata.QuestionGroups[1].Questions, "Second group questions should match in metadata")
	}
}

func TestGenerateAgentMetadataFromProjectV3CSW_EmptyFields(t *testing.T) {
	common.Verbose = true
	metadata, err := cmd.GenerateAgentMetadataFromProject("./fixtures/agent-projects/a-1.v3.qg")
	if err != nil {
		t.Errorf("error: %+v", err)
	}

	// Test that conversation starter and welcome message are empty when not specified
	assert.Equal(t, "", metadata[0].ConversationStarter, "agent metadata should have empty ConversationStarter when not specified")
	assert.Equal(t, "", metadata[0].WelcomeMessage, "agent metadata should have empty WelcomeMessage when not specified")

	// Test that question groups are still present
	if assert.NotNil(t, metadata[0].QuestionGroups, "QuestionGroups should not be nil") {
		assert.Equal(t, 2, len(metadata[0].QuestionGroups), "Should have 2 question groups")
	}
}

func TestGenerateAgentMetadataFromPackageV3_ConversationStarterAndWelcomeMessage(t *testing.T) {
	common.Verbose = true
	metadata, err := cmd.GenerateAgentMetadataFromPackage("./fixtures/agent-packages/a-1.v3.zip")
	if err != nil {
		t.Errorf("error: %+v", err)
	}

	// Test that conversation starter and welcome message are empty for package-based metadata
	// (since these fields are typically only available in project-based metadata)
	assert.Equal(t, "", metadata[0].ConversationStarter, "package metadata should have empty ConversationStarter")
	assert.Equal(t, "", metadata[0].WelcomeMessage, "package metadata should have empty WelcomeMessage")
}

func TestQuestionGroupsConsistency(t *testing.T) {
	common.Verbose = true
	metadata, err := cmd.GenerateAgentMetadataFromProject("./fixtures/agent-projects/a-1.v3.csw")
	if err != nil {
		t.Errorf("error: %+v", err)
	}

	// Test that question groups are consistent between top-level and metadata fields
	assert.Equal(t, metadata[0].QuestionGroups, metadata[0].Metadata.QuestionGroups, "QuestionGroups should be consistent between top-level and metadata fields")
}

func TestConversationStarterAndWelcomeMessageTypes(t *testing.T) {
	common.Verbose = true
	metadata, err := cmd.GenerateAgentMetadataFromProject("./fixtures/agent-projects/a-1.v3.csw")
	if err != nil {
		t.Errorf("error: %+v", err)
	}

	// Test that conversation starter and welcome message are strings
	assert.IsType(t, "", metadata[0].ConversationStarter, "ConversationStarter should be a string")
	assert.IsType(t, "", metadata[0].WelcomeMessage, "WelcomeMessage should be a string")

	// Test that they are not empty when specified
	assert.NotEmpty(t, metadata[0].ConversationStarter, "ConversationStarter should not be empty when specified")
	assert.NotEmpty(t, metadata[0].WelcomeMessage, "WelcomeMessage should not be empty when specified")
}

// ==== V3 PACKAGE TESTS WITH CONVERSATION GROUPS ====

func TestGenerateAgentMetadataFromPackageV3CG(t *testing.T) {
	common.Verbose = true
	metadata, err := cmd.GenerateAgentMetadataFromPackage("./fixtures/agent-packages/a-1.v3.cg.zip")
	if err != nil {
		t.Errorf("error: %+v", err)
	}

	// Test basic metadata
	assert.Equal(t, "0.0.1", metadata[0].Version, "agent metadata should have correct Version")
	assert.Equal(t, "a1", metadata[0].Name, "agent metadata should have correct Name")
	assert.Equal(t, "a1", metadata[0].Description, "agent metadata should have correct Description")
	assert.Equal(t, AgentServer.ReasoningDisabled, metadata[0].Reasoning, "agent metadata should have correct Reasoning")
	assert.Equal(t, AgentServer.ConversationalMode, metadata[0].Metadata.Mode, "agent metadata should have correct Metadata.Mode")

	// Test that conversation starter and welcome message are empty for package-based metadata
	assert.Equal(t, "", metadata[0].ConversationStarter, "package metadata should have empty ConversationStarter")
	assert.Equal(t, "", metadata[0].WelcomeMessage, "package metadata should have empty WelcomeMessage")

	// Test question groups (conversation groups)
	if assert.NotNil(t, metadata[0].QuestionGroups, "QuestionGroups should not be nil") {
		assert.Equal(t, 2, len(metadata[0].QuestionGroups), "Should have 2 question groups")
		assert.Equal(t, "Getting Started", metadata[0].QuestionGroups[0].Title, "First group title should match")
		assert.Equal(t, []string{"What can you do?", "How do I use this agent?"}, metadata[0].QuestionGroups[0].Questions, "First group questions should match")
		assert.Equal(t, "Advanced Usage", metadata[0].QuestionGroups[1].Title, "Second group title should match")
		assert.Equal(t, []string{"How do I connect to a database?", "Can you automate file management?"}, metadata[0].QuestionGroups[1].Questions, "Second group questions should match")
	}

	// Test that question groups are also present in metadata
	if assert.NotNil(t, metadata[0].Metadata.QuestionGroups, "Metadata.QuestionGroups should not be nil") {
		assert.Equal(t, 2, len(metadata[0].Metadata.QuestionGroups), "Should have 2 question groups in metadata")
		assert.Equal(t, "Getting Started", metadata[0].Metadata.QuestionGroups[0].Title, "First group title should match in metadata")
		assert.Equal(t, []string{"What can you do?", "How do I use this agent?"}, metadata[0].Metadata.QuestionGroups[0].Questions, "First group questions should match in metadata")
		assert.Equal(t, "Advanced Usage", metadata[0].Metadata.QuestionGroups[1].Title, "Second group title should match in metadata")
		assert.Equal(t, []string{"How do I connect to a database?", "Can you automate file management?"}, metadata[0].Metadata.QuestionGroups[1].Questions, "Second group questions should match in metadata")
	}

	// Test MCP servers (should be the same as regular v3)
	assertV3Metadata(t, metadata)
}

func TestGenerateAgentMetadataFromPackageV3CGWM(t *testing.T) {
	common.Verbose = true
	metadata, err := cmd.GenerateAgentMetadataFromPackage("./fixtures/agent-packages/a-1.v3.cg.wm.zip")
	if err != nil {
		t.Errorf("error: %+v", err)
	}

	// Test basic metadata
	assert.Equal(t, "0.0.1", metadata[0].Version, "agent metadata should have correct Version")
	assert.Equal(t, "a1", metadata[0].Name, "agent metadata should have correct Name")
	assert.Equal(t, "a1", metadata[0].Description, "agent metadata should have correct Description")
	assert.Equal(t, AgentServer.ReasoningDisabled, metadata[0].Reasoning, "agent metadata should have correct Reasoning")
	assert.Equal(t, AgentServer.ConversationalMode, metadata[0].Metadata.Mode, "agent metadata should have correct Metadata.Mode")

	// Test conversation starter (should be empty for package-based metadata)
	assert.Equal(t, "", metadata[0].ConversationStarter, "package metadata should have empty ConversationStarter")

	// Test welcome message
	assert.Equal(t, "What can you do?", metadata[0].WelcomeMessage, "agent metadata should have correct WelcomeMessage")

	// Test question groups (conversation groups)
	if assert.NotNil(t, metadata[0].QuestionGroups, "QuestionGroups should not be nil") {
		assert.Equal(t, 2, len(metadata[0].QuestionGroups), "Should have 2 question groups")
		assert.Equal(t, "Getting Started", metadata[0].QuestionGroups[0].Title, "First group title should match")
		assert.Equal(t, []string{"What can you do?", "How do I use this agent?"}, metadata[0].QuestionGroups[0].Questions, "First group questions should match")
		assert.Equal(t, "Advanced Usage", metadata[0].QuestionGroups[1].Title, "Second group title should match")
		assert.Equal(t, []string{"How do I connect to a database?", "Can you automate file management?"}, metadata[0].QuestionGroups[1].Questions, "Second group questions should match")
	}

	// Test that question groups are also present in metadata
	if assert.NotNil(t, metadata[0].Metadata.QuestionGroups, "Metadata.QuestionGroups should not be nil") {
		assert.Equal(t, 2, len(metadata[0].Metadata.QuestionGroups), "Should have 2 question groups in metadata")
		assert.Equal(t, "Getting Started", metadata[0].Metadata.QuestionGroups[0].Title, "First group title should match in metadata")
		assert.Equal(t, []string{"What can you do?", "How do I use this agent?"}, metadata[0].Metadata.QuestionGroups[0].Questions, "First group questions should match in metadata")
		assert.Equal(t, "Advanced Usage", metadata[0].Metadata.QuestionGroups[1].Title, "Second group title should match in metadata")
		assert.Equal(t, []string{"How do I connect to a database?", "Can you automate file management?"}, metadata[0].Metadata.QuestionGroups[1].Questions, "Second group questions should match in metadata")
	}

	// Test MCP servers (should be the same as regular v3)
	assertV3Metadata(t, metadata)
}

// ==== V3 PACKAGE TESTS WITH DOCKER MCP GATEWAY ====

func TestGenerateAgentMetadataFromPackageV3DockerMcpGateway(t *testing.T) {
	common.Verbose = true
	metadata, err := cmd.GenerateAgentMetadataFromProject("./fixtures/agent-projects/a-1.v3.docker")
	if err != nil {
		t.Errorf("error: %+v", err)
	}
	assert.NotNil(t, metadata[0].DockerMcpGateway, "DockerMcpGateway should not be nil")
	assert.NotNil(t, metadata[0].DockerMcpGateway.Servers, "DockerMcpGateway.Servers should not be nil")

	servers := metadata[0].DockerMcpGateway.Servers
	assert.Contains(t, servers, "duckduckgo", "DockerMcpGateway.Servers should contain 'duckduckgo'")
	assert.Contains(t, servers, "notion", "DockerMcpGateway.Servers should contain 'notion'")
	assert.Contains(t, servers, "wikipedia-mcp", "DockerMcpGateway.Servers should contain 'wikipedia-mcp'")
	assert.Contains(t, servers, "kubernetes", "DockerMcpGateway.Servers should contain 'kubernetes'")

	// duckduckgo: tools should be an empty slice (whitelist of tools)
	assert.NotNil(t, servers["duckduckgo"].Tools, "duckduckgo tools should not be nil")
	assert.Equal(t, 2, len(servers["duckduckgo"].Tools), "duckduckgo tools be all tools from catalog")

	// notion: tools should be an empty slice (all tools allowed)
	assert.NotNil(t, servers["notion"].Tools, "notion tools should not be nil")
	assert.Equal(t, 19, len(servers["notion"].Tools), "notion tools should be all tools from catalog")

	// wikipedia-mcp: tools should be ["get_article"]
	assert.NotNil(t, servers["wikipedia-mcp"].Tools, "wikipedia-mcp tools should not be nil")
	assert.Equal(t, 1, len(servers["wikipedia-mcp"].Tools), "wikipedia-mcp tools should just be one")
	assert.Equal(t, "get_article", servers["wikipedia-mcp"].Tools[0].Name, "wikipedia-mcp tools should be [\"get_article\"]")

	// kubernetes: tools should be nil or empty (all tools allowed)
	// Accept both nil and empty slice as "all tools allowed"
	if tools := servers["kubernetes"].Tools; tools == nil {
		// ok, nil means all tools allowed
	} else {
		assert.Equal(t, 21, len(tools), "kubernetes tools be all tools from catalog")
	}
}
