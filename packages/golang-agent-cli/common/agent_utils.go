package common

import (
	"fmt"
	"reflect"
	"strconv"
	"strings"

	AgentServer "github.com/Sema4AI/agent-platform/packages/golang-agent-cli/agent-server-client"
)

// === CHECKS FOR EQUALITY ===

// CheckSliceEquality checks if two slices are equal, regardless of order, using a custom equality function.
func CheckSliceEquality[A any, B any](a []A, b []B, equal func(x A, y B) bool) bool {
	if len(a) != len(b) {
		return false
	}

	matched := make(map[int]bool)
	for _, itemA := range a {
		found := false
		for j, itemB := range b {
			if matched[j] {
				continue
			}
			if equal(itemA, itemB) {
				matched[j] = true
				found = true
				break
			}
		}
		if !found {
			return false
		}
	}
	return true
}

// IsAgentMetadataEqual checks if two AgentMetadata structs are equal, accounting for possible nil WorkerConfig.
func IsAgentMetadataEqual(project AgentServer.AgentMetadata, deployed AgentServer.AgentMetadata) bool {
	// Mode Test
	if project.Mode != deployed.Mode {
		return false
	}

	// WelcomeMessage Test
	if project.WelcomeMessage != deployed.WelcomeMessage {
		return false
	}

	// QuestionGroups Test
	if len(project.QuestionGroups) != len(deployed.QuestionGroups) {
		return false
	}
	for i := range project.QuestionGroups {
		if project.QuestionGroups[i].Title != deployed.QuestionGroups[i].Title {
			return false
		}
		if len(project.QuestionGroups[i].Questions) != len(deployed.QuestionGroups[i].Questions) {
			return false
		}
		for j := range project.QuestionGroups[i].Questions {
			if project.QuestionGroups[i].Questions[j] != deployed.QuestionGroups[i].Questions[j] {
				return false
			}
		}
	}

	// WorkerConfig Test
	projectWorkerConfig := project.WorkerConfig
	deployedWorkerConfig := deployed.WorkerConfig
	if projectWorkerConfig == nil && deployedWorkerConfig == nil {
		return true
	}

	// Agent Server v2 is returning the WorkerConfig even if the mode is not 'worker' - in such a case, fields will be nullish.
	// Therefore, we need to check them explicitly if the projectWorkerConfig is itself null.
	if projectWorkerConfig == nil && deployedWorkerConfig.Type == "" && deployedWorkerConfig.DocumentType == "" {
		return true
	}

	if deployedWorkerConfig == nil && projectWorkerConfig.Type == "" && projectWorkerConfig.DocumentType == "" {
		return true
	}

	return projectWorkerConfig.Type == deployedWorkerConfig.Type && projectWorkerConfig.DocumentType == deployedWorkerConfig.DocumentType
}

// IsConversationGuideEqual checks if two conversation guides are equal, one is a file the other a list of QuestionGroups
func IsConversationGuideEqual(local string, deployed []AgentServer.QuestionGroup) bool {
	if local == "" && len(deployed) == 0 {
		return true
	}
	if local == "" && len(deployed) > 0 {
		return false
	}

	// Parse the local file
	questionGroups, err := ReadConversationGuideYAML(local)
	if err != nil {
		return false
	}

	return AreQuestionGroupsEqual(questionGroups, deployed)
}

// AreActionPackagesEqual checks if two slices of action packages are equal, regardless of order.
func AreActionPackagesEqual(local []SpecAgentActionPackage, deployed []AgentServer.AgentActionPackage) bool {
	return CheckSliceEquality(local, deployed, func(specAgentAP SpecAgentActionPackage, deployedAgentAP AgentServer.AgentActionPackage) bool {
		return specAgentAP.IsEqual(&deployedAgentAP)
	})
}

// AreMcpServersEqual checks if two slices of MCP servers are equal (order-insensitive, deep comparison)
func AreMcpServersEqual(local []SpecMcpServer, deployed []AgentServer.McpServer) bool {
	return CheckSliceEquality(local, deployed, func(specMcpServer SpecMcpServer, deployedMcpServer AgentServer.McpServer) bool {
		return isMcpServerEqual(&specMcpServer, &deployedMcpServer)
	})
}

