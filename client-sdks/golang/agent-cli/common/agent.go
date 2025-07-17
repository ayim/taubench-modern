package common

import (
	AgentServer "github.com/Sema4AI/agent-platform/client-sdks/golang/agent-client-go/pkg/client"
)

const (
	AgentSpecMcpServersFilter AgentSpecFilter = "mcp-servers-filter"
)

// Add this variable for pointer usage
var AgentSpecMcpServersFilterPtr = AgentSpecMcpServersFilter

type AgentSpecFilter string

const (
	ActionPackageFolder SpecAgentActionPackageType = "folder"
	ActionPackageZip    SpecAgentActionPackageType = "zip"
)

type SpecAgentActionPackageType string

// ----- SpecAgentActionPackage
type SpecAgentKnowledge struct {
	Name     string `yaml:"name" json:"name"`
	Embedded bool   `yaml:"embedded" json:"embedded"`
	Digest   string `yaml:"digest" json:"digest"`
}

// ----- SpecAgentModel
type SpecAgentModel struct {
	Provider AgentServer.AgentModelProvider `yaml:"provider" json:"provider"`
	Name     string                         `yaml:"name" json:"name"`
}

// ----- SpecAgentActionPackage
type SpecAgentActionPackage struct {
	Name         string                     `yaml:"name" json:"name"`
	Organization string                     `yaml:"organization" json:"organization"`
	Type         SpecAgentActionPackageType `yaml:"type" json:"type"`
	Version      string                     `yaml:"version" json:"version"`
	Whitelist    string                     `yaml:"whitelist" json:"whitelist"`
	Path         string                     `yaml:"path" json:"path"`
}

func (a *SpecAgentActionPackage) IsEqual(deployed *AgentServer.AgentActionPackage) bool {
	return a.Name == deployed.Name &&
		a.Organization == deployed.Organization &&
		a.Version == deployed.Version &&
		a.Whitelist == deployed.Whitelist
}

// ------ SpecMcpVariableType defines allowed types for headers and environment variables
type SpecMcpVariableType string

const (
	SpecMcpTypeString         SpecMcpVariableType = "string"
	SpecMcpTypeSecret         SpecMcpVariableType = "secret"
	SpecMcpTypeOAuth2Secret   SpecMcpVariableType = "oauth2-secret"
	SpecMcpTypeDataServerInfo SpecMcpVariableType = "data-server-info"
)

// ------ SpecMcpServerVariable
// --- represents a single header or env entry for HTTP/SSE/STDIO  MCP servers
type SpecMcpServerVariable struct {
	// The object forms share "type" and (optional) "description".
	Type        SpecMcpVariableType `yaml:"type,omitempty" json:"type,omitempty"`
	Description string              `yaml:"description,omitempty" json:"description,omitempty"`
	Provider    string              `yaml:"provider,omitempty" json:"provider,omitempty"`
	Scopes      []string            `yaml:"scopes,omitempty" json:"scopes,omitempty"`
	Default     string              `yaml:"default,omitempty" json:"default,omitempty"`

	// The value that is sent over by the user to be used as replacement for variable object
	Value *string `yaml:"value,omitempty" json:"value,omitempty"`
}

// UnmarshalYAML implements custom unmarshaling for SpecMcpServerVariable
// to handle both scalar string values and object values
func (s *SpecMcpServerVariable) UnmarshalYAML(unmarshal func(interface{}) error) error {
	// First, try to unmarshal as a string (scalar value)
	var scalarValue string
	if err := unmarshal(&scalarValue); err == nil {
		s.Value = &scalarValue
		return nil
	}

	// If that fails, try to unmarshal as an object
	var obj struct {
		Type        SpecMcpVariableType `yaml:"type" json:"type"`
		Description string              `yaml:"description,omitempty" json:"description,omitempty"`
		Provider    string              `yaml:"provider,omitempty" json:"provider,omitempty"`
		Scopes      []string            `yaml:"scopes,omitempty" json:"scopes,omitempty"`
		Default     string              `yaml:"default,omitempty" json:"default,omitempty"`
		Value       *string             `yaml:"value,omitempty" json:"value,omitempty"`
	}

	if err := unmarshal(&obj); err != nil {
		return err
	}

	s.Type = obj.Type
	s.Description = obj.Description
	s.Provider = obj.Provider
	s.Scopes = obj.Scopes
	s.Default = obj.Default
	s.Value = obj.Value

	return nil
}

// MarshalYAML implements custom marshaling for SpecMcpServerVariable
func (s SpecMcpServerVariable) MarshalYAML() (interface{}, error) {
	// If this is a simple string variable (Type=="string", no description/provider/scopes, only Default set), marshal as scalar
	if s.HasRawValue() {
		return s.Value, nil
	}
	// Otherwise, marshal as a mapping
	return struct {
		Type        SpecMcpVariableType `yaml:"type" json:"type"`
		Description string              `yaml:"description,omitempty" json:"description,omitempty"`
		Provider    string              `yaml:"provider,omitempty" json:"provider,omitempty"`
		Scopes      []string            `yaml:"scopes,omitempty" json:"scopes,omitempty"`
		Default     string              `yaml:"default,omitempty" json:"default,omitempty"`
		Value       *string             `yaml:"value,omitempty" json:"value,omitempty"`
	}{
		Type:        s.Type,
		Description: s.Description,
		Provider:    s.Provider,
		Scopes:      s.Scopes,
		Default:     s.Default,
		Value:       s.Value,
	}, nil
}

