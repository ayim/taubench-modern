package client

import "time"

type AgentReasoning string
type AgentModelProvider string
type AgentArchitecture string
type AgentMode string
type WorkerType string

const FIELD_NOT_CONFIGURED = "SEMA4AI_FIELD_NOT_CONFIGURED"

const (
	ReasoningDisabled AgentReasoning = "disabled"
	ReasoningEnabled  AgentReasoning = "enabled"
	ReasoningVerbose  AgentReasoning = "verbose"
)
const (
	OpenAI    AgentModelProvider = "OpenAI"
	Azure     AgentModelProvider = "Azure"
	Anthropic AgentModelProvider = "Anthropic"
	Google    AgentModelProvider = "Google"
	Amazon    AgentModelProvider = "Amazon"
	Ollama    AgentModelProvider = "Ollama"
)
const (
	AgentKind       AgentArchitecture = "agent"
	PlanExecuteKind AgentArchitecture = "plan_execute"
)

type AgentModel struct {
	Provider AgentModelProvider     `json:"provider"`
	Name     string                 `json:"name"`
	Config   map[string]interface{} `json:"config"`
}

type AgentActionPackage struct {
	Name              string            `json:"name"`
	Organization      string            `json:"organization"`
	Version           string            `json:"version"`
	URL               string            `json:"url"`
	APIKey            string            `json:"api_key"`
	Whitelist         string            `json:"whitelist"`
	AdditionalHeaders map[string]string `json:"additional_headers"`
}

// MCPTransport is the set of allowed transport modes.
// Auto defaults to streamable-http unless “sse” is in the URL;
// if there is no URL, it defaults to stdio.
type MCPTransport string

const (
	MCPTransportAuto           MCPTransport = "auto"
	MCPTransportStreamableHTTP MCPTransport = "streamable-http"
	MCPTransportSSE            MCPTransport = "sse"
	MCPTransportStdio          MCPTransport = "stdio"
)

type McpServer struct {
	// Name of the MCP server.
	Name string `json:"name"`

	// Transport protocol to use when connecting to the MCP server.
	// Auto defaults to streamable-http unless “sse” is in the URL;
	// if there is no URL, defaults to stdio.
	Transport MCPTransport `json:"transport"`

	// URL of the MCP server. This should point directly
	// to the transport endpoint to use.
	URL *string `json:"url,omitempty"`

	// Command to run the MCP server. If not provided,
	// the MCP server will be assumed to be running locally.
	Command *string `json:"command,omitempty"`

	// Arguments to pass to the MCP server command.
	Args []string `json:"args,omitempty"`

	// Environment variables to set for the MCP server command.
	Env map[string]string `json:"env,omitempty"`

	// Working directory to run the MCP server command in.
	Cwd *string `json:"cwd,omitempty"`

	// If true, all tool calls are executed under a lock
	// to support servers that cannot interleave multiple requests.
	ForceSerialToolCalls bool `json:"force_serial_tool_calls"`
}

const (
	ConversationalMode AgentMode = "conversational"
	WorkerMode         AgentMode = "worker"
)

const (
	DocumentIntelligence WorkerType = "Document Intelligence"
)

type WorkerConfig struct {
	Type         WorkerType `json:"type"`
	DocumentType string     `json:"document_type" yaml:"document-type"`
}

type AgentMetadata struct {
	Mode         AgentMode     `json:"mode"`
	WorkerConfig *WorkerConfig `json:"worker_config,omitempty" yaml:"worker-config,omitempty"`
}

type Agent struct {
	ID             string               `json:"id"`
	UserID         string               `json:"user_id"`
	Name           string               `json:"name"`
	Description    string               `json:"description"`
	Runbook        string               `json:"runbook"`
	Version        string               `json:"version"`
	Model          AgentModel           `json:"model"`
	AdvancedConfig AgentAdvancedConfig  `json:"advanced_config"`
	ActionPackages []AgentActionPackage `json:"action_packages"`
	McpServers     []McpServer          `json:"mcp_servers"`
	UpdatedAt      time.Time            `json:"updated_at"`
	Metadata       AgentMetadata        `json:"metadata"`
	Files          []AgentFile          `json:"files"`
	Public         bool                 `json:"public"`
}

type LangSmithConfig struct {
	APIKey      string `json:"api_key"`
	URL         string `json:"api_url"`
	ProjectName string `json:"project_name"`
}

type AgentAdvancedConfig struct {
	Architecture AgentArchitecture `json:"architecture"`
	Reasoning    AgentReasoning    `json:"reasoning"`
	LangSmith    *LangSmithConfig  `json:"langsmith"`
}

type AgentFile struct {
	FileID   string `json:"file_id"`
	FilePath string `json:"file_path"`
	FileHash string `json:"file_hash"`
	Embedded bool   `json:"embedded"`
}

type AgentCreatePayload struct {
	Name           string               `json:"name"`
	Description    string               `json:"description"`
	Runbook        string               `json:"runbook"`
	Version        string               `json:"version"`
	Model          AgentModel           `json:"model"`
	AdvancedConfig AgentAdvancedConfig  `json:"advanced_config"`
	ActionPackages []AgentActionPackage `json:"action_packages"`
	McpServers     []McpServer          `json:"mcp_servers"`
	Metadata       AgentMetadata        `json:"metadata"`
}

type AgentPayloadPackageActionServer struct {
	URL    string `json:"url"`
	APIKey string `json:"api_key"`
}

type AgentPayloadPackage struct {
	Public             bool                              `json:"public"`
	Name               string                            `json:"name"`
	AgentPackageUrl    *string                           `json:"agent_package_url"`
	AgentPackageBase64 *string                           `json:"agent_package_base64"`
	Model              AgentModel                        `json:"model"`
	ActionServers      []AgentPayloadPackageActionServer `json:"action_servers"`
	LangSmith          *LangSmithConfig                  `json:"langsmith"`
}
