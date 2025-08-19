package tests

import (
	"testing"

	"github.com/stretchr/testify/assert"

	AgentServer "github.com/Sema4AI/agent-platform/packages/golang-agent-cli/agent-server-client"
	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/cmd"
	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/common"
)

func TestConvertSpecAgentToAgentServer_BasicConversion(t *testing.T) {
	// Test basic conversion with all required fields
	specAgent := common.SpecAgent{
		Name:        "Test Agent",
		Description: "This is a test agent",
		Version:     "1.0.0",
		Runbook:     "# Test Runbook\nThis is a test runbook content.",
		Model: common.SpecAgentModel{
			Provider: AgentServer.OpenAI,
			Name:     "gpt-4",
		},
		Architecture: AgentServer.AgentKind,
		Reasoning:    AgentServer.ReasoningEnabled,
		Metadata: AgentServer.AgentMetadata{
			Mode: AgentServer.ConversationalMode,
		},
	}

	result := cmd.ConvertSpecAgentToAgentServer(specAgent)

	assert.NotNil(t, result)
	assert.Equal(t, "Test Agent", result.Name)
	assert.Equal(t, "This is a test agent", result.Description)
	assert.Equal(t, "1.0.0", result.Version)
	assert.Equal(t, "# Test Runbook\nThis is a test runbook content.", result.Runbook)
	assert.Equal(t, AgentServer.OpenAI, result.Model.Provider)
	assert.Equal(t, "gpt-4", result.Model.Name)
	assert.Equal(t, AgentServer.AgentKind, result.AdvancedConfig.Architecture)
	assert.Equal(t, AgentServer.ReasoningEnabled, result.AdvancedConfig.Reasoning)
	assert.Equal(t, AgentServer.ConversationalMode, result.Metadata.Mode)
	assert.True(t, result.Public)
}

func TestConvertSpecAgentToAgentServer_WithExtraFields(t *testing.T) {
	// Test conversion with extra fields like WelcomeMessage, ConversationStarter, etc.
	agentSettings := map[string]any{
		"temperature": 0.7,
		"max_tokens":  1000,
	}

	specAgent := common.SpecAgent{
		Name:                 "Enhanced Agent",
		Description:          "Agent with extra features",
		Version:              "2.0.0",
		Runbook:              "Enhanced runbook",
		WelcomeMessage:       "Welcome! I'm here to help you.",
		ConversationStarter:  "How can I assist you today?",
		DocumentIntelligence: AgentServer.DocumentIntelligenceVersionV2,
		AgentSettings:        agentSettings,
		Model: common.SpecAgentModel{
			Provider: AgentServer.Azure,
			Name:     "gpt-4-turbo",
		},
		Architecture: AgentServer.PlanExecuteKind,
		Reasoning:    AgentServer.ReasoningVerbose,
		Metadata: AgentServer.AgentMetadata{
			Mode: AgentServer.WorkerMode,
			WorkerConfig: &AgentServer.WorkerConfig{
				Type:         AgentServer.DocumentIntelligence,
				DocumentType: "invoice",
			},
		},
	}

	result := cmd.ConvertSpecAgentToAgentServer(specAgent)

	assert.NotNil(t, result)
	assert.Equal(t, "Enhanced Agent", result.Name)
	assert.Equal(t, "Welcome! I'm here to help you.", result.Extra.WelcomeMessage)
	assert.Equal(t, "How can I assist you today?", result.Extra.ConversationStarter)
	assert.Equal(t, AgentServer.DocumentIntelligenceVersionV2, result.Extra.DocumentIntelligence)
	assert.Equal(t, agentSettings, result.Extra.AgentSettings)
	assert.Equal(t, AgentServer.Azure, result.Model.Provider)
	assert.Equal(t, "gpt-4-turbo", result.Model.Name)
	assert.Equal(t, AgentServer.PlanExecuteKind, result.AdvancedConfig.Architecture)
	assert.Equal(t, AgentServer.ReasoningVerbose, result.AdvancedConfig.Reasoning)
	assert.Equal(t, AgentServer.WorkerMode, result.Metadata.Mode)
	assert.NotNil(t, result.Metadata.WorkerConfig)
	assert.Equal(t, AgentServer.DocumentIntelligence, result.Metadata.WorkerConfig.Type)
	assert.Equal(t, "invoice", result.Metadata.WorkerConfig.DocumentType)
}

