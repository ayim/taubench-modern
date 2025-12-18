package cmd

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	AgentServer "github.com/Sema4AI/agent-platform/packages/golang-agent-cli/agent-server-client"
	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/common"
	"github.com/Sema4AI/agent-platform/packages/golang-agent-cli/pretty"
	rccCommon "github.com/Sema4AI/rcc/common"
	"github.com/spf13/cobra"
)

var (
	public                bool
	modelConfig           string
	actionServerConfig    string
	langSmithConfig       string
	localAgentProjectPath string
)

func getAgentNameFromMetadata(metadata []*common.AgentPackageMetadata) string {
	if len(metadata) == 0 || metadata[0] == nil {
		return ""
	}
	return metadata[0].Name
}

func getActionPackagesFromMetadata(metadata []*common.AgentPackageMetadata) []common.AgentPackageActionPackageMetadata {
	return metadata[0].ActionPackages
}

func getAgentModelFromMetadata(metadata []*common.AgentPackageMetadata) AgentServer.AgentModel {
	if len(metadata) == 0 || metadata[0] == nil {
		return AgentServer.AgentModel{
			Provider: "",
			Name:     "",
			Config:   map[string]interface{}{},
		}
	}
	return AgentServer.AgentModel{
		Provider: metadata[0].Model.Provider,
		Name:     metadata[0].Model.Name,
		Config:   map[string]interface{}{},
	}
}
func getMcpServersFromMetadata(metadata []*common.AgentPackageMetadata) []AgentServer.McpServer {
	if len(metadata) == 0 || metadata[0] == nil {
		return []AgentServer.McpServer{}
	}
	var servers []AgentServer.McpServer
	for _, mcp := range metadata[0].McpServers {
		headers := make(map[string]AgentServer.McpServerVariable)
		for key, value := range mcp.Headers {
			headers[key] = common.BuildAgentMcpServerVariable(&value)
		}

		env := make(map[string]AgentServer.McpServerVariable)
		for key, value := range mcp.Env {
			env[key] = common.BuildAgentMcpServerVariable(&value)
		}

		servers = append(servers, AgentServer.McpServer{
			Name:                 mcp.Name,
			Description:          mcp.Description,
			Transport:            mcp.Transport,
			URL:                  &mcp.URL,
			Headers:              headers,
			Command:              &mcp.Command,
			Args:                 mcp.Arguments,
			Env:                  env,
			Cwd:                  &mcp.Cwd,
			ForceSerialToolCalls: mcp.ForceSerialToolCalls,
		})
	}

	if dockerMcpGateway := getDockerMCPGateway(metadata); dockerMcpGateway != nil {
		servers = append(servers, *dockerMcpGateway)
	}

	return servers
}

func getSelectedToolsFromMetadata(metadata []*common.AgentPackageMetadata) AgentServer.SelectedTools {
	if len(metadata) == 0 || metadata[0] == nil {
		return AgentServer.NewSelectedTools()
	}

	var toolConfigs []AgentServer.SelectedToolConfig
	for _, toolConfig := range metadata[0].SelectedTools.Tools {
		toolConfigs = append(toolConfigs, AgentServer.SelectedToolConfig{
			Name: toolConfig.Name,
		})
	}

	return AgentServer.SelectedTools{
		Tools: toolConfigs,
	}
}

func getDockerMCPGateway(metadata []*common.AgentPackageMetadata) *AgentServer.McpServer {
	if len(metadata) == 0 || metadata[0] == nil || metadata[0].DockerMcpGateway == nil {
		return nil
	}

	// Check if the docker MCP gateway is empty
	if len(metadata[0].DockerMcpGateway.Servers) == 0 {
		return nil
	}

	// Check if the Docker MCP Gateway registry is installed
	// TODO: decide later if we want to fail if the registry is not found
	if _, err := common.DockerParseRegistryYAML(); err != nil {
		pretty.LogIfVerbose("[getDockerMCPGateway] failed to parse Docker MCP Gateway registry (most likely not installed): %+v", err)
	}

	// Compose the MCP server for the docker MCP gateway
	pretty.LogIfVerbose("[getDockerMCPGateway] adding Docker MCP Gateway to the list of MCP servers...")
	return &AgentServer.McpServer{
		Name:                 "MCP_DOCKER",
		Description:          "Docker MCP Gateway",
		Transport:            AgentServer.MCPTransportStdio,
		URL:                  nil,
		Headers:              map[string]AgentServer.McpServerVariable{},
		Command:              common.Ptr("docker"),
		Args:                 []string{"mcp", "gateway", "run"},
		Env:                  map[string]AgentServer.McpServerVariable{},
		Cwd:                  nil,
		ForceSerialToolCalls: false,
	}
}

