package common

import (
	"encoding/json"
	"path"

	AgentServer "github.com/Sema4AI/agent-platform/packages/golang-agent-cli/agent-server-client"
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

// ----- SpecAgentKnowledge
type SpecAgentKnowledge struct {
	Name     string `yaml:"name" json:"name"`
	Embedded bool   `yaml:"embedded" json:"embedded"`
	Digest   string `yaml:"digest" json:"digest"`
}

// ----- SpecSemanticDataModel
type SpecSemanticDataModel struct {
	Name string `yaml:"name" json:"name"`
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

type SpecSelectedToolConfig struct {
	Name string `yaml:"name" json:"name"`
}

type SpecSelectedTools struct {
	Tools []SpecSelectedToolConfig `yaml:"tools" json:"tools"`
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
		Value       *string             `yaml:"value,omitempty" json:"value,omitempty"`
	}

	if err := unmarshal(&obj); err != nil {
		return err
	}

	s.Type = obj.Type
	s.Description = obj.Description
	s.Provider = obj.Provider
	s.Scopes = obj.Scopes
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
		Value       *string             `yaml:"value,omitempty" json:"value,omitempty"`
	}{
		Type:        s.Type,
		Description: s.Description,
		Provider:    s.Provider,
		Scopes:      s.Scopes,
		Value:       s.Value,
	}, nil
}

// UnmarshalJSON implements custom unmarshaling for McpServerVariable
func (s *SpecMcpServerVariable) UnmarshalJSON(data []byte) error {
	// Try to unmarshal as a string (scalar value)
	var scalarValue string
	if err := json.Unmarshal(data, &scalarValue); err == nil {
		*s = SpecMcpServerVariable{
			Value: &scalarValue,
		}
		return nil
	}
	// Otherwise, unmarshal as an object
	type Alias SpecMcpServerVariable
	var obj Alias
	if err := json.Unmarshal(data, &obj); err != nil {
		return err
	}
	*s = SpecMcpServerVariable(obj)
	return nil
}

// MarshalJSON implements custom marshaling for McpServerVariable
func (s SpecMcpServerVariable) MarshalJSON() ([]byte, error) {
	// If this is a simple string variable (Type=="string", no description/provider/scopes, only Default set), marshal as string
	if s.HasRawValue() {
		return json.Marshal(s.Value)
	}
	// Otherwise, marshal as an object
	type Alias SpecMcpServerVariable
	return json.Marshal(Alias(s))
}