// HasRawValue checks to see if Value should be treated as raw string and not object
func (s SpecMcpServerVariable) HasRawValue() bool {
	return s.Type == "" && s.Provider == "" && s.Description == "" && s.Default == "" && len(s.Scopes) == 0
}

type SpecMcpServerVariables = map[string]SpecMcpServerVariable

// ------ SpecMcpServer
// --- describes the configuration for one MCP server
type SpecMcpServer struct {
	Name                 string                   `yaml:"name" json:"name"`
	Transport            AgentServer.MCPTransport `yaml:"transport" json:"transport,omitempty"`
	Description          string                   `yaml:"description,omitempty" json:"description,omitempty"`
	URL                  string                   `yaml:"url,omitempty" json:"url,omitempty"`
	Headers              SpecMcpServerVariables   `yaml:"headers,omitempty" json:"headers,omitempty"`
	CommandLine          []string                 `yaml:"command-line,omitempty" json:"command_line,omitempty"`
	Env                  SpecMcpServerVariables   `yaml:"env,omitempty" json:"env,omitempty"`
	Cwd                  string                   `yaml:"cwd,omitempty" json:"cwd,omitempty"`
	ForceSerialToolCalls bool                     `yaml:"force-serial-tool-calls,omitempty" json:"force_serial_tool_calls,omitempty"`
}

// ------ SpecAgent
// --- this is the entry in the Agent Spec file
// --- this represents an Agent from the list of Agents
type SpecAgent struct {
	Name                string                        `yaml:"name" json:"name"`
	Description         string                        `yaml:"description" json:"description"`
	Model               SpecAgentModel                `yaml:"model" json:"model"`
	Version             string                        `yaml:"version" json:"version"`
	Architecture        AgentServer.AgentArchitecture `yaml:"architecture" json:"architecture"`
	Reasoning           AgentServer.AgentReasoning    `yaml:"reasoning" json:"reasoning"`
	Runbook             string                        `yaml:"runbook" json:"runbook"`
	ConversationGuide   string                        `yaml:"conversation-guide,omitempty" json:"conversation_guide,omitempty"`
	ConversationStarter string                        `yaml:"conversation-starter,omitempty" json:"conversation_starter,omitempty"`
	WelcomeMessage      string                        `yaml:"welcome-message,omitempty" json:"welcome_message,omitempty"`
	ActionPackages      []SpecAgentActionPackage      `yaml:"action-packages" json:"action_packages"`
	McpServers          []SpecMcpServer               `yaml:"mcp-servers,omitempty" json:"mcp_servers,omitempty"`
	Knowledge           []SpecAgentKnowledge          `yaml:"knowledge" json:"knowledge"`
	Metadata            AgentServer.AgentMetadata     `yaml:"metadata" json:"metadata"`
}

func (a *SpecAgent) IsEqual(deployed *AgentServer.Agent) (bool, AgentChanges) {
	changesMap := map[string]bool{
		"name":        a.Name == deployed.Name,
		"description": a.Description == deployed.Description,
		// From Agent Server v2 onwards, only the model provider can be selected by the user.
		// Therefore, when detecting changes, we only compare the model provider.
		"modelProvider":       a.Model.Provider == deployed.Model.Provider,
		"version":             a.Version == deployed.Version,
		"architecture":        a.Architecture == deployed.AdvancedConfig.Architecture,
		"reasoning":           a.Reasoning == deployed.AdvancedConfig.Reasoning,
		"runbook":             a.Runbook == deployed.Runbook,
		"conversationGuide":   IsConversationGuideEqual(a.ConversationGuide, deployed.QuestionGroups),
		"conversationStarter": a.ConversationStarter == deployed.Extra.ConversationStarter, // TODO: change this when ConversationStarter is added to top level Agent struct
		"welcomeMessage":      a.WelcomeMessage == deployed.Extra.WelcomeMessage,           // TODO: change this when WelcomeMessage is added to top level Agent struct
		"metadata":            IsAgentMetadataEqual(a.Metadata, deployed.Metadata),
		"actionPackages":      AreActionPackagesEqual(a.ActionPackages, deployed.ActionPackages),
		"mcpServers":          AreMcpServersEqual(a.McpServers, deployed.McpServers),
	}

	changes := AgentChanges{}
	for key, synced := range changesMap {
		if !synced {
			changes = append(changes, key)
		}
	}

	return len(changes) == 0, changes
}

// ------ SpecAgentPackage
// --- one level deeper where Version, list of Agents & exclude are present
type SpecAgentPackage struct {
	SpecVersion string      `yaml:"spec-version" json:"spec_version"`
	Agents      []SpecAgent `yaml:"agents" json:"agents"`
	Exclude     []string    `yaml:"exclude" json:"exclude"`
}

// ------ AgentSpec
// --- top level struct that holds the entire Agent Package Spec
type AgentSpec struct {
	AgentPackage SpecAgentPackage `yaml:"agent-package" json:"agent_package"`
}
