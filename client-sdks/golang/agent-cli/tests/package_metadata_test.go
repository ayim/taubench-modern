package tests

import (
	"testing"

	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/cmd"
	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/common"
	"github.com/stretchr/testify/assert"

	AgentServer "github.com/Sema4AI/agent-platform/client-sdks/golang/agent-client-go/pkg/client"
)

func assertV2Metadata(t *testing.T, metadata []*common.AgentPackageMetadata) {
	assert.Equal(t, "0.0.1", metadata[0].Version, "agent metadata should have correct Version")
	assert.Equal(t, "a1", metadata[0].Name, "agent metadata should have correct Name")
	assert.Equal(t, "a1", metadata[0].Description, "agent metadata should have correct Description")
	assert.Equal(t, AgentServer.ReasoningDisabled, metadata[0].Reasoning, "agent metadata should have correct Reasoning")
	assert.Equal(t, AgentServer.ConversationalMode, metadata[0].Metadata.Mode, "agent metadata should have correct Metadata.Mode")
	assert.Equal(t, "Wind of Change", metadata[0].ActionPackages[0].Name, "agent metadata should have correct ActionPackages[0].Name")
	assert.Equal(t, "0.0.1", metadata[0].ActionPackages[0].Version, "agent metadata should have correct ActionPackages[0].Version")
	assert.Equal(t, 5, len(metadata[0].ActionPackages[0].Actions), "agent metadata should have correct ActionPackages[0].Actions")
}

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
					Default:     "/data",
				},
				"MCP_API_KEY": {
					Type:        "secret",
					Description: "Your API key for authentication",
					Provider:    "",
					Scopes:      nil,
					Default:     "",
				},
				"MY_OAUTH2_API_KEY": {
					Type:        "oauth2-secret",
					Description: "Your OAuth2 API key for authentication",
					Provider:    "Microsoft",
					Scopes: []string{
						"user.read",
						"user.write",
					},
					Default: "",
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
					Default:     "",
				},
				"X-API-Version": {
					Type:        "string",
					Description: "API version header",
					Provider:    "",
					Scopes:      nil,
					Default:     "1.0.0",
				},
				"X-email-API-Key": {
					Type:        "secret",
					Description: "API key to access e-mails",
					Provider:    "",
					Scopes:      nil,
					Default:     "",
				},
			}, mcpServer.Headers, "agent metadata should have correct MCPServer.Env")
		}
	}
}

func TestGenerateAgentMetadataFromPackageV2(t *testing.T) {
	common.Verbose = true
	metadata, err := cmd.GenerateAgentMetadataFromPackage("./fixtures/agent-packages/a-1.v2.zip")
	if err != nil {
		t.Errorf("error: %+v", err)
	}

	assertV2Metadata(t, metadata)
}

func TestGenerateAgentMetadataFromPackageV3(t *testing.T) {
	common.Verbose = true
	metadata, err := cmd.GenerateAgentMetadataFromPackage("./fixtures/agent-packages/a-1.v3.zip")
	if err != nil {
		t.Errorf("error: %+v", err)
	}

	assertV2Metadata(t, metadata)
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
