package common

import (
	"encoding/json"

	AgentServer "github.com/Sema4AI/agent-platform/packages/golang-agent-cli/agent-server-client"
)

type AgentPackageMetadataKnowledge struct {
	Embedded bool   `json:"embedded"`
	Name     string `json:"name"`
	Digest   string `json:"digest"`
}

type AgentPackageMetadata struct {
	ReleaseNote         string                              `json:"release_note"`
	Version             string                              `json:"version"`
	Icon                string                              `json:"icon"`
	Name                string                              `json:"name"`
	Description         string                              `json:"description"`
	Model               SpecAgentModel                      `json:"model"`
	Architecture        AgentServer.AgentArchitecture       `json:"architecture"`
	Reasoning           AgentServer.AgentReasoning          `json:"reasoning"`
	Knowledge           []AgentPackageMetadataKnowledge     `json:"knowledge"`
	Datasources         []AgentPackageDatasource            `json:"datasources"`
	QuestionGroups      AgentServer.QuestionGroups          `json:"question_groups,omitempty"`
	ConversationStarter string                              `json:"conversation_starter,omitempty"`
	WelcomeMessage      string                              `json:"welcome_message,omitempty"`
	AgentSettings       map[string]any                      `json:"agent_settings,omitempty"`
	Metadata            AgentServer.AgentMetadata           `json:"metadata"`
	ActionPackages      []AgentPackageActionPackageMetadata `json:"action_packages"`
	McpServers          []AgentPackageMcpServer             `json:"mcp_servers,omitempty"`
	DockerMcpGateway    *AgentPackageDockerMcpGateway       `json:"docker_mcp_gateway,omitempty"`

	// Differences from external sources
	DockerMcpGatewayChanges DockerMcpGatewayChanges `json:"docker_mcp_gateway_changes,omitempty"`
}

type AgentPackageDockerMcpGateway struct {
	Catalog *string                      `json:"catalog,omitempty"`
	Servers DockerCatalogRegistryEntries `json:"servers,omitempty"`
}

type AgentPackageMcpServer struct {
	Name                 string                         `json:"name"`
	Transport            AgentServer.MCPTransport       `json:"transport,omitempty"`
	Description          string                         `json:"description,omitempty"`
	URL                  string                         `json:"url,omitempty"`
	Headers              AgentPackageMcpServerVariables `json:"headers,omitempty"`
	Command              string                         `json:"command,omitempty"`
	Arguments            []string                       `json:"args,omitempty"`
	Env                  AgentPackageMcpServerVariables `json:"env,omitempty"`
	Cwd                  string                         `json:"cwd,omitempty"`
	ForceSerialToolCalls bool                           `json:"force_serial_tool_calls"`
}

type AgentPackageMcpServerVariables = map[string]AgentPackageMcpServerVariable

type AgentPackageMcpServerVariable struct {
	// If the JSON node was a scalar we store it here.
	Value *string `json:"value,omitempty"`

	// The object forms share "type" and (optional) "description".
	Type        string   `json:"type,omitempty"`
	Description string   `json:"description,omitempty"`
	Provider    string   `json:"provider,omitempty"`
	Scopes      []string `json:"scopes,omitempty"`
}

// UnmarshalJSON implements custom unmarshaling for AgentPackageMcpServerVariable
func (s *AgentPackageMcpServerVariable) UnmarshalJSON(data []byte) error {
	// Try to unmarshal as a string (scalar value)
	var scalarValue string
	if err := json.Unmarshal(data, &scalarValue); err == nil {
		s.Value = &scalarValue
		return nil
	}
	// Otherwise, unmarshal as an object
	type Alias AgentPackageMcpServerVariable
	var obj Alias
	if err := json.Unmarshal(data, &obj); err != nil {
		return err
	}
	*s = AgentPackageMcpServerVariable(obj)
	return nil
}

// MarshalJSON implements custom marshaling for AgentPackageMcpServerVariable
func (s AgentPackageMcpServerVariable) MarshalJSON() ([]byte, error) {
	// If this is a simple string variable (Type=="string", no description/provider/scopes, only Default set), marshal as string
	if s.HasRawValue() {
		return json.Marshal(s.Value)
	}
	// Otherwise, marshal as an object
	type Alias AgentPackageMcpServerVariable
	return json.Marshal(Alias(s))
}

// HasRawValue checks to see if Value should be treated as raw string and not object
func (s AgentPackageMcpServerVariable) HasRawValue() bool {
	return s.Type == "" && s.Description == "" && s.Provider == "" && len(s.Scopes) == 0
}

func BuildAgentPackageMcpServerVariable(val *SpecMcpServerVariable) AgentPackageMcpServerVariable {
	return AgentPackageMcpServerVariable{
		Value:       val.Value,
		Type:        string(val.Type),
		Description: val.Description,
		Provider:    val.Provider,
		Scopes:      val.Scopes,
	}
}

func BuildSpecMcpServerVariable(val *AgentServer.McpServerVariable) SpecMcpServerVariable {
	return SpecMcpServerVariable{
		Value:       val.Value,
		Type:        SpecMcpVariableType(val.Type),
		Description: val.Description,
		Provider:    val.Provider,
		Scopes:      val.Scopes,
	}
}

func BuildAgentMcpServerVariable(val *AgentPackageMcpServerVariable) AgentServer.McpServerVariable {
	return AgentServer.McpServerVariable{
		Value:       val.Value,
		Type:        val.Type,
		Description: val.Description,
		Provider:    val.Provider,
		Scopes:      val.Scopes,
	}
}

type AgentPackageActionPackageMetadata struct {
	ActionPackageMetadata
	Whitelist string `json:"whitelist"`
	Icon      string `json:"icon"`
	Path      string `json:"path"`
}

type ExternalEndpointRule struct {
	Host string `json:"host"`
	Port int    `json:"port"`
}

type ExternalEndpoint struct {
	Name           string                 `json:"name"`
	Description    string                 `json:"description"`
	AdditionalInfo string                 `json:"additional-info-link"`
	Rules          []ExternalEndpointRule `json:"rules"`
}

type ActionPackageMetadata struct {
	Name              string                        `json:"name"`
	Description       string                        `json:"description"`
	Secrets           map[string]interface{}        `json:"secrets"`
	Version           string                        `json:"action_package_version"`
	Actions           []ActionPackageMetadataAction `json:"actions"`
	ExternalEndpoints []ExternalEndpoint            `json:"external-endpoints,omitempty"`
}

type ActionPackageMetadataAction struct {
	Description   string `json:"description"`
	Name          string `json:"name"`
	Summary       string `json:"summary"`
	OperationKind string `json:"operation_kind"`
}

type AgentPackageDatasource struct {
	CustomerFacingName string                 `json:"customer_facing_name"`
	Engine             string                 `json:"engine"`
	Description        string                 `json:"description"`
	Configuration      map[string]interface{} `json:"configuration"`
}

// ConversationGuide is a construct on top of QuestionGroups.
// ConversationGuide is specified in the spec as a reference to a YAML file.
// AgentPackageConversationGuideContents struct represents the contents of that file.
type AgentPackageConversationGuideContents struct {
	QuestionGroups AgentServer.QuestionGroups `json:"question-groups,omitempty" yaml:"question-groups,omitempty"`
}