func getModelConfig(modelConfig string) (map[string]interface{}, error) {
	if modelConfig == "" {
		return map[string]interface{}{}, nil
	}
	var config map[string]interface{}
	if err := json.Unmarshal([]byte(modelConfig), &config); err != nil {
		return nil, fmt.Errorf("failed to parse model config: %w", err)
	}
	return config, nil
}

func getActionServerConfig(actionServerConfig string) (*AgentServer.AgentActionPackage, error) {
	if actionServerConfig == "" {
		return nil, nil
	}
	var config *AgentServer.AgentActionPackage
	if err := json.Unmarshal([]byte(actionServerConfig), &config); err != nil {
		return nil, fmt.Errorf("failed to parse action server config: %w", err)
	}
	return config, nil
}

func getLangsmithConfig(langsmithConfig string) (*AgentServer.LangSmithConfig, error) {
	if langsmithConfig == "" {
		return nil, nil
	}
	var config AgentServer.LangSmithConfig
	if err := json.Unmarshal([]byte(langsmithConfig), &config); err != nil {
		return nil, fmt.Errorf("failed to parse langsmith config: %w", err)
	}
	return &config, nil
}

func prepareActionPackages(metadata []*common.AgentPackageMetadata, agentPackageDestPath string) error {
	galleryRootDir := common.S4SActionsGalleryLocation()
	if !common.FileExists(galleryRootDir) {
		pretty.LogIfVerbose("[prepareActionPackages] skipping the Action Packages preparation as Sema4.ai Studio Gallery was not found")
		return nil
	}

	pretty.LogIfVerbose("[prepareActionPackages] importing Action Packages...")
	actionPackages := getActionPackagesFromMetadata(metadata)
	for _, actionPackage := range actionPackages {
		pretty.LogIfVerbose("[prepareActionPackages] Action Package Path: %+v", actionPackage.Path)

		// skipping action packages coming from Sema4.ai
		if strings.Contains(actionPackage.Path, common.S4S_BUNDLED_ACTIONS_DIR) {
			pretty.LogIfVerbose("[prepareActionPackages] skipping import of Action Package: %s", actionPackage.Path)
			continue
		}

		// determine the organization and the package name from the path
		actionPackageOrganization, actionPackagePackageName := filepath.Split(actionPackage.Path)
		if actionPackageOrganization == "" || actionPackagePackageName == "" {
			return fmt.Errorf("[prepareActionPackages] failed to parse Action Package path")
		}

		// (source) calculate where the action packages need to be copied from
		actionPackageSourcePath := filepath.Join(agentPackageDestPath, common.AGENT_PROJECT_ACTIONS_DIR, actionPackageOrganization, actionPackagePackageName)
		pretty.LogIfVerbose("Action Package Path from the extracted Agent Package: %+v", actionPackageSourcePath)
		if !common.FileExists(actionPackageSourcePath) {
			return fmt.Errorf("[prepareActionPackages] calculated source path does not exist")
		}

		// (destination) calculate where the action packages need to be copied to
		actionPackageDestPath := filepath.Join(galleryRootDir, actionPackageOrganization, actionPackagePackageName, actionPackage.Version)
		pretty.LogIfVerbose("[prepareActionPackages] importing Action Package to: %+v", actionPackageDestPath)
		if err := os.MkdirAll(actionPackageDestPath, 0o755); err != nil {
			return fmt.Errorf("[prepareActionPackages] failed to create destination for Action Package: %w", err)
		}

		// we don't have a zipped action package but an expanded one
		if err := common.CopyDir(actionPackageSourcePath, actionPackageDestPath, true); err != nil {
			return fmt.Errorf("[prepareActionPackages] failed to copy files for Action Package: %w", err)
		}
		pretty.LogIfVerbose("[prepareActionPackages] Action Package  '%s'  imported successfully to: %s", actionPackage.Name, actionPackageDestPath)
	}

	return nil
}