// HasRawValue checks to see if Value should be treated as raw string and not object
func (s SpecMcpServerVariable) HasRawValue() bool {
	return s.Type == "" && s.Provider == "" && s.Description == "" && len(s.Scopes) == 0
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

// ------ SpecDockerMcpServer
// --- describes the configuration for one MCP server in a Docker container
type SpecDockerMcpGateway struct {
	Catalog *string                        `yaml:"catalog,omitempty" json:"catalog,omitempty"`
	Servers map[string]SpecDockerMcpServer `yaml:"servers,omitempty" json:"servers,omitempty"`
}

type SpecDockerMcpServer struct {
	Tools []string `yaml:"tools,omitempty" json:"tools,omitempty"` // This functions as a whitelist for the tools that are available in the Docker container - if empty, all tools are available
}

// ------ SpecAgent
// --- this is the entry in the Agent Spec file
// --- this represents an Agent from the list of Agents
type SpecAgent struct {
	Name                 string                                  `yaml:"name" json:"name"`
	Description          string                                  `yaml:"description" json:"description"`
	Model                SpecAgentModel                          `yaml:"model" json:"model"`
	Version              string                                  `yaml:"version" json:"version"`
	Architecture         AgentServer.AgentArchitecture           `yaml:"architecture" json:"architecture"`
	Reasoning            AgentServer.AgentReasoning              `yaml:"reasoning" json:"reasoning"`
	Runbook              string                                  `yaml:"runbook" json:"runbook"`
	ConversationGuide    string                                  `yaml:"conversation-guide,omitempty" json:"conversation_guide,omitempty"`
	ConversationStarter  string                                  `yaml:"conversation-starter,omitempty" json:"conversation_starter,omitempty"`
	WelcomeMessage       string                                  `yaml:"welcome-message,omitempty" json:"welcome_message,omitempty"`
	DocumentIntelligence AgentServer.DocumentIntelligenceVersion `yaml:"document-intelligence,omitempty" json:"document_intelligence,omitempty"`
	AgentSettings        map[string]any                          `yaml:"agent-settings,omitempty" json:"agent_settings,omitempty"`
	ActionPackages       []SpecAgentActionPackage                `yaml:"action-packages" json:"action_packages"`
	McpServers           []SpecMcpServer                         `yaml:"mcp-servers,omitempty" json:"mcp_servers,omitempty"`
	DockerMcpGateway     *SpecDockerMcpGateway                   `yaml:"docker-mcp-gateway,omitempty" json:"docker_mcp_gateway,omitempty"`
	Knowledge            []SpecAgentKnowledge                    `yaml:"knowledge" json:"knowledge"`
	SemanticDataModels   []SpecSemanticDataModel                 `yaml:"semantic-data-models,omitempty" json:"semantic_data_models,omitempty"`
	Metadata             AgentServer.AgentMetadata               `yaml:"metadata" json:"metadata"`
	SelectedTools        SpecSelectedTools                       `yaml:"selected-tools,omitempty" json:"selected_tools,omitempty"`
}

func (sa *SpecAgent) IsEqual(ap *AgentProject, deployed *AgentServer.Agent) (bool, AgentChanges) {
	// Calculate the path to the conversation guide file
	if ap == nil || deployed == nil {
		return false, AgentChanges{}
	}
	conversationGuidePath := path.Join(ap.Path, sa.ConversationGuide)
	if sa.ConversationGuide == "" {
		// If the conversation guide is not set, we consider it as equal to the empty string.
		conversationGuidePath = ""
	}

	// Check if the Docker MCP Gateway objects are equal
	// In the Agent this can be part of the MCP servers - we need to remove it from there
	// The check for docker MCP gateway is done separately as we check the object in the Spec and the entry in the Agent
	var specMcpServers []SpecMcpServer
	specHasDockerMcpGateway := false
	for _, mcpServer := range sa.McpServers {
		if !IsSpecDockerMcpGateway(&mcpServer) {
			specMcpServers = append(specMcpServers, mcpServer)
		} else {
			specHasDockerMcpGateway = true
		}
	}
	specHasDockerMcpGateway = specHasDockerMcpGateway || sa.DockerMcpGateway != nil

	var agentMcpServers []AgentServer.McpServer
	agentHasDockerMcpGateway := false
	for _, mcpServer := range deployed.McpServers {
		if !IsAgentDockerMcpGateway(&mcpServer) {
			agentMcpServers = append(agentMcpServers, mcpServer)
		} else {
			agentHasDockerMcpGateway = true
		}
	}

	// Map of changes to check
	changesMap := map[string]bool{
		"name":        sa.Name == deployed.Name,
		"description": sa.Description == deployed.Description,
		// From Agent Server v2 onwards, only the model provider can be selected by the user.
		// Therefore, when detecting changes, we only compare the model provider.
		"modelProvider":        sa.Model.Provider == deployed.Model.Provider,
		"version":              sa.Version == deployed.Version,
		"architecture":         sa.Architecture == deployed.AdvancedConfig.Architecture,
		"reasoning":            sa.Reasoning == deployed.AdvancedConfig.Reasoning,
		"runbook":              sa.Runbook == deployed.Runbook,
		"conversationGuide":    IsConversationGuideEqual(conversationGuidePath, deployed.QuestionGroups),
		"documentIntelligence": sa.DocumentIntelligence == deployed.Extra.DocumentIntelligence,
		"conversationStarter":  sa.ConversationStarter == deployed.Extra.ConversationStarter, // TODO: change this when ConversationStarter is added to top level Agent struct
		"welcomeMessage":       sa.WelcomeMessage == deployed.Extra.WelcomeMessage,           // TODO: change this when WelcomeMessage is added to top level Agent struct
		"metadata":             IsAgentMetadataEqual(sa.Metadata, deployed.Metadata),
		"actionPackages":       AreActionPackagesEqual(sa.ActionPackages, deployed.ActionPackages),
		"mcpServers":           AreMcpServersEqual(specMcpServers, agentMcpServers),
		"dockerMcpGateway":     specHasDockerMcpGateway == agentHasDockerMcpGateway,
		"agentSettings":        AreAgentSettingsEqual(sa.AgentSettings, deployed.Extra.AgentSettings),
		"selectedTools":        AreSelectedToolsEqual(&sa.SelectedTools, &deployed.SelectedTools),
	}

	// Collect the changes
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

// AreSelectedToolsEqual compares two SelectedTools configurations
func AreSelectedToolsEqual(spec *SpecSelectedTools, agent *AgentServer.SelectedTools) bool {
	if len(spec.Tools) != len(agent.ToolNames) {
		return false
	}

	// Create a map to track which tools we've found
	specTools := make(map[string]struct{})
	for _, specTool := range spec.Tools {
		specTools[specTool.Name] = struct{}{}
	}

	// Check if each agent tool exists in the spec
	for _, agentTool := range agent.ToolNames {
		_, exists := specTools[agentTool.ToolName]
		if !exists {
			return false
		}
	}

	return true
}