func TestConvertSpecAgentToAgentServer_WithActionPackages(t *testing.T) {
	// Test conversion with action packages
	specAgent := common.SpecAgent{
		Name:        "Agent with Actions",
		Description: "Agent that has action packages",
		Version:     "1.5.0",
		Runbook:     "Runbook with actions",
		Model: common.SpecAgentModel{
			Provider: AgentServer.Google,
			Name:     "gemini-pro",
		},
		Architecture: AgentServer.AgentKind,
		Reasoning:    AgentServer.ReasoningDisabled,
		ActionPackages: []common.SpecAgentActionPackage{
			{
				Name:         "file-operations",
				Organization: "sema4ai",
				Type:         "folder",
				Version:      "1.0.0",
				Whitelist:    "read_file,write_file",
				Path:         "./actions/file-ops",
			},
			{
				Name:         "web-scraping",
				Organization: "community",
				Type:         "zip",
				Version:      "2.1.0",
				Whitelist:    "*",
				Path:         "./actions/web-scraper.zip",
			},
		},
		Metadata: AgentServer.AgentMetadata{
			Mode: AgentServer.ConversationalMode,
		},
	}

	result := cmd.ConvertSpecAgentToAgentServer(specAgent)

	assert.NotNil(t, result)
	assert.Len(t, result.ActionPackages, 2)

	// Check first action package
	ap1 := result.ActionPackages[0]
	assert.Equal(t, "file-operations", ap1.Name)
	assert.Equal(t, "sema4ai", ap1.Organization)
	assert.Equal(t, "1.0.0", ap1.Version)
	assert.Equal(t, "read_file,write_file", ap1.Whitelist)

	// Check second action package
	ap2 := result.ActionPackages[1]
	assert.Equal(t, "web-scraping", ap2.Name)
	assert.Equal(t, "community", ap2.Organization)
	assert.Equal(t, "2.1.0", ap2.Version)
	assert.Equal(t, "*", ap2.Whitelist)
}

