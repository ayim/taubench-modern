package agent_server_client

import (
	"encoding/json"
	"time"
)

type AgentReasoning string
type AgentModelProvider string
type AgentArchitecture string
type AgentMode string
type WorkerType string
type DocumentIntelligenceVersion string

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

const (
	DocumentIntelligenceVersionV2 DocumentIntelligenceVersion = "v2"
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
	APIKey            string            `json:"api_key,omitempty"`
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

type McpServerVariable struct {
	// The object forms share "type" and (optional) "description".
	Type        string   `json:"type,omitempty"`
	Description string   `json:"description,omitempty"`
	Provider    string   `json:"provider,omitempty"`
	Scopes      []string `json:"scopes,omitempty"`

	// The value that is sent over by the user to be used as replacement for variable object
	Value *string `json:"value,omitempty"`
}

// UnmarshalJSON implements custom unmarshaling for McpServerVariable
func (s *McpServerVariable) UnmarshalJSON(data []byte) error {
	// Try to unmarshal as a string (scalar value)
	var scalarValue string
	if err := json.Unmarshal(data, &scalarValue); err == nil {
		*s = McpServerVariable{
			Value: &scalarValue,
		}
		return nil
	}
	// Otherwise, unmarshal as an object
	type Alias McpServerVariable
	var obj Alias
	if err := json.Unmarshal(data, &obj); err != nil {
		return err
	}
	*s = McpServerVariable(obj)
	return nil
}

// MarshalJSON implements custom marshaling for McpServerVariable
func (s McpServerVariable) MarshalJSON() ([]byte, error) {
	// If this is a simple string variable (Type=="string", no description/provider/scopes, only Default set), marshal as string
	if s.HasRawValue() {
		return json.Marshal(s.Value)
	}
	// Otherwise, marshal as an object
	type Alias McpServerVariable
	return json.Marshal(Alias(s))
}

// HasRawValue checks to see if Value should be treated as raw string and not object
func (s McpServerVariable) HasRawValue() bool {
	return s.Type == "" && s.Provider == "" && s.Description == "" && len(s.Scopes) == 0
}

type McpServerVariables = map[string]McpServerVariable

type McpServer struct {
	// Name of the MCP server.
	Name string `json:"name"`

	// Description of the MCP server.
	Description string `json:"description,omitempty"`

	// Transport protocol to use when connecting to the MCP server.
	// Auto defaults to streamable-http unless “sse” is in the URL;
	// if there is no URL, defaults to stdio.
	Transport MCPTransport `json:"transport"`

	// URL of the MCP server. This should point directly
	// to the transport endpoint to use.
	URL *string `json:"url,omitempty"`

	// Headers used for configuring requests & connections to the MCP server
	Headers McpServerVariables `json:"headers,omitempty"`

	// Command to run the MCP server. If not provided,
	// the MCP server will be assumed to be running locally.
	Command *string `json:"command,omitempty"`

	// Arguments to pass to the MCP server command.
	Args []string `json:"args,omitempty"`

	// Environment variables to set for the MCP server command.
	Env McpServerVariables `json:"env,omitempty"`

	// Working directory to run the MCP server command in.
	Cwd *string `json:"cwd,omitempty"`

	// If true, all tool calls are executed under a lock
	// to support servers that cannot interleave multiple requests.
	ForceSerialToolCalls bool `json:"force_serial_tool_calls"`
}

type QuestionGroup struct {
	Title     string   `json:"title"`
	Questions []string `json:"questions"`
}

type QuestionGroups = []QuestionGroup

// === AGENT ===

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

// DataConnection represents a data connection
type DataConnection struct {
	ID   string `json:"id"`
	Name string `json:"name"`
}

// SemanticDataModel represents a semantic data model associated with an agent
// The server returns a map[string]interface{} where the key is the SDM ID
// and the value is the semantic model content
type SemanticDataModel struct {
	ID            string
	SemanticModel map[string]interface{}
}

type AgentMetadata struct {
	Mode           AgentMode      `json:"mode"`
	WorkerConfig   *WorkerConfig  `json:"worker_config,omitempty" yaml:"worker-config,omitempty"`
	QuestionGroups QuestionGroups `json:"question_groups,omitempty" yaml:"question-groups,omitempty"`
	WelcomeMessage string         `json:"welcome_message,omitempty" yaml:"welcome-message,omitempty"`
}

type AgentExtra struct {
	DocumentIntelligence DocumentIntelligenceVersion `json:"document_intelligence,omitempty" yaml:"document-intelligence,omitempty"`
	ConversationStarter  string                      `json:"conversation_starter,omitempty" yaml:"conversation-starter,omitempty"`
	WelcomeMessage       string                      `json:"welcome_message,omitempty" yaml:"welcome-message,omitempty"`
	AgentSettings        map[string]any              `json:"agent_settings,omitempty" yaml:"agent-settings,omitempty"`
}

type Agent struct {
	ID             string               `json:"id"`
	UserID         string               `json:"user_id"`
	Name           string               `json:"name"`
	Description    string               `json:"description"`
	Version        string               `json:"version"`
	Runbook        string               `json:"runbook"`
	Model          AgentModel           `json:"model"`
	AdvancedConfig AgentAdvancedConfig  `json:"advanced_config"`
	ActionPackages []AgentActionPackage `json:"action_packages"`
	McpServers     []McpServer          `json:"mcp_servers"`
	UpdatedAt      time.Time            `json:"updated_at"`
	QuestionGroups QuestionGroups       `json:"question_groups,omitempty"`
	Metadata       AgentMetadata        `json:"metadata,omitempty"`
	Extra          AgentExtra           `json:"extra,omitempty"`
	AgentSettings  map[string]any       `json:"agent_settings,omitempty"`
	Files          []AgentFile          `json:"files"`
	Public         bool                 `json:"public"`
}

type AgentPayload struct {
	Name           string               `json:"name"`
	Description    string               `json:"description"`
	Version        string               `json:"version"`
	Runbook        string               `json:"runbook"`
	Model          AgentModel           `json:"model"`
	AdvancedConfig AgentAdvancedConfig  `json:"advanced_config,omitempty"`
	ActionPackages []AgentActionPackage `json:"action_packages"`
	McpServers     []McpServer          `json:"mcp_servers,omitempty"`
	QuestionGroups QuestionGroups       `json:"question_groups,omitempty"`
	Metadata       AgentMetadata        `json:"metadata,omitempty"` // TODO: remove this as Metadata is deprecated
	Extra          AgentExtra           `json:"extra,omitempty"`
	AgentSettings  map[string]any       `json:"agent_settings,omitempty"`
	Files          []AgentFile          `json:"files,omitempty"`
	Public         bool                 `json:"public"`
}

type AgentPayloadPackage struct {
	Public             bool                 `json:"public"`
	Name               string               `json:"name"`
	AgentPackageUrl    *string              `json:"agent_package_url"`
	AgentPackageBase64 *string              `json:"agent_package_base64"`
	Model              AgentModel           `json:"model"`
	ActionServers      []AgentActionPackage `json:"action_servers"`
	McpServers         []McpServer          `json:"mcp_servers"`
	LangSmith          *LangSmithConfig     `json:"langsmith"`
}