func BuildAgentPayload(
	metadata []*common.AgentPackageMetadata,
	spec *common.AgentSpec,
	runbook string,
	modelConfiguration string,
	actionServerConfiguration string,
	langSmithConfiguration string,
	makePublic bool,
) (*AgentServer.AgentPayload, error) {
	actionPackages := []AgentServer.AgentActionPackage{}
	for _, ap := range metadata[0].ActionPackages {
		// determine the organization and the package name from the path
		actionPackageOrganization, actionPackagePackageName := filepath.Split(ap.Path)
		if actionPackageOrganization == "" || actionPackagePackageName == "" {
			return nil, fmt.Errorf("[BuildAgentPayload] failed to parse Action Package path")
		}

		actionPackages = append(actionPackages, AgentServer.AgentActionPackage{
			Name:         ap.Name,
			Organization: strings.Trim(actionPackageOrganization, "/"),
			Version:      ap.Version,
			Whitelist:    ap.Whitelist,
		})
	}

	actionServerConfig, err := getActionServerConfig(actionServerConfiguration)
	if err != nil {
		return nil, fmt.Errorf("[BuildAgentPayload] failed to parse action server config: %w", err)
	}
	if actionServerConfig != nil {
		actionPackages = append(actionPackages, *actionServerConfig)
	}

	payload := AgentServer.AgentPayload{
		Name:                 getAgentNameFromMetadata(metadata),
		Description:          metadata[0].Description,
		Version:              metadata[0].Version,
		Runbook:              runbook,
		Model:                getAgentModelFromMetadata(metadata),
		ActionPackages:       actionPackages,
		McpServers:           getMcpServersFromMetadata(metadata),
		Metadata:             metadata[0].Metadata,
		DocumentIntelligence: metadata[0].DocumentIntelligence,
		QuestionGroups:       metadata[0].QuestionGroups,
		AgentSettings:        common.NormalizeMap(metadata[0].AgentSettings),
		Public:               makePublic,
		SelectedTools:        getSelectedToolsFromMetadata(metadata),
		Extra: AgentServer.AgentExtra{
			WelcomeMessage:       metadata[0].WelcomeMessage,
			ConversationStarter:  metadata[0].ConversationStarter,
			DocumentIntelligence: metadata[0].DocumentIntelligence,
			AgentSettings:        common.NormalizeMap(metadata[0].AgentSettings),
		},
	}

	if modelConfiguration != "" {
		modelConfigObj, err := getModelConfig(modelConfiguration)
		if err != nil {
			return nil, fmt.Errorf("[BuildAgentPayload] failed to parse given model config: %w", err)
		}
		payload.Model.Config = modelConfigObj
	}

	langsmithConfig, err := getLangsmithConfig(langSmithConfiguration)
	if err != nil {
		return nil, fmt.Errorf("[BuildAgentPayload] failed to parse langsmith config: %w", err)
	}
	payload.AdvancedConfig.LangSmith = langsmithConfig

	return &payload, nil
}