func TestConvertSpecAgentToAgentServer_WithMcpServers(t *testing.T) {
	// Test conversion with MCP servers
	specAgent := common.SpecAgent{
		Name:        "Agent with MCP",
		Description: "Agent with MCP servers",
		Version:     "1.0.0",
		Runbook:     "MCP runbook",
		Model: common.SpecAgentModel{
			Provider: AgentServer.Anthropic,
			Name:     "claude-3-sonnet",
		},
		Architecture: AgentServer.AgentKind,
		Reasoning:    AgentServer.ReasoningEnabled,
		McpServers: []common.SpecMcpServer{
			{
				Name:        "file-server",
				Description: "File system MCP server",
				Transport:   AgentServer.MCPTransportStdio,
				CommandLine: []string{"uvx", "mcp-server-file"},
				Env: map[string]common.SpecMcpServerVariable{
					"ROOT_PATH": {
						Type:        common.SpecMcpTypeString,
						Description: "Root directory for file operations",
						Value:       common.Ptr("/workspace"),
					},
					"API_KEY": {
						Type:        common.SpecMcpTypeSecret,
						Description: "API key for authentication",
					},
				},
				Cwd:                  "./mcp-servers",
				ForceSerialToolCalls: false,
			},
			{
				Name:        "web-server",
				Description: "Web MCP server",
				Transport:   AgentServer.MCPTransportStreamableHTTP,
				URL:         "http://localhost:8080/mcp",
				Headers: map[string]common.SpecMcpServerVariable{
					"Authorization": {
						Type:        common.SpecMcpTypeOAuth2Secret,
						Description: "OAuth2 token",
						Provider:    "Google",
						Scopes:      []string{"read", "write"},
					},
					"Content-Type": {
						Value: common.Ptr("application/json"),
					},
				},
				ForceSerialToolCalls: true,
			},
		},
		Metadata: AgentServer.AgentMetadata{
			Mode: AgentServer.ConversationalMode,
		},
	}

	result := cmd.ConvertSpecAgentToAgentServer(specAgent)

	assert.NotNil(t, result)
	assert.Len(t, result.McpServers, 2)

	// Check STDIO MCP server
	stdioServer := result.McpServers[0]
	assert.Equal(t, "file-server", stdioServer.Name)
	assert.Equal(t, "File system MCP server", stdioServer.Description)
	assert.Equal(t, AgentServer.MCPTransportStdio, stdioServer.Transport)
	assert.NotNil(t, stdioServer.Command)
	assert.Equal(t, "uvx", *stdioServer.Command)
	assert.Equal(t, []string{"mcp-server-file"}, stdioServer.Args)
	assert.NotNil(t, stdioServer.Cwd)
	assert.Equal(t, "./mcp-servers", *stdioServer.Cwd)
	assert.False(t, stdioServer.ForceSerialToolCalls)

	// Check environment variables
	assert.Len(t, stdioServer.Env, 2)
	rootPath := stdioServer.Env["ROOT_PATH"]
	assert.Equal(t, "string", rootPath.Type)
	assert.Equal(t, "Root directory for file operations", rootPath.Description)
	assert.NotNil(t, rootPath.Value)
	assert.Equal(t, "/workspace", *rootPath.Value)

	apiKey := stdioServer.Env["API_KEY"]
	assert.Equal(t, "secret", apiKey.Type)
	assert.Equal(t, "API key for authentication", apiKey.Description)

	// Check HTTP MCP server
	httpServer := result.McpServers[1]
	assert.Equal(t, "web-server", httpServer.Name)
	assert.Equal(t, "Web MCP server", httpServer.Description)
	assert.Equal(t, AgentServer.MCPTransportStreamableHTTP, httpServer.Transport)
	assert.NotNil(t, httpServer.URL)
	assert.Equal(t, "http://localhost:8080/mcp", *httpServer.URL)
	assert.True(t, httpServer.ForceSerialToolCalls)

	// Check headers
	assert.Len(t, httpServer.Headers, 2)
	auth := httpServer.Headers["Authorization"]
	assert.Equal(t, "oauth2-secret", auth.Type)
	assert.Equal(t, "OAuth2 token", auth.Description)
	assert.Equal(t, "Google", auth.Provider)
	assert.Equal(t, []string{"read", "write"}, auth.Scopes)

	contentType := httpServer.Headers["Content-Type"]
	assert.NotNil(t, contentType.Value)
	assert.Equal(t, "application/json", *contentType.Value)
}

func TestConvertSpecAgentToAgentServer_WithDockerMcpGateway(t *testing.T) {
	// Test conversion with Docker MCP Gateway
	specAgent := common.SpecAgent{
		Name:        "Agent with Docker MCP",
		Description: "Agent with Docker MCP Gateway",
		Version:     "1.0.0",
		Runbook:     "Docker MCP runbook",
		Model: common.SpecAgentModel{
			Provider: AgentServer.OpenAI,
			Name:     "gpt-4",
		},
		Architecture: AgentServer.AgentKind,
		Reasoning:    AgentServer.ReasoningEnabled,
		DockerMcpGateway: &common.SpecDockerMcpGateway{
			Catalog: common.Ptr("https://registry.docker.com/catalog"),
			Servers: map[string]common.SpecDockerMcpServer{
				"database": {
					Tools: []string{"query", "insert", "update"},
				},
			},
		},
		Metadata: AgentServer.AgentMetadata{
			Mode: AgentServer.ConversationalMode,
		},
	}

	result := cmd.ConvertSpecAgentToAgentServer(specAgent)

	assert.NotNil(t, result)
	assert.Len(t, result.McpServers, 1)

	// Check Docker MCP Gateway server
	dockerServer := result.McpServers[0]
	assert.Equal(t, "MCP_DOCKER", dockerServer.Name)
	assert.Equal(t, "Docker MCP Gateway", dockerServer.Description)
	assert.Equal(t, AgentServer.MCPTransportStdio, dockerServer.Transport)
	assert.NotNil(t, dockerServer.Command)
	assert.Equal(t, "docker", *dockerServer.Command)
	assert.Equal(t, []string{"mcp", "gateway", "run"}, dockerServer.Args)
	assert.False(t, dockerServer.ForceSerialToolCalls)
}