// IsSpecDockerMcpGateway checks if the given SpecMcpServer is a docker MCP gateway entry.
func IsSpecDockerMcpGateway(mcp *SpecMcpServer) bool {
	if mcp == nil {
		return false
	}
	if mcp.CommandLine == nil {
		return false
	}
	if len(mcp.CommandLine) != 4 {
		return false
	}
	return mcp.CommandLine[0] == "docker" &&
		mcp.CommandLine[1] == "mcp" &&
		mcp.CommandLine[2] == "gateway" &&
		mcp.CommandLine[3] == "run"
}

// IsAgentDockerMcpGateway checks if the given AgentServer.McpServer is a docker MCP gateway entry.
func IsAgentDockerMcpGateway(mcp *AgentServer.McpServer) bool {
	if mcp == nil {
		return false
	}
	if mcp.Command == nil {
		return false
	}
	if len(mcp.Args) != 3 {
		return false
	}
	return *mcp.Command == "docker" &&
		mcp.Args[0] == "mcp" &&
		mcp.Args[1] == "gateway" &&
		mcp.Args[2] == "run"
}

// isMcpServerEqual compares a SpecMcpServer and AgentServer.McpServer deeply
func isMcpServerEqual(local *SpecMcpServer, deployed *AgentServer.McpServer) bool {
	if local.Name != deployed.Name {
		return false
	}

	// If the transport is auto, we consider it as equal to the other transport.
	if string(local.Transport) != string(deployed.Transport) && local.Transport != "auto" && deployed.Transport != "auto" {
		return false
	}
	if local.Description != deployed.Description {
		return false
	}
	if local.URL != DerefString(deployed.URL) {
		return false
	}

	if len(local.CommandLine) == 0 {
		if deployed.Command != nil && *deployed.Command != "" {
			return false
		}
		if len(deployed.Args) != 0 {
			return false
		}
	} else {
		if deployed.Command == nil || *deployed.Command != local.CommandLine[0] {
			return false
		}
		if !StringSlicesEqual(local.CommandLine[1:], deployed.Args) {
			return false
		}
	}

	if local.Cwd != DerefString(deployed.Cwd) {
		return false
	}
	if local.ForceSerialToolCalls != deployed.ForceSerialToolCalls {
		return false
	}

	if !mcpServerVariablesEqual(local.Headers, deployed.Headers) {
		return false
	}
	if !mcpServerVariablesEqual(local.Env, deployed.Env) {
		return false
	}
	return true
}

// mcpServerVariablesEqual compares SpecMcpServerVariables and map[string]AgentServer.McpServerVariable
func mcpServerVariablesEqual(local SpecMcpServerVariables, deployed map[string]AgentServer.McpServerVariable) bool {
	if len(local) != len(deployed) {
		return false
	}
	for k, v := range local {
		dep, ok := deployed[k]
		if !ok {
			return false
		}
		if !isMcpServerVariableEqual(&v, &dep) {
			return false
		}
	}
	return true
}

// isMcpServerVariableEqual compares SpecMcpServerVariable and AgentServer.McpServerVariable
func isMcpServerVariableEqual(local *SpecMcpServerVariable, deployed *AgentServer.McpServerVariable) bool {
	if local.HasRawValue() && deployed.HasRawValue() {
		if DerefString(local.Value) != DerefString(deployed.Value) {
			return false
		}
	}
	// If the type is string, we need to check the value
	// For other types, value is nil in the Spec
	if local.Type == SpecMcpTypeString && deployed.Type == "string" {
		if DerefString(local.Value) != DerefString(deployed.Value) {
			return false
		}
	}

	if string(local.Type) != string(deployed.Type) {
		return false
	}
	if local.Description != deployed.Description {
		return false
	}
	if local.Provider != deployed.Provider {
		return false
	}
	if !StringSlicesEqual(local.Scopes, deployed.Scopes) {
		return false
	}

	return true
}