func importAgentPackageToAgentServer(agentPackageDestPath, agentPackageSourcePath, serverUrl, modelConfiguration, actionServerConfiguration, langSmithConfiguration string, makePublic bool) error {
	agentServerClient := AgentServer.NewClient(serverUrl)

	// Read the agent package zip file
	zipBytes, err := os.ReadFile(agentPackageSourcePath)
	if err != nil {
		return fmt.Errorf("[importAgentPackageToAgentServer] failed to read agent package file: %w", err)
	}

	// Encode to base64
	packageBase64 := base64.StdEncoding.EncodeToString(zipBytes)

	// Extract metadata to get the agent name (we still need this for the payload)
	metadata, err := GenerateAgentMetadataFromPackageTo(agentPackageSourcePath, agentPackageDestPath)
	if err != nil {
		return fmt.Errorf("[importAgentPackageToAgentServer] failed to generate metadata: %w", err)
	}

	agentName := getAgentNameFromMetadata(metadata)
	if agentName == "" {
		return fmt.Errorf("[importAgentPackageToAgentServer] agent name not found in metadata")
	}

	// Build the AgentPackagePayload
	payload, err := BuildAgentPackagePayload(
		agentName,
		metadata,
		packageBase64,
		modelConfiguration,
		actionServerConfiguration,
		langSmithConfiguration,
		makePublic,
	)
	if err != nil {
		return fmt.Errorf("[importAgentPackageToAgentServer] failed to build payload: %w", err)
	}

	// Create or update agent using the package endpoint
	agent, err := createOrUpdateAgentFromPackage(*payload, agentServerClient)
	if err != nil {
		return fmt.Errorf("[importAgentPackageToAgentServer] failed to create or update Agent: %w", err)
	}

	// Prepare action packages locally (for Studio to use them)
	// This is needed even though the server processes the package, because
	// Studio needs local copies of custom action packages to run agents locally
	err = prepareActionPackages(metadata, agentPackageDestPath)
	if err != nil {
		// Don't fail the import if action package preparation fails
		// The agent and SDMs are already created on the server
		pretty.LogIfVerbose("[importAgentPackageToAgentServer] WARNING: failed to prepare action packages locally: %v", err)
	}

	agentJson, err := json.Marshal(agent)
	if err != nil {
		return fmt.Errorf("[importAgentPackageToAgentServer] failed to marshal Agent: %w", err)
	}
	rccCommon.Stdout("%s\n", agentJson)
	return nil
}

// BuildAgentPackagePayload builds an AgentPackagePayload from metadata and configuration
func BuildAgentPackagePayload(
	agentName string,
	metadata []*common.AgentPackageMetadata,
	packageBase64 string,
	modelConfiguration string,
	actionServerConfiguration string,
	langSmithConfiguration string,
	makePublic bool,
) (*AgentServer.AgentPackagePayload, error) {
	// Parse model configuration
	var modelConfig map[string]interface{}
	if modelConfiguration != "" {
		if err := json.Unmarshal([]byte(modelConfiguration), &modelConfig); err != nil {
			return nil, fmt.Errorf("[BuildAgentPackagePayload] failed to parse model config: %w", err)
		}
	}

	// Parse action server configuration
	var actionServers []AgentServer.ActionServerRef
	if actionServerConfiguration != "" {
		var actionServerConfig AgentServer.ActionServerRef
		if err := json.Unmarshal([]byte(actionServerConfiguration), &actionServerConfig); err != nil {
			return nil, fmt.Errorf("[BuildAgentPackagePayload] failed to parse action server config: %w", err)
		}
		actionServers = []AgentServer.ActionServerRef{actionServerConfig}
	}

	// Parse langsmith configuration
	var langsmithConfig *AgentServer.LangSmithConfig
	if langSmithConfiguration != "" {
		var config AgentServer.LangSmithConfig
		if err := json.Unmarshal([]byte(langSmithConfiguration), &config); err != nil {
			return nil, fmt.Errorf("[BuildAgentPackagePayload] failed to parse langsmith config: %w", err)
		}
		langsmithConfig = &config
	}

	// Get description from metadata
	description := ""
	if len(metadata) > 0 && metadata[0] != nil {
		description = metadata[0].Description
	}

	// Build the payload
	selectedTools := getSelectedToolsFromMetadata(metadata)
	payload := AgentServer.AgentPackagePayload{
		Name:               agentName,
		Description:        description,
		Public:             makePublic,
		AgentPackageBase64: &packageBase64,
		Model:              modelConfig,
		ActionServers:      actionServers,
		Langsmith:          langsmithConfig,
		SelectedTools:      &selectedTools,
	}

	return &payload, nil
}