func TestConvertSpecAgentToAgentServer_WithQuestionGroups(t *testing.T) {
	// Test conversion with question groups
	questionGroups := AgentServer.QuestionGroups{
		{
			Title:     "Getting Started",
			Questions: []string{"How do I begin?", "What can you do?"},
		},
		{
			Title:     "Advanced Features",
			Questions: []string{"How do I configure X?", "What are the limitations?"},
		},
	}

	specAgent := common.SpecAgent{
		Name:        "Agent with Questions",
		Description: "Agent with predefined questions",
		Version:     "1.0.0",
		Runbook:     "Question runbook",
		Model: common.SpecAgentModel{
			Provider: AgentServer.OpenAI,
			Name:     "gpt-4",
		},
		Architecture: AgentServer.AgentKind,
		Reasoning:    AgentServer.ReasoningEnabled,
		Metadata: AgentServer.AgentMetadata{
			Mode:           AgentServer.ConversationalMode,
			QuestionGroups: questionGroups,
		},
	}

	result := cmd.ConvertSpecAgentToAgentServer(specAgent)

	assert.NotNil(t, result)
	assert.Len(t, result.QuestionGroups, 2)
	assert.Equal(t, "Getting Started", result.QuestionGroups[0].Title)
	assert.Equal(t, []string{"How do I begin?", "What can you do?"}, result.QuestionGroups[0].Questions)
	assert.Equal(t, "Advanced Features", result.QuestionGroups[1].Title)
	assert.Equal(t, []string{"How do I configure X?", "What are the limitations?"}, result.QuestionGroups[1].Questions)

	// Also check that metadata is properly copied
	assert.Equal(t, questionGroups, result.Metadata.QuestionGroups)
}

func TestConvertSpecAgentToAgentServer_EmptyFields(t *testing.T) {
	// Test conversion with minimal required fields and empty optional fields
	specAgent := common.SpecAgent{
		Name:        "Minimal Agent",
		Description: "",
		Version:     "0.0.1",
		Runbook:     "",
		Model: common.SpecAgentModel{
			Provider: AgentServer.OpenAI,
			Name:     "gpt-3.5-turbo",
		},
		Architecture:         AgentServer.AgentKind,
		Reasoning:            AgentServer.ReasoningDisabled,
		WelcomeMessage:       "",
		ConversationStarter:  "",
		DocumentIntelligence: "",
		AgentSettings:        nil,
		ActionPackages:       []common.SpecAgentActionPackage{},
		McpServers:           []common.SpecMcpServer{},
		DockerMcpGateway:     nil,
		Knowledge:            []common.SpecAgentKnowledge{},
		Metadata: AgentServer.AgentMetadata{
			Mode: AgentServer.ConversationalMode,
		},
	}

	result := cmd.ConvertSpecAgentToAgentServer(specAgent)

	assert.NotNil(t, result)
	assert.Equal(t, "Minimal Agent", result.Name)
	assert.Equal(t, "", result.Description)
	assert.Equal(t, "0.0.1", result.Version)
	assert.Equal(t, "", result.Runbook)
	assert.Equal(t, "", result.Extra.WelcomeMessage)
	assert.Equal(t, "", result.Extra.ConversationStarter)
	assert.Equal(t, AgentServer.DocumentIntelligenceVersion(""), result.Extra.DocumentIntelligence)
	assert.Nil(t, result.Extra.AgentSettings)
	assert.Empty(t, result.ActionPackages)
	assert.Empty(t, result.McpServers)
	assert.True(t, result.Public)
}

func TestConvertSpecAgentToAgentServer_DifferentModelProviders(t *testing.T) {
	// Test conversion with different model providers
	testCases := []struct {
		provider AgentServer.AgentModelProvider
		name     string
	}{
		{AgentServer.OpenAI, "gpt-4"},
		{AgentServer.Azure, "gpt-4-azure"},
		{AgentServer.Anthropic, "claude-3-sonnet"},
		{AgentServer.Google, "gemini-pro"},
		{AgentServer.Amazon, "titan-text"},
		{AgentServer.Ollama, "llama2"},
	}

	for _, tc := range testCases {
		t.Run(string(tc.provider), func(t *testing.T) {
			specAgent := common.SpecAgent{
				Name:        "Test Agent",
				Description: "Test with " + string(tc.provider),
				Version:     "1.0.0",
				Runbook:     "Test runbook",
				Model: common.SpecAgentModel{
					Provider: tc.provider,
					Name:     tc.name,
				},
				Architecture: AgentServer.AgentKind,
				Reasoning:    AgentServer.ReasoningEnabled,
				Metadata: AgentServer.AgentMetadata{
					Mode: AgentServer.ConversationalMode,
				},
			}

			result := cmd.ConvertSpecAgentToAgentServer(specAgent)

			assert.NotNil(t, result)
			assert.Equal(t, tc.provider, result.Model.Provider)
			assert.Equal(t, tc.name, result.Model.Name)
		})
	}
}

