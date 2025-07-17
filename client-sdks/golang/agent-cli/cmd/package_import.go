package cmd

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/common"
	"github.com/Sema4AI/agent-platform/client-sdks/golang/agent-cli/pretty"
	AgentServer "github.com/Sema4AI/agent-platform/client-sdks/golang/agent-client-go/pkg/client"
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
	return servers
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

func importAgentPackageToAgentServer(agentPackageDestPath, agentPackageSourcePath, serverUrl, modelConfiguration, actionServerConfiguration, langSmithConfiguration string, makePublic bool) error {
	agentServerClient := AgentServer.NewClient(serverUrl)

	metadata, err := GenerateAgentMetadataFromPackageTo(agentPackageSourcePath, agentPackageDestPath)
	if err != nil {
		return fmt.Errorf("failed to generate metadata: %w", err)
	}

	spec, err := ReadSpec(agentPackageDestPath)
	if err != nil {
		return fmt.Errorf("failed to read spec: %w", err)
	}

	runbook, err := ReadRunbook(filepath.Join(agentPackageDestPath, spec.AgentPackage.Agents[0].Runbook))
	if err != nil {
		return fmt.Errorf("failed to read runbook: %w", err)
	}

	actionPackages := []AgentServer.AgentActionPackage{}
	actionServerConfig, err := getActionServerConfig(actionServerConfiguration)
	if err != nil {
		return fmt.Errorf("failed to parse action server config: %w", err)
	}
	if actionServerConfig != nil {
		actionPackages = append(actionPackages, *actionServerConfig)
	}

	payload := AgentServer.AgentPayload{
		Name:           getAgentNameFromMetadata(metadata),
		Description:    metadata[0].Description,
		Version:        metadata[0].Version,
		Runbook:        runbook,
		Model:          getAgentModelFromMetadata(metadata),
		ActionPackages: actionPackages,
		McpServers:     getMcpServersFromMetadata(metadata),
		Metadata:       metadata[0].Metadata,
		Extra: AgentServer.AgentExtra{
			WelcomeMessage:      metadata[0].WelcomeMessage,
			ConversationStarter: metadata[0].ConversationStarter,
		},
		Public: makePublic,
	}

	if modelConfiguration != "" {
		modelConfigObj, err := getModelConfig(modelConfiguration)
		if err != nil {
			return fmt.Errorf("failed to parse given model config: %w", err)
		}
		payload.Model.Config = modelConfigObj
	}

	langsmithConfig, err := getLangsmithConfig(langSmithConfiguration)
	if err != nil {
		return fmt.Errorf("failed to parse langsmith config: %w", err)
	}
	payload.AdvancedConfig.LangSmith = langsmithConfig

	agent, err := createOrUpdateAgent(payload, agentServerClient)
	if err != nil {
		return fmt.Errorf("failed to create or update Agent: %w", err)
	}
	agentJson, err := json.Marshal(agent)
	if err != nil {
		return fmt.Errorf("failed to marshal Agent: %w", err)
	}
	rccCommon.Stdout("%s\n", agentJson)
	return nil
}

// createOrUpdateAgent creates or updates an agent given an AgentPayload object and an AgentServer client
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
		pretty.LogIfVerbose("[createOrUpdateAgent] payload: %+v", payload)
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