// createOrUpdateAgentFromPackage creates or updates an agent from a package using the /agents/package endpoint
func createOrUpdateAgentFromPackage(
	payload AgentServer.AgentPackagePayload,
	client *AgentServer.Client,
) (*AgentServer.Agent, error) {
	agents, err := client.GetAgents(false)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch agents: %w", err)
	}

	var existingAgentID string
	for _, a := range *agents {
		if a.Name == payload.Name {
			existingAgentID = a.ID
			break
		}
	}

	var agent *AgentServer.Agent

	if existingAgentID != "" {
		pretty.LogIfVerbose("[createOrUpdateAgentFromPackage] found existing agent. will update: %s", payload.Name)
		agent, err = client.UpdateAgentFromPackage(existingAgentID, payload)
		if err != nil {
			return nil, fmt.Errorf("failed to update agent from package: %w", err)
		}
	} else {
		pretty.LogIfVerbose("[createOrUpdateAgentFromPackage] creating a new agent with name: %s", payload.Name)
		agent, err = client.CreateAgentFromPackage(payload)
		if err != nil {
			return nil, fmt.Errorf("failed to create agent from package: %w", err)
		}
	}

	pretty.LogIfVerbose("[createOrUpdateAgentFromPackage] succeeded!\n")

	rawAgent, err := client.GetAgent(agent.ID, true)
	if err != nil {
		return nil, fmt.Errorf("failed to get agent: %w", err)
	}

	return rawAgent, nil
}

// createOrUpdateAgent creates or updates an agent given an AgentPayload object and an AgentServer client
// DEPRECATED: Use createOrUpdateAgentFromPackage instead
func createOrUpdateAgent(
	payload AgentServer.AgentPayload,
	client *AgentServer.Client,
) (*AgentServer.Agent, error) {
	agents, err := client.GetAgents(false)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch agents: %w", err)
	}

	var existingAgentID string
	for _, a := range *agents {
		if a.Name == payload.Name {
			existingAgentID = a.ID
			break
		}
	}

	var agent *AgentServer.Agent

	if existingAgentID != "" {
		pretty.LogIfVerbose("[createOrUpdateAgent] found existing agent. will update: %s", payload.Name)
		agent, err = client.UpdateAgent(existingAgentID, payload)
		if err != nil {
			return nil, fmt.Errorf("failed to update agent: %w", err)
		}
	} else {
		pretty.LogIfVerbose("[createOrUpdateAgent] creating a new agent with name: %s", payload.Name)
		agent, err = client.CreateAgent(payload)
		if err != nil {
			return nil, fmt.Errorf("failed to create agent: %w", err)
		}
	}

	pretty.LogIfVerbose("[createOrUpdateAgent] succeeded!\n")

	rawAgent, err := client.GetAgent(agent.ID, true)
	if err != nil {
		return nil, fmt.Errorf("failed to get agent: %w", err)
	}

	return rawAgent, nil
}

// If an agent with the same name already exists, it will be updated.
// Otherwise, a new agent will be created.
var importCmd = &cobra.Command{
	Use:   "import",
	Short: "Import an agent package to the agent server.",
	Long:  `Import an agent package to the agent server. Outputs the created or updated agent JSON to stdout.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		agentPackageDestPath, err := func() (string, error) {
			if localAgentProjectPath != "" {
				return localAgentProjectPath, nil
			}
			return common.CreateTempDir("import")
		}()
		if err != nil {
			return fmt.Errorf("[importCmd] failed to create temporary directory: %w", err)
		}
		defer func() {
			if localAgentProjectPath == "" {
				os.RemoveAll(agentPackageDestPath)
			}
		}()

		return importAgentPackageToAgentServer(agentPackageDestPath, agentPackagePath, agentServerURL, modelConfig, actionServerConfig, langSmithConfig, public)
	},
}

func init() {
	packageCmd.AddCommand(importCmd)
	importCmd.Flags().StringVar(
		&agentPackagePath, "package", common.AGENT_PACKAGE_DEFAULT_NAME, "The .zip file to import.")
	if err := importCmd.MarkFlagRequired("package"); err != nil {
		fmt.Printf("failed to mark flag as required: %+v", err)
	}

	importCmd.Flags().StringVar(
		&agentServerURL, "agent-server-url", common.S4S_BACKEND_DEFAULT_URL, "Set the agent server URL.",
	)
	importCmd.Flags().StringVar(
		&modelConfig, "model-config", "", "The model configuration in JSON format.")
	importCmd.Flags().StringVar(
		&actionServerConfig, "action-server-config", "", "The action server configuration in JSON format.")
	importCmd.Flags().StringVar(
		&langSmithConfig, "langsmith-config", "", "The langsmith configuration in JSON format.")
	importCmd.Flags().BoolVar(
		&public, "public", false, "Make the agent public.")
	importCmd.Flags().StringVar(&localAgentProjectPath, "agent-project-path", "", "Create agent project to path.")

}