func TestConvertSpecAgentToAgentServer_DifferentArchitectures(t *testing.T) {
	// Test conversion with different architectures
	testCases := []struct {
		architecture AgentServer.AgentArchitecture
		reasoning    AgentServer.AgentReasoning
	}{
		{AgentServer.AgentKind, AgentServer.ReasoningDisabled},
		{AgentServer.AgentKind, AgentServer.ReasoningEnabled},
		{AgentServer.AgentKind, AgentServer.ReasoningVerbose},
		{AgentServer.PlanExecuteKind, AgentServer.ReasoningEnabled},
	}

	for _, tc := range testCases {
		t.Run(string(tc.architecture)+"_"+string(tc.reasoning), func(t *testing.T) {
			specAgent := common.SpecAgent{
				Name:         "Test Agent",
				Description:  "Test architecture",
				Version:      "1.0.0",
				Runbook:      "Test runbook",
				Architecture: tc.architecture,
				Reasoning:    tc.reasoning,
				Model: common.SpecAgentModel{
					Provider: AgentServer.OpenAI,
					Name:     "gpt-4",
				},
				Metadata: AgentServer.AgentMetadata{
					Mode: AgentServer.ConversationalMode,
				},
			}

			result := cmd.ConvertSpecAgentToAgentServer(specAgent)

			assert.NotNil(t, result)
			assert.Equal(t, tc.architecture, result.AdvancedConfig.Architecture)
			assert.Equal(t, tc.reasoning, result.AdvancedConfig.Reasoning)
		})
	}
}

func TestConvertSpecAgentToAgentServer_ComplexMcpServerVariables(t *testing.T) {
	// Test conversion with complex MCP server variable configurations
	specAgent := common.SpecAgent{
		Name:        "Complex MCP Agent",
		Description: "Agent with complex MCP configurations",
		Version:     "1.0.0",
		Runbook:     "Complex MCP runbook",
		Model: common.SpecAgentModel{
			Provider: AgentServer.OpenAI,
			Name:     "gpt-4",
		},
		Architecture: AgentServer.AgentKind,
		Reasoning:    AgentServer.ReasoningEnabled,
		McpServers: []common.SpecMcpServer{
			{
				Name:        "complex-server",
				Description: "Complex MCP server with various variable types",
				Transport:   AgentServer.MCPTransportStreamableHTTP,
				URL:         "https://api.example.com/mcp",
				Headers: map[string]common.SpecMcpServerVariable{
					"Authorization": {
						Type:        common.SpecMcpTypeOAuth2Secret,
						Description: "OAuth2 authorization header",
						Provider:    "Microsoft",
						Scopes:      []string{"https://graph.microsoft.com/.default"},
					},
					"X-API-Version": {
						Value: common.Ptr("v1.0"),
					},
					"User-Agent": {
						Type:        common.SpecMcpTypeString,
						Description: "User agent string",
						Value:       common.Ptr("MyApp/1.0"),
					},
				},
				Env: map[string]common.SpecMcpServerVariable{
					"DATABASE_URL": {
						Type:        common.SpecMcpTypeDataServerInfo,
						Description: "Database connection info",
					},
					"LOG_LEVEL": {
						Value: common.Ptr("INFO"),
					},
				},
				ForceSerialToolCalls: true,
			},
		},
		Metadata: AgentServer.AgentMetadata{
			Mode: AgentServer.ConversationalMode,
		},
	}

	result := cmd.ConvertSpecAgentToAgentServer(specAgent)

	assert.NotNil(t, result)
	assert.Len(t, result.McpServers, 1)

	server := result.McpServers[0]
	assert.Equal(t, "complex-server", server.Name)

	// Check headers conversion
	assert.Len(t, server.Headers, 3)

	authHeader := server.Headers["Authorization"]
	assert.Equal(t, "oauth2-secret", authHeader.Type)
	assert.Equal(t, "OAuth2 authorization header", authHeader.Description)
	assert.Equal(t, "Microsoft", authHeader.Provider)
	assert.Equal(t, []string{"https://graph.microsoft.com/.default"}, authHeader.Scopes)

	versionHeader := server.Headers["X-API-Version"]
	assert.NotNil(t, versionHeader.Value)
	assert.Equal(t, "v1.0", *versionHeader.Value)

	userAgentHeader := server.Headers["User-Agent"]
	assert.Equal(t, "string", userAgentHeader.Type)
	assert.Equal(t, "User agent string", userAgentHeader.Description)
	assert.NotNil(t, userAgentHeader.Value)
	assert.Equal(t, "MyApp/1.0", *userAgentHeader.Value)

	// Check environment variables conversion
	assert.Len(t, server.Env, 2)

	dbUrlEnv := server.Env["DATABASE_URL"]
	assert.Equal(t, "data-server-info", dbUrlEnv.Type)
	assert.Equal(t, "Database connection info", dbUrlEnv.Description)

	logLevelEnv := server.Env["LOG_LEVEL"]
	assert.NotNil(t, logLevelEnv.Value)
	assert.Equal(t, "INFO", *logLevelEnv.Value)
}