// areQuestionGroupsEqual checks if two QuestionGroups slices are equal (order and content)
func AreQuestionGroupsEqual(local []AgentServer.QuestionGroup, deployed []AgentServer.QuestionGroup) bool {
	return CheckSliceEquality(local, deployed, func(local AgentServer.QuestionGroup, deployed AgentServer.QuestionGroup) bool {
		return local.Title == deployed.Title && StringSlicesEqual(local.Questions, deployed.Questions)
	})
}

// areAgentSettingsEqual checks if two AgentSettings maps are equal, treating nil and empty maps as equal
func AreAgentSettingsEqual(local map[string]any, deployed map[string]any) bool {
	// Treat nil and empty maps as equal for BOTH sides
	localEmpty := len(local) == 0
	deployedEmpty := len(deployed) == 0

	if localEmpty && deployedEmpty {
		return true
	}

	// For more complex comparison that handles YAML parsing differences,
	// we need to normalize the maps before comparison
	normalizedLocal := NormalizeMap(local)
	normalizedDeployed := NormalizeMap(deployed)

	// Use reflect.DeepEqual for deep comparison of the normalized map contents
	equal := reflect.DeepEqual(normalizedLocal, normalizedDeployed)
	return equal
}

// NormalizeMap converts interface{} keys to string keys recursively to handle YAML parsing differences
func NormalizeMap(m map[string]any) map[string]any {
	if m == nil {
		return nil
	}

	result := make(map[string]any)
	for k, v := range m {
		result[k] = normalizeValue(v)
	}
	return result
}

// normalizeValue recursively normalizes values, converting map[interface{}]interface{} to map[string]interface{}
func normalizeValue(v any) any {
	if v == nil {
		return nil
	}

	switch val := v.(type) {
	// Normalize integer types to a common int64 to avoid DeepEqual false positives
	case int:
		return float64(val)
	case int8:
		return float64(val)
	case int16:
		return float64(val)
	case int32:
		return float64(val)
	case int64:
		return float64(val)
	case uint:
		return float64(val)
	case uint8:
		return float64(val)
	case uint16:
		return float64(val)
	case uint32:
		return float64(val)
	case uint64:
		return float64(val)
	case float32:
		return float64(val)
	case float64:
		return float64(val)
	case string:
		// Attempt to coerce numeric strings to numbers for robust deep equality checks
		s := strings.TrimSpace(val)
		if i, err := strconv.ParseInt(s, 10, 64); err == nil {
			// Normalize numeric strings to float64 to match other numeric types after normalization
			return float64(i)
		}
		if f, err := strconv.ParseFloat(s, 64); err == nil {
			return f
		}
		return val
	case map[interface{}]interface{}:
		// Convert map[interface{}]interface{} to map[string]interface{}
		result := make(map[string]interface{})
		for k, v := range val {
			if keyStr, ok := k.(string); ok {
				result[keyStr] = normalizeValue(v)
			}
		}
		return result
	case map[string]interface{}:
		// Recursively normalize nested maps
		result := make(map[string]interface{})
		for k, v := range val {
			result[k] = normalizeValue(v)
		}
		return result
	case []interface{}:
		// Recursively normalize slice elements
		result := make([]interface{}, len(val))
		for i, item := range val {
			result[i] = normalizeValue(item)
		}
		return result
	default:
		return v
	}
}

// === FINDERS ===

func FindDeployedAgentById(agents []*AgentServer.Agent, agentId string) *AgentServer.Agent {
	for _, agent := range agents {
		if agent.ID == agentId {
			return agent
		}
	}
	return nil
}

func GetDeployedAgentByName(name, serverURL string) (*AgentServer.Agent, error) {
	client := AgentServer.NewClient(serverURL)
	agents, err := client.GetAgents(false)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch agents: %w", err)
	}

	for _, a := range *agents {
		if a.Name == name {
			return &a, nil
		}
	}
	return nil, fmt.Errorf("agent not found: %s", name)
}
