package cmd

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	AgentServer "github.com/Sema4AI/agent-client-go/pkg/client"
	"github.com/Sema4AI/agents-spec/cli/common"
	rccCommon "github.com/robocorp/rcc/common"
	"github.com/robocorp/rcc/pathlib"
	"github.com/spf13/cobra"
)

var (
	public                bool
	modelConfig           string
	actionServerConfig    string
	langSmithConfig       string
	localAgentProjectPath string
)

func getAgentNameFromMetadata(metadata []*agentPackageMetadata) string {
	return metadata[0].Name
}

func getAgentModelFromMetadata(metadata []*agentPackageMetadata) *AgentServer.AgentModel {
	return &AgentServer.AgentModel{
		Provider: metadata[0].Model.Provider,
		Name:     metadata[0].Model.Name,
		Config:   map[string]interface{}{},
	}
}
func getActionPackagesFromMetadata(metadata []*agentPackageMetadata) []agentPackageActionPackageMetadata {
	return metadata[0].ActionPackages
}

func getKnowledgeFilesFromMetadata(metadata []*agentPackageMetadata) []agentPackageMetadataKnowledge {
	return metadata[0].Knowledge
}

func getAgentPackageBase64(agentPackagePath string) (string, error) {
	fileContent, err := os.ReadFile(agentPackagePath)
	if err != nil {
		return "", fmt.Errorf("failed to read agent package file: %w", err)
	}
	return base64.StdEncoding.EncodeToString(fileContent), nil
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

func getActionServerConfig(actionServerConfig string) (AgentServer.AgentPayloadPackageActionServer, error) {
	if actionServerConfig == "" {
		return AgentServer.AgentPayloadPackageActionServer{}, nil
	}
	var config AgentServer.AgentPayloadPackageActionServer
	if err := json.Unmarshal([]byte(actionServerConfig), &config); err != nil {
		return AgentServer.AgentPayloadPackageActionServer{}, fmt.Errorf("failed to parse action server config: %w", err)
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

func createOrUpdateAgent(
	payload AgentServer.AgentPayloadPackage,
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
		logVerbose("Found an existing agent with name: %s. Updating.\n", payload.Name)
		agent, err = client.UpdateAgentViaPackage(existingAgentID, payload)
		if err != nil {
			return nil, fmt.Errorf("failed to update agent: %w", err)
		}
	} else {
		logVerbose("Creating a new agent with name: %s.\n", payload.Name)
		agent, err = client.CreateAgentViaPackage(payload)
		if err != nil {
			return nil, fmt.Errorf("failed to create agent: %w", err)
		}
	}

	rawAgent, err := client.GetAgent(agent.ID, true)
	if err != nil {
		return nil, fmt.Errorf("failed to get agent: %w", err)
	}

	return rawAgent, nil
}

func preparePayload(
	metadata []*agentPackageMetadata,
	agentPackagePath string,
	public bool,
	modelConfig string,
	actionServerConfig string,
	langsmithConfig string,
) (*AgentServer.AgentPayloadPackage, error) {
	agentPackageBase64, err := getAgentPackageBase64(agentPackagePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read agent package file: %w", err)
	}

	payload := AgentServer.AgentPayloadPackage{
		Name:               getAgentNameFromMetadata(metadata),
		Public:             public,
		AgentPackageUrl:    nil,
		AgentPackageBase64: &agentPackageBase64,
		Model:              *getAgentModelFromMetadata(metadata),
		ActionServers:      []AgentServer.AgentPayloadPackageActionServer{},
	}

	modelConfigObj, err := getModelConfig(modelConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to parse given model config: %w", err)
	}
	payload.Model.Config = modelConfigObj

	actionServerObj, err := getActionServerConfig(actionServerConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to parse given action server config: %w", err)
	}
	payload.ActionServers = []AgentServer.AgentPayloadPackageActionServer{actionServerObj}

	langsmithConfigObj, err := getLangsmithConfig(langsmithConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to parse given langsmith config: %w", err)
	}
	payload.LangSmith = langsmithConfigObj

	return &payload, nil
}

func prepareActionPackages(metadata []*agentPackageMetadata, agentPackageDestPath string) error {
	galleryRootDir := common.S4SActionsGalleryLocation()
	if !pathlib.Exists(galleryRootDir) {
		logVerbose("Skipping the Action Packages preparation as Sema4.ai Studio Gallery was not found")
		return nil
	}

	logVerbose("Importing Action Packages...")
	actionPackages := getActionPackagesFromMetadata(metadata)
	for _, actionPackage := range actionPackages {
		logVerbose("Action Package Path: %+v", actionPackage.Path)

		// skipping action packages coming from Sema4.ai
		if strings.Contains(actionPackage.Path, common.S4S_BUNDLED_ACTIONS_DIR) {
			logVerbose("Skipping import of Action Package: %s", actionPackage.Path)
			continue
		}

		// determine the organization and the package name from the path
		actionPackageOrganization, actionPackagePackageName := filepath.Split(actionPackage.Path)
		if actionPackageOrganization == "" || actionPackagePackageName == "" {
			return fmt.Errorf("[prepareActionPackages] failed to parse Action Package path")
		}

		// (source) calculate where the action packages need to be copied from
		actionPackageSourcePath := filepath.Join(agentPackageDestPath, common.AGENT_PROJECT_ACTIONS_DIR, actionPackageOrganization, actionPackagePackageName)
		logVerbose("Action Package Path from the extracted Agent Package: %+v", actionPackageSourcePath)
		if !pathlib.Exists(actionPackageSourcePath) {
			return fmt.Errorf("[prepareActionPackages] calculated source path does not exist")
		}

		// (destination) calculate where the action packages need to be copied to
		actionPackageDestPath := filepath.Join(galleryRootDir, actionPackageOrganization, actionPackagePackageName, actionPackage.Version)
		logVerbose("Importing Action Package to: %+v", actionPackageDestPath)
		if err := os.MkdirAll(actionPackageDestPath, 0o755); err != nil {
			return fmt.Errorf("[prepareActionPackages] failed to create destination for Action Package: %w", err)
		}

		// we don't have a zipped action package but an expanded one
		if err := common.CopyDir(actionPackageSourcePath, actionPackageDestPath, true); err != nil {
			return fmt.Errorf("[prepareActionPackages] failed to copy files for Action Package: %w", err)
		}
		logVerbose("Action Package  '%s'  imported successfully to: %s", actionPackage.Name, actionPackageDestPath)
	}

	return nil
}

func importAgentPackageToAgentServer(agentPackageDestPath, agentPackageSourcePath, serverUrl, modelConfiguration, actionServerConfiguration, langSmithConfiguration string, makePublic bool) error {
	agentServerClient := AgentServer.NewClient(serverUrl)

	metadata, err := generateAgentMetadataFromPackageTo(agentPackageSourcePath, agentPackageDestPath)
	if err != nil {
		return fmt.Errorf("failed to generate metadata: %w", err)
	}
	payload, err := preparePayload(
		metadata,
		agentPackageSourcePath,
		makePublic,
		modelConfiguration,
		actionServerConfiguration,
		langSmithConfiguration,
	)
	if err != nil {
		return fmt.Errorf("failed to prepare payload: %w", err)
	}
	err = prepareActionPackages(metadata, agentPackageDestPath)
	if err != nil {
		return fmt.Errorf("failed to prepare Action Packages: %w", err)
	}
	agent, err := createOrUpdateAgent(*payload, agentServerClient)
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
	importCmd.MarkFlagRequired("package")
}