func TestConvertSpecAgentToAgentServer_EdgeCases(t *testing.T) {
	t.Run("NilAgentSettings", func(t *testing.T) {
		specAgent := common.SpecAgent{
			Name:        "Agent with nil settings",
			Description: "Testing nil agent settings",
			Version:     "1.0.0",
			Runbook:     "Test runbook",
			Model: common.SpecAgentModel{
				Provider: AgentServer.OpenAI,
				Name:     "gpt-4",
			},
			Architecture:  AgentServer.AgentKind,
			Reasoning:     AgentServer.ReasoningEnabled,
			AgentSettings: nil,
			Metadata: AgentServer.AgentMetadata{
				Mode: AgentServer.ConversationalMode,
			},
		}

		result := cmd.ConvertSpecAgentToAgentServer(specAgent)
		assert.NotNil(t, result)
		assert.Nil(t, result.Extra.AgentSettings)
	})

	t.Run("EmptyMcpServerSlice", func(t *testing.T) {
		specAgent := common.SpecAgent{
			Name:        "Agent with empty MCP",
			Description: "Testing empty MCP servers",
			Version:     "1.0.0",
			Runbook:     "Test runbook",
			Model: common.SpecAgentModel{
				Provider: AgentServer.OpenAI,
				Name:     "gpt-4",
			},
			Architecture: AgentServer.AgentKind,
			Reasoning:    AgentServer.ReasoningEnabled,
			McpServers:   []common.SpecMcpServer{},
			Metadata: AgentServer.AgentMetadata{
				Mode: AgentServer.ConversationalMode,
			},
		}

		result := cmd.ConvertSpecAgentToAgentServer(specAgent)
		assert.NotNil(t, result)
		assert.Empty(t, result.McpServers)
	})

	t.Run("McpServerWithEmptyCommandLine", func(t *testing.T) {
		specAgent := common.SpecAgent{
			Name:        "Agent with empty command MCP",
			Description: "Testing MCP server with empty command line",
			Version:     "1.0.0",
			Runbook:     "Test runbook",
			Model: common.SpecAgentModel{
				Provider: AgentServer.OpenAI,
				Name:     "gpt-4",
			},
			Architecture: AgentServer.AgentKind,
			Reasoning:    AgentServer.ReasoningEnabled,
			McpServers: []common.SpecMcpServer{
				{
					Name:        "empty-command-server",
					Description: "MCP server with empty command",
					Transport:   AgentServer.MCPTransportStdio,
					CommandLine: []string{},
					Env:         map[string]common.SpecMcpServerVariable{},
				},
			},
			Metadata: AgentServer.AgentMetadata{
				Mode: AgentServer.ConversationalMode,
			},
		}

		result := cmd.ConvertSpecAgentToAgentServer(specAgent)
		assert.NotNil(t, result)
		assert.Len(t, result.McpServers, 1)

		server := result.McpServers[0]
		assert.Nil(t, server.Command)
		assert.Nil(t, server.Args)
		assert.Empty(t, server.Env)
	})

	t.Run("McpServerWithSingleCommandArgument", func(t *testing.T) {
		specAgent := common.SpecAgent{
			Name:        "Agent with single command MCP",
			Description: "Testing MCP server with single command",
			Version:     "1.0.0",
			Runbook:     "Test runbook",
			Model: common.SpecAgentModel{
				Provider: AgentServer.OpenAI,
				Name:     "gpt-4",
			},
			Architecture: AgentServer.AgentKind,
			Reasoning:    AgentServer.ReasoningEnabled,
			McpServers: []common.SpecMcpServer{
				{
					Name:        "single-command-server",
					Description: "MCP server with single command",
					Transport:   AgentServer.MCPTransportStdio,
					CommandLine: []string{"python"},
				},
			},
			Metadata: AgentServer.AgentMetadata{
				Mode: AgentServer.ConversationalMode,
			},
		}

		result := cmd.ConvertSpecAgentToAgentServer(specAgent)
		assert.NotNil(t, result)
		assert.Len(t, result.McpServers, 1)

		server := result.McpServers[0]
		assert.NotNil(t, server.Command)
		assert.Equal(t, "python", *server.Command)
		assert.Nil(t, server.Args)
	})

	t.Run("ComplexNestedMcpServerVariables", func(t *testing.T) {
		specAgent := common.SpecAgent{
			Name:        "Agent with complex MCP variables",
			Description: "Testing complex nested MCP server variables",
			Version:     "1.0.0",
			Runbook:     "Test runbook",
			Model: common.SpecAgentModel{
				Provider: AgentServer.OpenAI,
				Name:     "gpt-4",
			},
			Architecture: AgentServer.AgentKind,
			Reasoning:    AgentServer.ReasoningEnabled,
			McpServers: []common.SpecMcpServer{
				{
					Name:        "complex-vars-server",
					Description: "MCP server with complex variables",
					Transport:   AgentServer.MCPTransportStreamableHTTP,
					URL:         "https://api.example.com",
					Headers: map[string]common.SpecMcpServerVariable{
						"X-Custom-Header": {
							Type:        common.SpecMcpTypeString,
							Description: "Custom header with multiple scopes",
							Provider:    "CustomProvider",
							Scopes:      []string{"scope1", "scope2", "scope3"},
							Value:       common.Ptr("custom-value"),
						},
					},
					Env: map[string]common.SpecMcpServerVariable{
						"COMPLEX_ENV": {
							Type:        common.SpecMcpTypeOAuth2Secret,
							Description: "Complex environment variable",
							Provider:    "OAuth2Provider",
							Scopes:      []string{},
						},
					},
				},
			},
			Metadata: AgentServer.AgentMetadata{
				Mode: AgentServer.ConversationalMode,
			},
		}

		result := cmd.ConvertSpecAgentToAgentServer(specAgent)
		assert.NotNil(t, result)
		assert.Len(t, result.McpServers, 1)

		server := result.McpServers[0]

		// Check complex header
		customHeader := server.Headers["X-Custom-Header"]
		assert.Equal(t, "string", customHeader.Type)
		assert.Equal(t, "Custom header with multiple scopes", customHeader.Description)
		assert.Equal(t, "CustomProvider", customHeader.Provider)
		assert.Equal(t, []string{"scope1", "scope2", "scope3"}, customHeader.Scopes)
		assert.NotNil(t, customHeader.Value)
		assert.Equal(t, "custom-value", *customHeader.Value)

		// Check complex environment variable
		complexEnv := server.Env["COMPLEX_ENV"]
		assert.Equal(t, "oauth2-secret", complexEnv.Type)
		assert.Equal(t, "Complex environment variable", complexEnv.Description)
		assert.Equal(t, "OAuth2Provider", complexEnv.Provider)
		assert.Empty(t, complexEnv.Scopes)
	})
}

func TestConvertSpecAgentToAgentServer_DockerMcpGatewayEdgeCases(t *testing.T) {
	t.Run("DockerMcpGatewayWithNilCatalog", func(t *testing.T) {
		specAgent := common.SpecAgent{
			Name:        "Agent with Docker MCP - nil catalog",
			Description: "Testing Docker MCP Gateway with nil catalog",
			Version:     "1.0.0",
			Runbook:     "Test runbook",
			Model: common.SpecAgentModel{
				Provider: AgentServer.OpenAI,
				Name:     "gpt-4",
			},
			Architecture: AgentServer.AgentKind,
			Reasoning:    AgentServer.ReasoningEnabled,
			DockerMcpGateway: &common.SpecDockerMcpGateway{
				Catalog: nil,
				Servers: map[string]common.SpecDockerMcpServer{},
			},
			Metadata: AgentServer.AgentMetadata{
				Mode: AgentServer.ConversationalMode,
			},
		}

		result := cmd.ConvertSpecAgentToAgentServer(specAgent)
		assert.NotNil(t, result)
		assert.Len(t, result.McpServers, 1)

		dockerServer := result.McpServers[0]
		assert.Equal(t, "MCP_DOCKER", dockerServer.Name)
	})

	t.Run("DockerMcpGatewayWithEmptyServers", func(t *testing.T) {
		specAgent := common.SpecAgent{
			Name:        "Agent with Docker MCP - empty servers",
			Description: "Testing Docker MCP Gateway with empty servers",
			Version:     "1.0.0",
			Runbook:     "Test runbook",
			Model: common.SpecAgentModel{
				Provider: AgentServer.OpenAI,
				Name:     "gpt-4",
			},
			Architecture: AgentServer.AgentKind,
			Reasoning:    AgentServer.ReasoningEnabled,
			DockerMcpGateway: &common.SpecDockerMcpGateway{
				Catalog: common.Ptr("https://catalog.example.com"),
				Servers: map[string]common.SpecDockerMcpServer{},
			},
			Metadata: AgentServer.AgentMetadata{
				Mode: AgentServer.ConversationalMode,
			},
		}

		result := cmd.ConvertSpecAgentToAgentServer(specAgent)
		assert.NotNil(t, result)
		assert.Len(t, result.McpServers, 1)

		dockerServer := result.McpServers[0]
		assert.Equal(t, "MCP_DOCKER", dockerServer.Name)
		assert.Equal(t, "Docker MCP Gateway", dockerServer.Description)
	})
}

func TestConvertSpecAgentToAgentServer_MetadataEdgeCases(t *testing.T) {
	t.Run("EmptyQuestionGroups", func(t *testing.T) {
		specAgent := common.SpecAgent{
			Name:        "Agent with empty question groups",
			Description: "Testing empty question groups",
			Version:     "1.0.0",
			Runbook:     "Test runbook",
			Model: common.SpecAgentModel{
				Provider: AgentServer.OpenAI,
				Name:     "gpt-4",
			},
			Architecture: AgentServer.AgentKind,
			Reasoning:    AgentServer.ReasoningEnabled,
			Metadata: AgentServer.AgentMetadata{
				Mode:           AgentServer.ConversationalMode,
				QuestionGroups: AgentServer.QuestionGroups{},
			},
		}

		result := cmd.ConvertSpecAgentToAgentServer(specAgent)
		assert.NotNil(t, result)
		assert.Empty(t, result.QuestionGroups)
		assert.Empty(t, result.Metadata.QuestionGroups)
	})

	t.Run("WorkerModeWithoutWorkerConfig", func(t *testing.T) {
		specAgent := common.SpecAgent{
			Name:        "Worker Agent without config",
			Description: "Testing worker mode without worker config",
			Version:     "1.0.0",
			Runbook:     "Test runbook",
			Model: common.SpecAgentModel{
				Provider: AgentServer.OpenAI,
				Name:     "gpt-4",
			},
			Architecture: AgentServer.AgentKind,
			Reasoning:    AgentServer.ReasoningEnabled,
			Metadata: AgentServer.AgentMetadata{
				Mode:         AgentServer.WorkerMode,
				WorkerConfig: nil,
			},
		}

		result := cmd.ConvertSpecAgentToAgentServer(specAgent)
		assert.NotNil(t, result)
		assert.Equal(t, AgentServer.WorkerMode, result.Metadata.Mode)
		assert.Nil(t, result.Metadata.WorkerConfig)
	})
}
